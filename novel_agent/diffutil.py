from __future__ import annotations

import difflib
import re
from typing import Any


_TOKEN_RE = re.compile(r"[\u4e00-\u9fff]|[A-Za-z0-9_]+|[^\s]")


def _tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall(text or "")


def _paragraphs(text: str) -> list[str]:
    normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    parts = re.split(r"\n{2,}", normalized)
    return parts if parts != [""] else []


def build_text_diff(*, before_title: str, before_content: str, after_title: str, after_content: str) -> dict[str, Any]:
    sections: list[dict[str, Any]] = []
    added = 0
    removed = 0

    if before_title.strip() != after_title.strip():
        title_lines: list[dict[str, str]] = []
        if before_title.strip():
            title_lines.append({"type": "removed", "text": before_title.strip()})
            removed += len(_tokens(before_title))
        if after_title.strip():
            title_lines.append({"type": "added", "text": after_title.strip()})
            added += len(_tokens(after_title))
        sections.append({"type": "title", "lines": title_lines})

    before_paras = _paragraphs(before_content)
    after_paras = _paragraphs(after_content)
    matcher = difflib.SequenceMatcher(a=before_paras, b=after_paras, autojunk=False)
    content_lines: list[dict[str, str]] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for para in before_paras[i1:i2]:
                content_lines.append({"type": "context", "text": para})
            continue
        if tag in {"replace", "delete"}:
            for para in before_paras[i1:i2]:
                content_lines.append({"type": "removed", "text": para})
                removed += len(_tokens(para))
        if tag in {"replace", "insert"}:
            for para in after_paras[j1:j2]:
                content_lines.append({"type": "added", "text": para})
                added += len(_tokens(para))
    if content_lines:
        sections.append({"type": "content", "lines": content_lines})

    return {"added": added, "removed": removed, "sections": sections}

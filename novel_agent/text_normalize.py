from __future__ import annotations

import hashlib


def normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def normalize_draft_title(title: str) -> str:
    return title.strip()


def normalize_draft_content(content: str) -> str:
    """Normalize newlines only; do not trim body whitespace."""
    return normalize_newlines(content)


def draft_content_hash(title: str, content: str) -> str:
    normalized_title = normalize_draft_title(title)
    normalized_content = normalize_draft_content(content)
    payload = f"{normalized_title}\0{normalized_content}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()

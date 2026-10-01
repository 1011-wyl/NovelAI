"""Small JSON/text helpers used by remote LLM prompt construction."""

from __future__ import annotations

import json
from typing import Any


def _compact_json(value: Any) -> str:
    """Keep JSON semantics while removing indentation-only prompt tokens."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _tail(text: str, limit: int) -> str:
    return text[-limit:] if text else ""

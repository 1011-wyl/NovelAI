"""JSON helpers shared by SQLite feature stores."""

from __future__ import annotations

import json
from typing import Any


def dump_json(value: Any) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        default=lambda item: item.model_dump(mode="json")
        if hasattr(item, "model_dump")
        else str(item),
    )

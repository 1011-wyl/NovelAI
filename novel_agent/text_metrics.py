from __future__ import annotations


def count_content_chars(content: str | None) -> int:
    """Count non-whitespace characters in chapter body text."""
    if not content:
        return 0
    return sum(1 for char in content if not char.isspace())

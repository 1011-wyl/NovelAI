from __future__ import annotations


def count_content_chars(content: str | None) -> int:
    """Count non-whitespace characters in chapter body text."""
    if not content:
        return 0
    return sum(1 for char in content if not char.isspace())


def count_chapter_body_chars(content: str | None) -> int:
    """Count non-whitespace characters after dropping the title line."""
    if not content:
        return 0
    text = content.replace("\r\n", "\n").replace("\r", "\n")
    _title, separator, rest = text.partition("\n")
    body = rest if separator else text
    return count_content_chars(body)

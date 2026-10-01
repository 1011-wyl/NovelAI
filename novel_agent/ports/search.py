from __future__ import annotations

from typing import Protocol


class SearchAdapter(Protocol):
    name: str
    enabled: bool

    def research(self, questions: list[str]) -> list[dict[str, object]]: ...

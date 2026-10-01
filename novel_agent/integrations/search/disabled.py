from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class DisabledSearchAdapter:
    name: str = "disabled"
    enabled: bool = False

    def research(self, questions: list[str]) -> list[dict[str, object]]:
        return []

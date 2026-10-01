from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class DisabledEmbeddingGateway:
    name: str = "disabled"
    model: str = "disabled"
    enabled: bool = False

    def embed(self, texts: list[str]) -> list[list[float]]:
        return []

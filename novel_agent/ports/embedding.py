from __future__ import annotations

from typing import Protocol


class EmbeddingGateway(Protocol):
    name: str
    model: str
    enabled: bool

    def embed(self, texts: list[str]) -> list[list[float]]: ...

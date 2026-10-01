from __future__ import annotations

from typing import Protocol


class PublisherAdapter(Protocol):
    name: str

    def publish(self, project_id: str, chapter_id: str, title: str, content: str) -> dict[str, str]: ...

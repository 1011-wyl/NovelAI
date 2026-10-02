"""Feature ports for story-design persistence."""

from __future__ import annotations

from typing import Any, Protocol

from novel_agent.features.projects.models import ProjectRecord
from novel_agent.features.story_design.models import CreativeBrief
from novel_agent.models import CharacterRecord, WorldFactRecord


class StoryDesignStore(Protocol):
    def create_project(
        self,
        project: ProjectRecord,
        characters: list[CharacterRecord],
        world_facts: list[WorldFactRecord],
    ) -> ProjectRecord: ...

    def save_draft_brief(
        self,
        project_id: str,
        brief: CreativeBrief,
        *,
        source: str,
        feedback: str = "",
    ) -> ProjectRecord: ...

    def get_project(self, project_id: str) -> ProjectRecord: ...

    def get_brief_version(self, project_id: str, version: int) -> CreativeBrief: ...

    def list_brief_versions(self, project_id: str) -> list[dict[str, Any]]: ...

    def list_chapters(self, project_id: str) -> list[Any]: ...

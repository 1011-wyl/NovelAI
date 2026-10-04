"""Transitional project-detail aggregator used until Memory/Chapter stores split."""

from __future__ import annotations

from typing import Any, Protocol

from novel_agent.features.projects.models import ProjectRecord


class ProjectDetailSource(Protocol):
    def get_project(self, project_id: str) -> ProjectRecord: ...

    def list_chapters(self, project_id: str) -> list[Any]: ...

    def get_latest_run_id(self, project_id: str) -> str | None: ...

    def list_events(self, run_id: str) -> list[Any]: ...

    def list_characters(self, project_id: str) -> list[Any]: ...

    def list_world_facts(self, project_id: str) -> list[Any]: ...

    def list_timeline(self, project_id: str) -> list[Any]: ...

    def list_research_sources(self, project_id: str) -> list[Any]: ...

    def semantic_document_count(self, project_id: str) -> int: ...

    def reserve_count(self, project_id: str) -> int: ...


class SkillsReadinessProvider(Protocol):
    def readiness(self) -> dict[str, object]: ...


class GenreCardProvider(Protocol):
    def readiness(self) -> dict[str, object]: ...

    def genre_card(self, genre: str, audience_channel: str) -> Any: ...


class AggregatingProjectDetailReader:
    def __init__(
        self,
        source: ProjectDetailSource,
        story_skills: SkillsReadinessProvider,
        writing_skills: GenreCardProvider,
    ) -> None:
        self._source = source
        self._story_skills = story_skills
        self._writing_skills = writing_skills

    def read_project_detail(self, project_id: str) -> dict[str, object]:
        project = self._source.get_project(project_id)
        chapters = self._source.list_chapters(project_id)
        latest_run_id = self._source.get_latest_run_id(project_id)
        latest_events = (
            self._source.list_events(latest_run_id) if latest_run_id else []
        )
        card = self._writing_skills.genre_card(
            project.request.genre,
            project.request.audience_channel,
        )
        return {
            "project": project,
            "chapters": chapters,
            "latest_events": latest_events,
            "characters": self._source.list_characters(project_id),
            "world_facts": self._source.list_world_facts(project_id),
            "timeline": self._source.list_timeline(project_id),
            "research_sources": self._source.list_research_sources(project_id),
            "semantic_document_count": self._source.semantic_document_count(project_id),
            "reserve_count": self._source.reserve_count(project_id),
            "chapter_failures": (
                self._source.list_chapter_failure_diagnostics(project_id)
                if hasattr(self._source, "list_chapter_failure_diagnostics")
                else []
            ),
            "skills": {
                "story_skills": self._story_skills.readiness(),
                "oh_story": {
                    **self._writing_skills.readiness(),
                    "active_genre_card": card.name if card else None,
                },
            },
        }

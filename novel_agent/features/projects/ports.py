"""Feature ports for project lifecycle persistence and detail reads."""

from __future__ import annotations

from typing import Any, Protocol

from novel_agent.features.projects.models import ProjectRecord, ProjectStatus


class ProjectStore(Protocol):
    def list_projects(self) -> list[ProjectRecord]: ...

    def get_project(self, project_id: str) -> ProjectRecord: ...

    def update_project_status(
        self, project_id: str, status: ProjectStatus
    ) -> ProjectRecord: ...

    def confirm_project(self, project_id: str) -> ProjectRecord: ...

    def delete_project(self, project_id: str, *, force: bool = False) -> None: ...

    def list_chapters(self, project_id: str) -> list[Any]: ...


class ProjectDetailReader(Protocol):
    def read_project_detail(self, project_id: str) -> dict[str, object]: ...

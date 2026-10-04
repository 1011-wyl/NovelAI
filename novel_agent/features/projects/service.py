"""Project lifecycle application service."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from novel_agent.features.projects.models import (
    ProjectMetadataUpdate,
    ProjectRecord,
    ProjectStatus,
    ProjectSummary,
)
from novel_agent.features.projects.ports import ProjectDetailReader, ProjectStore


@dataclass(slots=True)
class ProjectService:
    store: ProjectStore
    detail_reader: ProjectDetailReader
    recover_handler: Callable[[str], ProjectRecord] | None = None

    def list_projects(self) -> list[ProjectRecord]:
        """Full records — prefer list_project_summaries for bookshelf HTTP."""
        return self.store.list_projects()

    def list_project_summaries(self) -> list[ProjectSummary]:
        return self.store.list_project_summaries()

    def get_detail(self, project_id: str) -> dict[str, object]:
        return self.detail_reader.read_project_detail(project_id)

    def confirm(self, project_id: str) -> ProjectRecord:
        return self.store.confirm_project(project_id)

    def pause(self, project_id: str) -> ProjectRecord:
        return self.store.update_project_status(project_id, ProjectStatus.PAUSED)

    def resume(self, project_id: str) -> ProjectRecord:
        project = self.store.get_project(project_id)
        if not project.confirmed:
            raise ValueError("创作方案尚未确认")
        return self.store.update_project_status(project_id, ProjectStatus.ACTIVE)

    def update_metadata(
        self, project_id: str, update: ProjectMetadataUpdate
    ) -> ProjectSummary:
        return self.store.update_project_metadata(project_id, update.title)

    def delete(
        self, project_id: str, confirmation_title: str | None = None
    ) -> None:
        project = self.store.get_project(project_id)
        editable_draft = (
            project.status == ProjectStatus.DRAFT
            and not project.confirmed
            and not self.store.list_chapters(project_id)
        )
        if editable_draft:
            if project.status != ProjectStatus.DRAFT or project.confirmed:
                raise ValueError("创作方案已确认，不能再按草稿方式修改")
            if self.store.list_chapters(project_id):
                raise ValueError("项目已经生成章节，不能再按草稿方式修改")
            self.store.delete_project(project_id)
            return
        if confirmation_title != project.title:
            raise ValueError("删除正式作品时必须完整输入当前书名进行确认")
        self.store.delete_project(project_id, force=True)

    def recover(self, project_id: str) -> ProjectRecord:
        if self.recover_handler is None:
            raise RuntimeError("项目恢复代理未配置")
        return self.recover_handler(project_id)

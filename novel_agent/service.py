from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from novel_agent.integrations.embedding.disabled import DisabledEmbeddingGateway
from novel_agent.integrations.search.disabled import DisabledSearchAdapter
from novel_agent.ports import EmbeddingGateway, LLMGateway, SearchAdapter
from novel_agent.chapter_workspace import ChapterWorkspaceMixin
from novel_agent.features.analytics.service import AnalyticsService
from novel_agent.features.projects.detail_reader import AggregatingProjectDetailReader
from novel_agent.features.projects.service import ProjectService
from novel_agent.features.story_design.characters import build_character_records
from novel_agent.features.story_design.service import StoryDesignService
from novel_agent.memory_manager import MemoryManager
from novel_agent.models import (
    BriefRegenerateRequest,
    ChapterStatus,
    CharacterRecord,
    CreativeBrief,
    IssueSeverity,
    NovelCreateRequest,
    ProjectRecord,
    ProjectStatus,
    ReviewDecision,
    WorkflowResult,
)
from novel_agent.repository import RepositoryError, SQLiteRepository
from novel_agent.story_skills import StorySkillsRuntime
from novel_agent.writing_skills import OhStoryWritingRuntime
from novel_agent.workflow import ChapterWorkflow


@dataclass(slots=True)
class NovelAgentService(ChapterWorkspaceMixin):
    """Compatibility Facade / coordinator.

    Project lifecycle and story-design methods delegate to ProjectService /
    StoryDesignService. Chapter workflow, memory, revision and recover remain
    here until later modular splits.
    """

    repository: SQLiteRepository
    gateway: LLMGateway
    search: SearchAdapter
    max_revision_attempts: int = 2
    embedding: EmbeddingGateway = field(default_factory=DisabledEmbeddingGateway)
    semantic_retrieval_limit: int = 6
    story_skills: StorySkillsRuntime = field(default_factory=StorySkillsRuntime.disabled)
    writing_skills: OhStoryWritingRuntime = field(default_factory=OhStoryWritingRuntime.disabled)
    memory_manager: MemoryManager = field(default_factory=MemoryManager)
    story_design: StoryDesignService | None = None
    projects: ProjectService | None = None

    def __post_init__(self) -> None:
        if self.story_design is None:
            self.story_design = StoryDesignService(
                store=self.repository,
                gateway=self.gateway,
            )
        if self.projects is None:
            self.projects = ProjectService(
                store=self.repository,
                detail_reader=AggregatingProjectDetailReader(
                    self.repository,
                    self.story_skills,
                    self.writing_skills,
                ),
                recover_handler=self.recover_known_issue,
            )

    def create_novel(self, request: NovelCreateRequest) -> ProjectRecord:
        assert self.story_design is not None
        self.story_design.gateway = self.gateway
        return self.story_design.create_story(request)

    @staticmethod
    def _character_records(
        project_id: str,
        request: NovelCreateRequest,
        brief: CreativeBrief,
    ) -> list[CharacterRecord]:
        return build_character_records(project_id, request, brief)

    def confirm_novel(self, project_id: str) -> ProjectRecord:
        assert self.projects is not None
        return self.projects.confirm(project_id)

    def update_draft_brief(
        self, project_id: str, brief: CreativeBrief
    ) -> ProjectRecord:
        assert self.story_design is not None
        return self.story_design.update_brief(project_id, brief)

    def regenerate_draft_brief(
        self, project_id: str, change: BriefRegenerateRequest
    ) -> ProjectRecord:
        assert self.story_design is not None
        self.story_design.gateway = self.gateway
        return self.story_design.regenerate_brief(project_id, change)

    def restore_draft_brief(self, project_id: str, version: int) -> ProjectRecord:
        assert self.story_design is not None
        return self.story_design.restore_brief(project_id, version)

    def delete_novel(
        self, project_id: str, *, confirmation_title: str | None = None
    ) -> None:
        assert self.projects is not None
        self.projects.delete(project_id, confirmation_title=confirmation_title)

    def rework_chapter(
        self,
        project_id: str,
        chapter_number: int,
        *,
        feedback: str = "",
        mode: str = "auto",
    ) -> ProjectRecord:
        project = self.repository.get_project(project_id)
        if project.status == ProjectStatus.DRAFT:
            raise ValueError("草稿项目没有可重做的章节，请先确认创作方案")
        if project.status == ProjectStatus.ARCHIVED:
            raise ValueError("归档项目不能直接重做，请先恢复项目状态")
        existing = self.repository.get_chapter_by_number(project_id, chapter_number)
        if existing is None:
            raise RepositoryError(f"找不到第{chapter_number}章")
        from novel_agent.features.chapter_planning.rework_policy import resolve_requested_mode
        from novel_agent.models import ReviewReport

        latest_report = None
        with self.repository.connection() as conn:
            report_row = conn.execute(
                """SELECT report_json FROM review_reports
                WHERE chapter_id=? ORDER BY created_at DESC LIMIT 1""",
                (existing.id,),
            ).fetchone()
        if report_row and report_row["report_json"]:
            latest_report = ReviewReport.model_validate_json(report_row["report_json"])
        resolve_requested_mode(
            mode or "auto",
            report=latest_report,
            chapter_number=chapter_number,
            plan=existing.plan,
        )
        base_characters = self._character_records(
            project_id, project.request, project.brief
        )
        result = self.repository.rework_chapter(
            project_id,
            chapter_number,
            base_characters=base_characters,
            feedback=feedback,
        )
        self.repository.save_setting(f"rework_mode:{existing.id}", mode or "auto")
        return result

    def get_usage(self) -> dict[str, Any]:
        if hasattr(self.gateway, "usage_summary"):
            return self.gateway.usage_summary()
        return {"model": self.gateway.name, "request_count": 0}

    def get_token_statistics(
        self, start_date: str, end_date: str
    ) -> dict[str, Any]:
        return AnalyticsService(self.repository.analytics).get_token_statistics(
            start_date, end_date
        )

    def pause_novel(self, project_id: str) -> ProjectRecord:
        assert self.projects is not None
        return self.projects.pause(project_id)

    def resume_novel(self, project_id: str) -> ProjectRecord:
        assert self.projects is not None
        return self.projects.resume(project_id)

    def recover_known_issue(self, project_id: str) -> ProjectRecord:
        """Recover a project from HUMAN_REQUIRED to ACTIVE.

        Handles the legacy protagonist-name issue specifically. For other
        failure modes, resets the failed chapter back to PLANNED and
        returns the project to ACTIVE so the user can retry generation.
        """
        project = self.repository.get_project(project_id)
        if project.status != ProjectStatus.HUMAN_REQUIRED:
            raise ValueError("项目不处于需要人工处理状态")
        diagnostic = self.repository.get_latest_run_diagnostic(project_id)
        if not diagnostic:
            return self.repository.update_project_status(
                project_id, ProjectStatus.ACTIVE
            )
        if diagnostic.get("error_code") == "REVIEW_RETRY_EXHAUSTED":
            report = diagnostic.get("checkpoint", {}).get("report", {})
            issues = report.get("issues", [])
            known = bool(issues) and all(
                issue.get("category") == "character"
                and issue.get("message") == "主角在正文中缺失"
                for issue in issues
            )
            if known:
                chapter = self.repository.get_chapter_by_number(
                    project_id, project.current_chapter + 1
                )
                if chapter and chapter.status == ChapterStatus.FAILED:
                    return self.repository.recover_protagonist_name_issue(
                        project_id,
                        project.brief,
                        project.brief.protagonist_name,
                        project.brief.protagonist_profile,
                        chapter.id,
                    )
        # Fallback: reset failed chapter and return project to ACTIVE
        next_chapter = self.repository.get_chapter_by_number(
            project_id, project.current_chapter + 1
        )
        if next_chapter and next_chapter.status == ChapterStatus.FAILED:
            self.repository.update_chapter(
                next_chapter.id, status=ChapterStatus.PLANNED,
            )
        return self.repository.update_project_status(
            project_id, ProjectStatus.ACTIVE
        )

    def generate_next_chapter(self, project_id: str) -> WorkflowResult:
        project = self.repository.get_project(project_id)
        if project.status == ProjectStatus.HUMAN_REQUIRED:
            diagnostic = self.repository.get_latest_run_diagnostic(project_id)
            report = (diagnostic or {}).get("checkpoint", {}).get("report", {})
            if (
                (diagnostic or {}).get("error_code") == "REVIEW_RETRY_EXHAUSTED"
                and report.get("decision") != ReviewDecision.HUMAN_REQUIRED.value
            ):
                feedback = "；".join(
                    str(issue.get("suggestion", "")).strip()
                    for issue in report.get("issues", [])
                    if issue.get("severity") in {
                        IssueSeverity.BLOCKER.value,
                        IssueSeverity.MAJOR.value,
                    }
                    and str(issue.get("suggestion", "")).strip()
                )[:2000]
                chapter_id = str((diagnostic or {}).get("chapter_id") or "")
                if feedback and chapter_id:
                    self.repository.save_setting(
                        f"rework_feedback:{chapter_id}", feedback
                    )
                self.recover_known_issue(project_id)
        workflow = ChapterWorkflow(
            repository=self.repository,
            gateway=self.gateway,
            search=self.search,
            max_revision_attempts=self.max_revision_attempts,
            embedding=self.embedding,
            semantic_retrieval_limit=self.semantic_retrieval_limit,
            story_skills=self.story_skills,
            writing_skills=self.writing_skills,
            memory_manager=self.memory_manager,
        )
        return workflow.run(project_id)

    def fill_reserve(self, project_id: str, limit: int | None = None) -> list[WorkflowResult]:
        project = self.repository.get_project(project_id)
        target = project.request.reserve_target
        missing = max(0, target - self.repository.reserve_count(project_id))
        if limit is not None:
            missing = min(missing, max(0, limit))
        results: list[WorkflowResult] = []
        for _ in range(missing):
            result = self.generate_next_chapter(project_id)
            results.append(result)
            if result.chapter.status == ChapterStatus.FAILED:
                break
        return results

    def rebuild_character_archives(self, project_id: str) -> dict[str, object]:
        project = self.repository.get_project(project_id)
        chapters = [
            chapter
            for chapter in self.repository.list_chapters(project_id)
            if chapter.status == ChapterStatus.READY and chapter.content
        ]
        processed = 0
        updated_names: set[str] = set()
        failures: list[dict[str, object]] = []
        for chapter in chapters:
            roster = self.repository.list_characters(project_id)
            try:
                extracted = self.gateway.extract_character_memories(
                    project.brief,
                    chapter.number,
                    chapter.content or "",
                    roster,
                )
                plan_updates = chapter.plan.character_updates if chapter.plan else []
                updates = ChapterWorkflow._merge_character_updates(
                    [*plan_updates, *extracted.characters]
                )
                self.repository.upsert_character_memories(
                    project_id,
                    chapter.number,
                    updates,
                )
                processed += 1
                updated_names.update(item.name for item in updates)
            except Exception as exc:
                failures.append(
                    {"chapter": chapter.number, "error": type(exc).__name__}
                )
        removed_count = 0
        if chapters and not failures:
            keep_names = {
                profile.name for profile in project.brief.character_profiles
            }
            keep_names.update(updated_names)
            removed_count = self.repository.prune_character_archives(
                project_id,
                keep_names,
            )
        return {
            "processed_chapters": processed,
            "character_count": len(self.repository.list_characters(project_id)),
            "updated_characters": sorted(updated_names),
            "removed_nonimportant": removed_count,
            "failures": failures,
        }

    def project_detail(self, project_id: str) -> dict[str, object]:
        assert self.projects is not None
        return self.projects.get_detail(project_id)

    def semantic_search(
        self, project_id: str, query: str, limit: int | None = None
    ) -> list[dict[str, object]]:
        if not self.embedding.enabled:
            raise ValueError("Embedding 未启用，无法执行语义检索")
        query = query.strip()
        if not query:
            raise ValueError("语义检索内容不能为空")
        vector = self.embedding.embed([query])[0]
        return self.repository.semantic_search(
            project_id,
            vector,
            limit=min(max(1, limit or self.semantic_retrieval_limit), 20),
        )

    def _assert_editable_draft(self, project_id: str) -> ProjectRecord:
        assert self.story_design is not None
        return self.story_design._assert_editable_draft(project_id)

    @staticmethod
    def _brief_fields(sections: list[str]) -> list[str]:
        return StoryDesignService.brief_fields(sections)


def build_service(repository: SQLiteRepository, gateway: LLMGateway) -> NovelAgentService:
    return NovelAgentService(
        repository,
        gateway,
        DisabledSearchAdapter(),
        embedding=DisabledEmbeddingGateway(),
    )

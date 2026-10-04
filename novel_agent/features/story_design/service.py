"""Story-design application service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from novel_agent.features.projects.models import ProjectRecord, ProjectStatus
from novel_agent.features.story_design.characters import build_character_records
from novel_agent.features.story_design.models import (
    BriefRegenerateRequest,
    CreativeBrief,
    NovelCreateRequest,
)
from novel_agent.features.story_design.ports import StoryDesignStore
from novel_agent.features.story_design.requirements import validate_requirements
from novel_agent.models import WorldFactRecord, new_id, utc_now
from novel_agent.ports import LLMGateway
from novel_agent.telemetry import llm_call_scope


@dataclass(slots=True)
class StoryDesignService:
    store: StoryDesignStore
    gateway: LLMGateway
    id_factory: Callable[[str], str] = new_id
    clock: Callable[[], str] = utc_now

    def create_story(self, request: NovelCreateRequest) -> ProjectRecord:
        validate_requirements(request)
        project_id = self.id_factory("novel")
        with llm_call_scope(project_id=project_id, category="agent"):
            brief = self.gateway.create_brief(request)
        if request.preferred_title:
            candidates = [request.preferred_title, *brief.title_candidates]
            brief = brief.model_copy(
                update={
                    "selected_title": request.preferred_title,
                    "title_candidates": list(dict.fromkeys(candidates))[:6],
                }
            )
        now = self.clock()
        confirmed = not request.require_plan_confirmation
        project = ProjectRecord(
            id=project_id,
            title=brief.selected_title,
            status=ProjectStatus.ACTIVE if confirmed else ProjectStatus.DRAFT,
            request=request,
            brief=brief,
            confirmed=confirmed,
            current_chapter=0,
            created_at=now,
            updated_at=now,
        )
        characters = build_character_records(project_id, request, brief)
        facts = [
            WorldFactRecord(
                id=self.id_factory("fact"),
                project_id=project_id,
                category="hard_rule",
                statement=statement,
                locked=True,
            )
            for statement in brief.world_rules
        ]
        return self.store.create_project(project, characters, facts)

    def update_brief(self, project_id: str, brief: CreativeBrief) -> ProjectRecord:
        self._assert_editable_draft(project_id)
        brief = CreativeBrief.model_validate(brief.model_dump(mode="json"))
        return self.store.save_draft_brief(
            project_id, brief, source="manual_edit"
        )

    def regenerate_brief(
        self, project_id: str, change: BriefRegenerateRequest
    ) -> ProjectRecord:
        project = self._assert_editable_draft(project_id)
        fields = self.brief_fields(change.sections)
        with llm_call_scope(project_id=project_id, category="agent"):
            if change.feedback or change.sections:
                candidate = self.gateway.revise_brief(
                    project.request,
                    project.brief,
                    change.feedback,
                    fields,
                )
            else:
                candidate = self.gateway.create_brief(project.request)
        if fields:
            merged = project.brief.model_dump(mode="json")
            generated = candidate.model_dump(mode="json")
            for name in fields:
                merged[name] = generated[name]
            candidate = CreativeBrief.model_validate(merged)
        else:
            candidate = CreativeBrief.model_validate(
                candidate.model_dump(mode="json")
            )
        source = "partial_regenerate" if change.sections else "regenerate"
        if change.feedback:
            source = "feedback_regenerate"
        return self.store.save_draft_brief(
            project_id,
            candidate,
            source=source,
            feedback=change.feedback,
        )

    def restore_brief(self, project_id: str, version: int) -> ProjectRecord:
        self._assert_editable_draft(project_id)
        brief = self.store.get_brief_version(project_id, version)
        return self.store.save_draft_brief(
            project_id, brief, source="restore", feedback=f"恢复 v{version}"
        )

    def list_versions(self, project_id: str) -> list[dict[str, Any]]:
        return self.store.list_brief_versions(project_id)

    def _assert_editable_draft(self, project_id: str) -> ProjectRecord:
        project = self.store.get_project(project_id)
        if project.status != ProjectStatus.DRAFT or project.confirmed:
            raise ValueError("创作方案已确认，不能再按草稿方式修改")
        if self.store.list_chapters(project_id):
            raise ValueError("项目已经生成章节，不能再按草稿方式修改")
        return project

    @staticmethod
    def brief_fields(sections: list[str]) -> list[str]:
        groups = {
            "title": ["title_candidates", "selected_title"],
            "story": [
                "synopsis",
                "target_readers",
                "selling_points",
                "main_conflict",
                "reader_contract",
                "core_expectation",
            ],
            "protagonist": [
                "protagonist",
                "protagonist_name",
                "protagonist_profile",
                "character_profiles",
            ],
            "world": ["world_rules"],
            "opening": ["opening_three_chapters", "opening_chapter_anchors"],
            "style": ["style_guide"],
            "serialization": ["total_chapters", "volume_count", "update_plan"],
        }
        return list(
            dict.fromkeys(field for section in sections for field in groups[section])
        )

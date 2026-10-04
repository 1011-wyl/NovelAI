from __future__ import annotations

from typing import Protocol

from novel_agent.models import (
    AssistantGatewayResponse,
    AssistantMode,
    ChapterPlan,
    ChapterPlanBatch,
    ChapterPlanSelection,
    ChapterRecord,
    ChapterRevisionAnalysis,
    ChapterSelection,
    CharacterMemoryBatch,
    CharacterRecord,
    ContinuityContext,
    CreativeBrief,
    NovelCreateRequest,
    OpeningChapterAnchor,
    ProjectRecord,
    ReadabilityContext,
    ReviewReport,
    WorldFactRecord,
)
from novel_agent.features.chapter_review.revision_context import ChapterRevisionContext


class LLMGateway(Protocol):
    name: str

    def create_brief(self, request: NovelCreateRequest) -> CreativeBrief: ...

    def revise_brief(
        self,
        request: NovelCreateRequest,
        current: CreativeBrief,
        feedback: str,
        fields: list[str],
    ) -> CreativeBrief: ...

    def plan_chapter(
        self,
        request: NovelCreateRequest,
        brief: CreativeBrief,
        chapter_number: int,
        recent_summaries: list[str],
        open_threads: list[str],
        character_roster: list[CharacterRecord] | None = None,
        writing_guidance: dict[str, str] | None = None,
        compact_characters: list[str] | None = None,
        compact_world_facts: list[str] | None = None,
        compact_timeline: list[str] | None = None,
        previous_chapter_excerpt: str = "",
        opening_anchor: OpeningChapterAnchor | None = None,
    ) -> ChapterPlan: ...

    def plan_chapter_candidates(
        self,
        request: NovelCreateRequest,
        brief: CreativeBrief,
        chapter_number: int,
        recent_summaries: list[str],
        open_threads: list[str],
        character_roster: list[CharacterRecord] | None = None,
        writing_guidance: dict[str, str] | None = None,
        compact_characters: list[str] | None = None,
        compact_world_facts: list[str] | None = None,
        compact_timeline: list[str] | None = None,
        previous_chapter_excerpt: str = "",
        opening_anchor: OpeningChapterAnchor | None = None,
    ) -> ChapterPlanBatch: ...

    def select_chapter_plan(
        self,
        candidates: list[ChapterPlan],
        previous_chapter_excerpt: str = "",
    ) -> ChapterPlanSelection: ...

    def write_chapter(
        self,
        request: NovelCreateRequest,
        brief: CreativeBrief,
        plan: ChapterPlan,
        protagonist_name: str,
        research_notes: list[str],
        character_roster: list[CharacterRecord] | None = None,
        genre_prose_card: str = "",
        compact_characters: list[str] | None = None,
        previous_chapter_excerpt: str = "",
        opening_anchor: OpeningChapterAnchor | None = None,
        quality_contract: dict | None = None,
    ) -> str: ...

    def repair_chapter_plan(
        self,
        plan: ChapterPlan,
        issues: list[str],
        opening_anchor: OpeningChapterAnchor | None,
        chapter_number: int,
        brief: CreativeBrief,
    ) -> ChapterPlan: ...

    def deslop_chapter(
        self,
        content: str,
        plan: ChapterPlan,
        genre_prose_card: str,
        skill_instructions: str,
    ) -> str: ...

    def revise_chapter(self, context: ChapterRevisionContext) -> str: ...

    def extract_character_memories(
        self,
        brief: CreativeBrief,
        chapter_number: int,
        content: str,
        character_roster: list[CharacterRecord] | None = None,
    ) -> CharacterMemoryBatch: ...

    def review_continuity(
        self,
        context: ContinuityContext,
        skill_instructions: str,
    ) -> ReviewReport: ...

    def review_readability(self, context: ReadabilityContext) -> ReviewReport: ...

    def respond_to_chapter_assistant(
        self,
        *,
        mode: AssistantMode,
        user_message: str,
        selection: ChapterSelection | None,
        project: ProjectRecord,
        chapter: ChapterRecord,
        working_title: str,
        working_content: str,
        recent_summaries: list[str],
        characters: list[CharacterRecord],
        world_facts: list[WorldFactRecord],
        timeline: list[dict[str, object]],
    ) -> AssistantGatewayResponse: ...

    def analyze_chapter_revision(
        self,
        *,
        project: ProjectRecord,
        chapter: ChapterRecord,
        title: str,
        content: str,
        characters: list[CharacterRecord],
    ) -> ChapterRevisionAnalysis: ...

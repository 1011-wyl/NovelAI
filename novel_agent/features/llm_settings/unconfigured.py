from __future__ import annotations

from dataclasses import dataclass

from novel_agent.integrations.errors import APIConfigurationRequired
from novel_agent.models import (
    AssistantGatewayResponse,
    ChapterPlan,
    ChapterPlanBatch,
    ChapterPlanSelection,
    ChapterRevisionAnalysis,
    CharacterMemoryBatch,
    CreativeBrief,
    NovelCreateRequest,
    ReviewReport,
)


@dataclass(slots=True)
class UnconfiguredLLMGateway:
    name: str = "unconfigured"
    message: str = "尚未配置大模型服务"

    def _blocked(self) -> None:
        raise APIConfigurationRequired(self.message)

    def create_brief(self, request: NovelCreateRequest) -> CreativeBrief:
        self._blocked()

    def revise_brief(self, *args: object, **kwargs: object) -> CreativeBrief:
        self._blocked()

    def plan_chapter(self, *args: object, **kwargs: object) -> ChapterPlan:
        self._blocked()

    def plan_chapter_candidates(self, *args: object, **kwargs: object) -> ChapterPlanBatch:
        self._blocked()

    def select_chapter_plan(self, *args: object, **kwargs: object) -> ChapterPlanSelection:
        self._blocked()

    def write_chapter(self, *args: object, **kwargs: object) -> str:
        self._blocked()

    def repair_chapter_plan(self, *args: object, **kwargs: object) -> ChapterPlan:
        self._blocked()

    def deslop_chapter(self, *args: object, **kwargs: object) -> str:
        self._blocked()

    def revise_chapter(self, *args: object, **kwargs: object) -> str:
        self._blocked()

    def extract_character_memories(self, *args: object, **kwargs: object) -> CharacterMemoryBatch:
        self._blocked()

    def review_continuity(self, *args: object, **kwargs: object) -> ReviewReport:
        self._blocked()

    def review_readability(self, *args: object, **kwargs: object) -> ReviewReport:
        self._blocked()

    def respond_to_chapter_assistant(self, *args: object, **kwargs: object) -> AssistantGatewayResponse:
        self._blocked()

    def analyze_chapter_revision(self, *args: object, **kwargs: object) -> ChapterRevisionAnalysis:
        self._blocked()

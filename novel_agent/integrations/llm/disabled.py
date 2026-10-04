from __future__ import annotations

from dataclasses import dataclass

from novel_agent.integrations.errors import APIConfigurationRequired
from novel_agent.models import (
    AssistantGatewayResponse,
    ChapterPlan,
    ChapterPlanBatch,
    ChapterPlanSelection,
    CharacterMemoryBatch,
    ChapterRevisionAnalysis,
    CreativeBrief,
    NovelCreateRequest,
    ReviewReport,
)


@dataclass(slots=True)
class DisabledRemoteGateway:
    """Deliberate safety gate: it never sends content to a third party."""

    provider: str
    name: str = "remote-disabled-until-implemented"

    def _blocked(self) -> None:
        raise APIConfigurationRequired(
            f"已选择远程模型 {self.provider!r}，但远程适配器仍处于受控状态。"
            "请先完成 novel_agent/adapters_remote.py 中的供应商实现与密钥配置。"
        )

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

    def repair_chapter_plan(self, *args: object, **kwargs: object) -> ChapterPlan:
        self._blocked()

    def revise_chapter(self, *args: object, **kwargs: object) -> str:
        self._blocked()

    def deslop_chapter(self, *args: object, **kwargs: object) -> str:
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

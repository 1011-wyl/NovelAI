from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import Field

from novel_agent.features.story_design.models import OpeningChapterAnchor, StrictModel


class ReworkMode(StrEnum):
    AUTO = "auto"
    REUSE_PLAN = "reuse_plan"
    REPLAN = "replan"


class PlanningContext(StrictModel):
    chapter_number: int
    recent_summaries: list[str] = Field(default_factory=list)
    timeline: list[dict[str, Any]] = Field(default_factory=list)
    open_threads: list[str] = Field(default_factory=list)
    previous_chapter_excerpt: str = ""
    opening_anchor: OpeningChapterAnchor | None = None

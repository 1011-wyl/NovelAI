from __future__ import annotations

from typing import Any

from pydantic import Field

from novel_agent.features.story_design.models import OpeningChapterAnchor, StrictModel


class OpeningRepairPreview(StrictModel):
    eligible: bool
    reasons: list[str] = Field(default_factory=list)
    project_updated_at: str = ""
    detected_problems: list[str] = Field(default_factory=list)
    opening_anchor: dict[str, Any] = Field(default_factory=dict)
    character_changes: list[dict[str, Any]] = Field(default_factory=list)
    chapter_changes: list[dict[str, Any]] = Field(default_factory=list)
    preserved_artifacts: list[str] = Field(default_factory=list)


class OpeningRepairApplyRequest(StrictModel):
    confirm: bool = False
    expected_project_updated_at: str = ""


class OpeningRepairApplyResult(StrictModel):
    snapshot_id: str
    next_action: str
    preview: OpeningRepairPreview

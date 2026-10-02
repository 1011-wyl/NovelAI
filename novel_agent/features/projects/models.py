"""Project lifecycle domain models."""

from __future__ import annotations

from enum import StrEnum

from novel_agent.features.story_design.models import (
    CreativeBrief,
    NovelCreateRequest,
    StrictModel,
)


class ProjectStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    ARCHIVED = "ARCHIVED"
    HUMAN_REQUIRED = "HUMAN_REQUIRED"


class ProjectRecord(StrictModel):
    id: str
    title: str
    status: ProjectStatus
    request: NovelCreateRequest
    brief: CreativeBrief
    confirmed: bool
    current_chapter: int
    created_at: str
    updated_at: str

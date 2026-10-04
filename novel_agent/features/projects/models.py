"""Project lifecycle domain models."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import Field, field_validator

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


class ProjectSummary(StrictModel):
    """Bookshelf list row — no request/brief payload."""

    id: str
    title: str
    status: ProjectStatus
    confirmed: bool
    audience_channel: str
    genre: str
    chapter_count: int = Field(ge=0)
    content_chars: int = Field(ge=0)
    current_chapter: int = Field(ge=0)
    created_at: str
    updated_at: str


class ProjectMetadataUpdate(StrictModel):
    title: str = Field(min_length=1, max_length=80)

    @field_validator("title", mode="before")
    @classmethod
    def strip_title(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value

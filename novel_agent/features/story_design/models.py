"""Story-design domain models (create request, brief, character profiles)."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NovelCreateRequest(StrictModel):
    preferred_title: str | None = Field(default=None, max_length=80)
    audience_channel: str = "男频"
    genre: str = Field(min_length=1, max_length=40)
    experiences: list[str] = Field(default_factory=list, max_length=8)
    elements: list[str] = Field(default_factory=list, max_length=12)
    protagonist_tags: list[str] = Field(default_factory=list, max_length=8)
    romance: str | None = Field(default=None, max_length=40)
    idea: str = Field(min_length=1, max_length=2000)
    must_have: list[str] = Field(default_factory=list, max_length=20)
    nice_to_have: list[str] = Field(default_factory=list, max_length=20)
    exclude: list[str] = Field(default_factory=list, max_length=20)
    chapter_target_chars: int = Field(default=2200, ge=800, le=8000)
    daily_chapters: int = Field(default=2, ge=1, le=20)
    reserve_target: int = Field(default=5, ge=1, le=50)
    require_plan_confirmation: bool = True

    @field_validator("genre", "idea", "preferred_title", mode="before")
    @classmethod
    def strip_required(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value

    @field_validator("audience_channel")
    @classmethod
    def validate_audience_channel(cls, value: str) -> str:
        if value not in {"男频", "女频"}:
            raise ValueError("频道只能选择男频或女频")
        return value


class BriefRegenerateRequest(StrictModel):
    feedback: str = Field(default="", max_length=2000)
    sections: list[str] = Field(default_factory=list, max_length=8)

    @field_validator("feedback", mode="before")
    @classmethod
    def strip_feedback(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value

    @field_validator("sections")
    @classmethod
    def validate_sections(cls, value: list[str]) -> list[str]:
        allowed = {
            "title",
            "story",
            "protagonist",
            "world",
            "opening",
            "style",
            "serialization",
        }
        invalid = sorted(set(value) - allowed)
        if invalid:
            raise ValueError(f"不支持的方案模块：{'、'.join(invalid)}")
        return list(dict.fromkeys(value))


class CharacterProfile(StrictModel):
    name: str = Field(min_length=1, max_length=20)
    role: str = Field(default="supporting", max_length=30)
    importance: Literal["core", "major"] = "major"
    profile: str = Field(default="", max_length=1000)
    personality: list[str] = Field(default_factory=list, max_length=8)
    core_goal: str = Field(default="", max_length=500)
    relationships: dict[str, str] = Field(default_factory=dict)
    stable_facts: list[str] = Field(default_factory=list, max_length=20)
    initial_state: str = Field(default="", max_length=1000)
    initial_goal: str = Field(default="", max_length=500)
    initial_relationships: dict[str, str] = Field(default_factory=dict)
    future_arc: str = Field(default="", max_length=1500)
    future_relationships: dict[str, str] = Field(default_factory=dict)
    first_appearance_chapter: int | None = Field(default=None, ge=1)

    @field_validator("name", "role", "profile", "core_goal", "initial_state", "initial_goal", "future_arc", mode="before")
    @classmethod
    def strip_character_text(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value


class OpeningChapterAnchor(StrictModel):
    number: Literal[1, 2, 3]
    title: str = Field(default="", max_length=80)
    core_event: str = Field(min_length=1, max_length=800)
    must_establish: list[str] = Field(default_factory=list, max_length=12)
    forbidden_assumptions: list[str] = Field(default_factory=list, max_length=12)
    ending_direction: str = Field(default="", max_length=500)

    @field_validator("title", "core_event", "ending_direction", mode="before")
    @classmethod
    def strip_anchor_text(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value


class CreativeBrief(StrictModel):
    title_candidates: list[str]
    selected_title: str
    synopsis: str
    target_readers: str
    selling_points: list[str]
    protagonist: str
    protagonist_name: str = ""
    protagonist_profile: str = ""
    character_profiles: list[CharacterProfile] = Field(default_factory=list, max_length=20)
    main_conflict: str
    world_rules: list[str]
    total_chapters: int
    volume_count: int
    opening_three_chapters: list[str] = Field(default_factory=list)
    opening_chapter_anchors: list[OpeningChapterAnchor] = Field(default_factory=list, max_length=3)
    update_plan: str
    style_guide: list[str]
    reader_contract: str = ""
    core_expectation: str = ""

    @model_validator(mode="after")
    def normalize_opening_anchors(self) -> "CreativeBrief":
        """Keep one structured source of truth; old string lists stay a derived projection."""
        if self.opening_chapter_anchors:
            ordered = sorted(self.opening_chapter_anchors, key=lambda item: item.number)
            self.opening_chapter_anchors = ordered
            derived: list[str] = []
            for anchor in ordered:
                title = anchor.title.strip()
                derived.append(
                    f"{title}：{anchor.core_event}" if title else anchor.core_event
                )
            self.opening_three_chapters = derived
            return self
        converted: list[OpeningChapterAnchor] = []
        for index, text in enumerate(self.opening_three_chapters[:3], start=1):
            event = str(text or "").strip()
            if not event:
                continue
            converted.append(
                OpeningChapterAnchor(
                    number=index,  # type: ignore[arg-type]
                    title="",
                    core_event=event,
                )
            )
        self.opening_chapter_anchors = converted
        return self

    @model_validator(mode="after")
    def normalize_protagonist(self) -> "CreativeBrief":
        """Keep legacy briefs compatible while separating a name from a biography."""
        raw = (self.protagonist_profile or self.protagonist or "").strip()
        candidate = (self.protagonist_name or self.protagonist or "").strip()
        candidate = re.sub(r"^主角(?:姓名)?\s*[：:]?\s*", "", candidate)
        name = re.split(r"[，,：:；;（(\n]", candidate, maxsplit=1)[0].strip()
        if not name:
            raise ValueError("创作方案缺少主角姓名")
        if len(name) > 20:
            raise ValueError("主角姓名过长，请把人物介绍放入 protagonist_profile")
        self.protagonist_name = name
        self.protagonist_profile = raw if raw != name else self.protagonist_profile.strip()
        # `protagonist` remains the compatibility field used by older clients.
        self.protagonist = name
        profiles: list[CharacterProfile] = []
        seen: set[str] = set()
        for profile in self.character_profiles:
            if profile.name in seen:
                continue
            seen.add(profile.name)
            if profile.name == name:
                profile = profile.model_copy(
                    update={
                        "role": "protagonist",
                        "importance": "core",
                        "profile": profile.profile or self.protagonist_profile,
                        "core_goal": profile.core_goal or self.main_conflict,
                    }
                )
            elif profile.role == "protagonist":
                profile = profile.model_copy(update={"role": "supporting"})
            profiles.append(profile)
        if name not in seen:
            profiles.insert(
                0,
                CharacterProfile(
                    name=name,
                    role="protagonist",
                    importance="core",
                    profile=self.protagonist_profile,
                    core_goal=self.main_conflict,
                ),
            )
        self.character_profiles = profiles
        return self

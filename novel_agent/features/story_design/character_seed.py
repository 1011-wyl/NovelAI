"""Shared chapter-0 character seed rules used by create and confirm sync."""

from __future__ import annotations

from typing import Any

from novel_agent.features.story_design.models import (
    CharacterProfile,
    CreativeBrief,
    NovelCreateRequest,
)


def chapter_zero_immutable_facts(
    profile: CharacterProfile,
    request: NovelCreateRequest,
    brief: CreativeBrief,
) -> list[str]:
    is_protagonist = profile.name == brief.protagonist_name
    facts: list[str] = []
    if is_protagonist:
        facts.append(f"主角姓名为{profile.name}")
    facts.extend(f"稳定事实：{item}" for item in profile.stable_facts if str(item).strip())
    if profile.personality:
        facts.append(f"性格特征：{'、'.join(profile.personality)}")
    if is_protagonist:
        facts.append(f"故事起点属于{request.genre}")
        facts.append("没有未经故事建立的无限资源或全知能力")
    return facts


def chapter_zero_current_state(
    profile: CharacterProfile,
    brief: CreativeBrief,
) -> dict[str, Any]:
    is_protagonist = profile.name == brief.protagonist_name
    goal = profile.initial_goal.strip()
    if not goal and is_protagonist:
        goal = (brief.core_expectation or brief.main_conflict or "").strip()
    return {
        "chapter": 0,
        "importance": "core" if is_protagonist else profile.importance,
        "goal": goal,
        "knowledge": [],
        "relationships": dict(profile.initial_relationships),
        "initial_state": profile.initial_state,
    }


def seed_payloads_from_brief(
    request: NovelCreateRequest,
    brief: CreativeBrief,
) -> list[tuple[CharacterProfile, list[str], dict[str, Any]]]:
    payloads: list[tuple[CharacterProfile, list[str], dict[str, Any]]] = []
    for profile in brief.character_profiles:
        payloads.append(
            (
                profile,
                chapter_zero_immutable_facts(profile, request, brief),
                chapter_zero_current_state(profile, brief),
            )
        )
    return payloads

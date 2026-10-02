"""Build initial character seed records from a creative brief."""

from __future__ import annotations

from novel_agent.features.story_design.models import CreativeBrief, NovelCreateRequest
from novel_agent.models import CharacterRecord, new_id


def build_character_records(
    project_id: str,
    request: NovelCreateRequest,
    brief: CreativeBrief,
) -> list[CharacterRecord]:
    records: list[CharacterRecord] = []
    for profile in brief.character_profiles:
        is_protagonist = profile.name == brief.protagonist_name
        immutable_facts = [
            *([f"人物背景：{profile.profile}"] if profile.profile else []),
            *([f"性格特征：{'、'.join(profile.personality)}"] if profile.personality else []),
        ]
        if is_protagonist:
            immutable_facts = [
                f"主角姓名为{profile.name}",
                *immutable_facts,
                f"故事起点属于{request.genre}",
                "没有未经故事建立的无限资源或全知能力",
            ]
        records.append(
            CharacterRecord(
                id=new_id("character"),
                project_id=project_id,
                name=profile.name,
                role="protagonist" if is_protagonist else profile.role,
                immutable_facts=immutable_facts,
                current_state={
                    "chapter": 0,
                    "importance": "core" if is_protagonist else profile.importance,
                    "goal": profile.core_goal
                    or (brief.main_conflict if is_protagonist else ""),
                    "knowledge": [],
                    "relationships": profile.relationships,
                },
            )
        )
    return records

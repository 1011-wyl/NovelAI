"""Build initial character seed records from a creative brief."""

from __future__ import annotations

from novel_agent.features.story_design.character_seed import seed_payloads_from_brief
from novel_agent.features.story_design.models import CreativeBrief, NovelCreateRequest
from novel_agent.models import CharacterRecord, new_id


def build_character_records(
    project_id: str,
    request: NovelCreateRequest,
    brief: CreativeBrief,
) -> list[CharacterRecord]:
    records: list[CharacterRecord] = []
    for profile, facts, state in seed_payloads_from_brief(request, brief):
        is_protagonist = profile.name == brief.protagonist_name
        records.append(
            CharacterRecord(
                id=new_id("character"),
                project_id=project_id,
                name=profile.name,
                role="protagonist" if is_protagonist else profile.role,
                immutable_facts=facts,
                current_state=state,
            )
        )
    return records

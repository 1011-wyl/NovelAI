from __future__ import annotations

import json
import unittest
from pathlib import Path

from pydantic import ValidationError

from novel_agent.features.story_design import models as new_models
from novel_agent.models import (
    BriefRegenerateRequest,
    CharacterProfile,
    CreativeBrief,
    NovelCreateRequest,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


class StoryDesignModelsCompatTests(unittest.TestCase):
    def test_model_identities(self) -> None:
        self.assertIs(NovelCreateRequest, new_models.NovelCreateRequest)
        self.assertIs(BriefRegenerateRequest, new_models.BriefRegenerateRequest)
        self.assertIs(CharacterProfile, new_models.CharacterProfile)
        self.assertIs(CreativeBrief, new_models.CreativeBrief)

    def test_json_schemas_match_feature_module(self) -> None:
        for old, new in (
            (NovelCreateRequest, new_models.NovelCreateRequest),
            (BriefRegenerateRequest, new_models.BriefRegenerateRequest),
            (CharacterProfile, new_models.CharacterProfile),
            (CreativeBrief, new_models.CreativeBrief),
        ):
            self.assertEqual(old.model_json_schema(), new.model_json_schema(), old.__name__)

    def test_legacy_protagonist_brief_json_normalizes(self) -> None:
        payload = json.loads(
            (FIXTURES / "legacy_brief_protagonist.json").read_text(encoding="utf-8")
        )
        brief = CreativeBrief.model_validate(payload)
        self.assertEqual(brief.protagonist, "顾宁")
        self.assertEqual(brief.protagonist_name, "顾宁")
        self.assertIn("仓库管理员", brief.protagonist_profile)
        self.assertEqual(brief.character_profiles[0].name, "顾宁")
        self.assertEqual(brief.character_profiles[0].role, "protagonist")
        self.assertEqual(brief.character_profiles[0].importance, "core")

    def test_character_profiles_dedupe_and_correct_roles(self) -> None:
        brief = CreativeBrief.model_validate(
            {
                "title_candidates": ["书名"],
                "selected_title": "书名",
                "synopsis": "简介",
                "target_readers": "读者",
                "selling_points": ["卖点"],
                "protagonist": "方远",
                "protagonist_name": "方远",
                "protagonist_profile": "主角简介",
                "character_profiles": [
                    {
                        "name": "方远",
                        "role": "supporting",
                        "importance": "major",
                        "profile": "",
                        "personality": [],
                        "core_goal": "",
                        "relationships": {},
                    },
                    {
                        "name": "方远",
                        "role": "protagonist",
                        "importance": "core",
                        "profile": "重复档案",
                        "personality": [],
                        "core_goal": "",
                        "relationships": {},
                    },
                    {
                        "name": "沈岚",
                        "role": "protagonist",
                        "importance": "major",
                        "profile": "配角",
                        "personality": [],
                        "core_goal": "目标",
                        "relationships": {},
                    },
                ],
                "main_conflict": "主线冲突",
                "world_rules": ["规则"],
                "total_chapters": 100,
                "volume_count": 3,
                "opening_three_chapters": ["一", "二", "三"],
                "update_plan": "日更",
                "style_guide": ["文风"],
            }
        )
        names = [item.name for item in brief.character_profiles]
        self.assertEqual(names.count("方远"), 1)
        self.assertEqual(brief.character_profiles[0].role, "protagonist")
        supporting = next(item for item in brief.character_profiles if item.name == "沈岚")
        self.assertEqual(supporting.role, "supporting")

    def test_sections_dedupe_and_reject_unknown(self) -> None:
        req = BriefRegenerateRequest(sections=["title", "title", "story"])
        self.assertEqual(req.sections, ["title", "story"])
        with self.assertRaises(ValidationError):
            BriefRegenerateRequest(sections=["title", "unknown"])

    def test_audience_channel_and_strip_validators(self) -> None:
        req = NovelCreateRequest(
            preferred_title="  书名  ",
            audience_channel="男频",
            genre="  末世  ",
            idea="  想法  ",
        )
        self.assertEqual(req.preferred_title, "书名")
        self.assertEqual(req.genre, "末世")
        self.assertEqual(req.idea, "想法")
        with self.assertRaises(ValidationError):
            NovelCreateRequest(audience_channel="全频", genre="末世", idea="想法")

    def test_extra_fields_forbidden(self) -> None:
        with self.assertRaises(ValidationError):
            NovelCreateRequest.model_validate(
                {"genre": "末世", "idea": "想法", "unexpected": 1}
            )

    def test_legacy_brief_without_time_fields_still_loads(self) -> None:
        payload = json.loads(
            (FIXTURES / "legacy_brief_protagonist.json").read_text(encoding="utf-8")
        )
        brief = CreativeBrief.model_validate(payload)
        profile = brief.character_profiles[0]
        self.assertEqual(profile.initial_relationships, {})
        self.assertEqual(profile.future_relationships, {})
        self.assertEqual(profile.stable_facts, [])
        self.assertTrue(brief.opening_chapter_anchors)
        self.assertEqual(brief.opening_chapter_anchors[0].number, 1)

    def test_legacy_relationships_are_not_promoted_to_initial(self) -> None:
        brief = CreativeBrief.model_validate(
            {
                "title_candidates": ["书名"],
                "selected_title": "书名",
                "synopsis": "简介",
                "target_readers": "读者",
                "selling_points": ["卖点"],
                "protagonist": "顾宁",
                "protagonist_name": "顾宁",
                "protagonist_profile": "主角",
                "character_profiles": [
                    {
                        "name": "顾铁山",
                        "role": "supporting",
                        "profile": "旧档案",
                        "personality": [],
                        "core_goal": "",
                        "relationships": {"顾宁": "被救后效忠主角"},
                    }
                ],
                "main_conflict": "冲突",
                "world_rules": ["规则"],
                "total_chapters": 100,
                "volume_count": 1,
                "opening_three_chapters": ["第一章异常征兆", "第二章选择代价", "第三章第一次对抗"],
                "update_plan": "日更",
                "style_guide": ["文风"],
            }
        )
        tie_shan = next(item for item in brief.character_profiles if item.name == "顾铁山")
        self.assertEqual(tie_shan.relationships["顾宁"], "被救后效忠主角")
        self.assertEqual(tie_shan.initial_relationships, {})
        self.assertEqual(brief.opening_chapter_anchors[0].core_event, "第一章异常征兆")


if __name__ == "__main__":
    unittest.main()

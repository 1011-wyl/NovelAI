from __future__ import annotations

import unittest

from novel_agent.features.story_design.requirements import (
    RequirementConflict as NewRequirementConflict,
    validate_requirements as new_validate_requirements,
)
from novel_agent.features.story_design.tags import (
    TAG_CATALOG as NEW_TAG_CATALOG,
    public_tag_catalog as new_public_tag_catalog,
)
from novel_agent.models import NovelCreateRequest
from novel_agent.requirements import RequirementConflict, validate_requirements
from novel_agent.tags import TAG_CATALOG, public_tag_catalog


class StoryDesignRequirementsCompatTests(unittest.TestCase):
    def test_requirements_and_tags_are_identical_objects(self) -> None:
        self.assertIs(RequirementConflict, NewRequirementConflict)
        self.assertIs(validate_requirements, new_validate_requirements)
        self.assertIs(TAG_CATALOG, NEW_TAG_CATALOG)
        self.assertIs(public_tag_catalog, new_public_tag_catalog)

    def test_public_tag_catalog_shape_frozen(self) -> None:
        catalog = public_tag_catalog()
        self.assertEqual(catalog["default_channel"], "男频")
        self.assertEqual(
            catalog["note"],
            "标签经过跨平台归纳，只用于创作方向，不代表平台官方投稿分类。",
        )
        self.assertEqual(
            [item["name"] for item in catalog["references"]],
            ["番茄小说", "起点中文网", "晋江文学城作品库"],
        )
        self.assertIn("都市高武", catalog["channels"]["男频"]["genres"])
        self.assertIn("现言脑洞", catalog["channels"]["女频"]["genres"])
        self.assertEqual(catalog["channels"]["男频"]["romance"][0], "自动推导")
        self.assertNotEqual(
            catalog["channels"]["男频"]["protagonist_tags"],
            catalog["channels"]["女频"]["protagonist_tags"],
        )

    def test_incompatible_rules_and_must_exclude_overlap(self) -> None:
        with self.assertRaises(RequirementConflict) as romance:
            validate_requirements(
                NovelCreateRequest(
                    genre="末世",
                    romance="无感情线",
                    elements=["先婚后爱"],
                    idea="冲突标签",
                )
            )
        self.assertTrue(romance.exception.conflicts)

        with self.assertRaises(RequirementConflict) as overlap:
            validate_requirements(
                NovelCreateRequest(
                    genre="悬疑",
                    idea="调查",
                    must_have=["群像"],
                    exclude=["群像"],
                )
            )
        self.assertIn("群像", overlap.exception.conflicts[0])

    def test_channel_genre_gate(self) -> None:
        valid = NovelCreateRequest(
            audience_channel="女频",
            genre="现言脑洞",
            experiences=["甜宠"],
            elements=["穿书"],
            protagonist_tags=["大女主"],
            idea="女主进入恋爱游戏。",
        )
        validate_requirements(valid)
        with self.assertRaises(RequirementConflict):
            validate_requirements(valid.model_copy(update={"genre": "都市高武"}))


if __name__ == "__main__":
    unittest.main()

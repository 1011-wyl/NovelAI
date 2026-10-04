from __future__ import annotations

import unittest

from novel_agent.features.chapter_review.quality_spec import (
    DEFAULT_QUALITY_CONTRACT,
    READABILITY_DIMENSIONS,
    WRITE_TEMPERATURE,
    build_reviewer_quality_contract,
    build_writer_quality_contract,
)
from novel_agent.features.story_design.models import OpeningChapterAnchor
from novel_agent.integrations.llm.deepseek import DeepSeekLLMGateway


class QualitySpecTests(unittest.TestCase):
    def test_writer_and_reviewer_share_dimensions_and_pass_line(self) -> None:
        writer = build_writer_quality_contract(
            chapter_number=1,
            target_chars=3000,
            opening_anchor=OpeningChapterAnchor(
                number=1,
                title="异常征兆",
                core_event="神纹异常出现",
                must_establish=["主角发现异常"],
                forbidden_assumptions=["已经效忠"],
            ),
            exclude=["过度血腥"],
        )
        reviewer = build_reviewer_quality_contract(
            chapter_number=1,
            target_chars=3000,
            opening_anchor=OpeningChapterAnchor(
                number=1,
                title="异常征兆",
                core_event="神纹异常出现",
                must_establish=["主角发现异常"],
                forbidden_assumptions=["已经效忠"],
            ),
            exclude=["过度血腥"],
        )
        self.assertEqual(
            [item["name"] for item in writer["dimensions"]],
            list(READABILITY_DIMENSIONS),
        )
        self.assertEqual(writer["pass_score_exclusive"], reviewer["pass_score_exclusive"])
        self.assertEqual(
            writer["pass_score_exclusive"],
            DEFAULT_QUALITY_CONTRACT.pass_score_exclusive,
        )
        self.assertEqual(writer["desired_generation_score"], 85.0)
        self.assertEqual(writer["accepted_length_min"], 2500)
        self.assertEqual(writer["accepted_length_max"], 3500)
        self.assertEqual(writer["length_tolerance_chars"], 500)
        self.assertNotIn("dimension_min_score", writer)
        self.assertNotIn("average_min_score", writer)
        self.assertIn("主角发现异常", writer["must_establish"])
        self.assertIn("已经效忠", writer["forbidden_assumptions"])
        self.assertIn("不得作为第二套通过条件", reviewer["decision_rule"])

    def test_chapter_two_contract_requires_previous_continuity(self) -> None:
        contract = build_writer_quality_contract(
            chapter_number=2,
            target_chars=1200,
            previous_chapter_excerpt="门后的敲击忽然停了。",
        )
        self.assertTrue(contract["has_previous_chapter"])
        self.assertTrue(
            any("承接上一章" in rule or "直接承接" in rule for rule in contract["hard_rules"])
        )

    def test_write_temperature_is_stable_default(self) -> None:
        self.assertEqual(WRITE_TEMPERATURE, 0.72)
        self.assertEqual(DeepSeekLLMGateway.__module__, "novel_agent.integrations.llm.deepseek")


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from novel_agent.features.chapter_review.quality_spec import (
    classify_length,
    count_quality_chars,
    length_bounds,
)
from novel_agent.features.chapter_review.recovery import merge_length_repair
from novel_agent.integrations.llm.offline import OfflineLLMGateway
from novel_agent.integrations.search.disabled import DisabledSearchAdapter
from novel_agent.models import ChapterStatus, NovelCreateRequest, ReviewDecision
from novel_agent.repository import SQLiteRepository
from novel_agent.service import NovelAgentService
from novel_agent.story_skills import StorySkillsRuntime
from novel_agent.writing_skills import OhStoryWritingRuntime


class ShortDraftGateway(OfflineLLMGateway):
    def write_chapter(self, *args, **kwargs) -> str:
        return "第1章 短稿\n\n" + ("缺口" * 400)

    def revise_chapter(self, context) -> str:
        if context.quality_contract.get("length_repair"):
            return context.current_draft + ("补写" * 500)
        return super().revise_chapter(context)


class NonExpandingDraftGateway(ShortDraftGateway):
    def revise_chapter(self, context) -> str:
        if context.quality_contract.get("length_repair"):
            return context.current_draft
        return super().revise_chapter(context)


class LengthLoopTests(unittest.TestCase):
    def test_fragment_length_repair_preserves_original_and_ending_hook(self) -> None:
        original = "第1章 异常\n\n林川打开仓门。\n\n门外突然传来三声敲击。"
        fragment = "他压住门把手，先查看监控中的异常光点。"

        merged = merge_length_repair(original, fragment)

        self.assertEqual(merged.count("第1章 异常"), 1)
        self.assertIn(fragment, merged)
        self.assertTrue(merged.endswith("门外突然传来三声敲击。"))
        self.assertGreater(count_quality_chars(merged), count_quality_chars(original))

    def test_full_length_repair_response_cannot_shrink_draft(self) -> None:
        original = "第1章\n\n" + ("原文" * 200)
        shorter_rewrite = "第1章\n\n" + ("原文" * 20)
        self.assertEqual(merge_length_repair(original, shorter_rewrite), original)

    def test_3000_bounds(self) -> None:
        bounds = length_bounds(3000)
        self.assertEqual(bounds["accepted_length_min"], 2500)
        self.assertEqual(bounds["accepted_length_max"], 3500)
        self.assertEqual(classify_length(2610, 3000), "ok")
        self.assertEqual(classify_length(2099, 3000), "severe_short")
        self.assertEqual(classify_length(2499, 3000), "short")
        self.assertEqual(classify_length(2500, 3000), "ok")
        self.assertEqual(classify_length(3500, 3000), "ok")
        self.assertEqual(classify_length(3501, 3000), "over")

    def test_short_draft_length_repair_does_not_consume_quality_revisions(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        repo = SQLiteRepository(Path(tmp.name) / "len.db")
        gateway = ShortDraftGateway()
        service = NovelAgentService(
            repo,
            gateway,
            DisabledSearchAdapter(),
            max_revision_attempts=0,
            story_skills=StorySkillsRuntime.disabled(),
            writing_skills=OhStoryWritingRuntime.disabled(),
        )
        project = service.create_novel(
            NovelCreateRequest(
                genre="末世",
                experiences=["爽文"],
                elements=["囤货"],
                protagonist_tags=["普通人成长"],
                idea="字数补写闭环。",
                require_plan_confirmation=False,
                chapter_target_chars=3000,
            )
        )
        result = service.generate_next_chapter(project.id)
        self.assertGreaterEqual(result.review.length_repair_count, 1)
        self.assertEqual(result.review.revision_count, 0)
        if result.chapter.status == ChapterStatus.READY:
            self.assertEqual(result.review.decision, ReviewDecision.PASS)
            self.assertNotEqual(result.review.quality_status, "QUALITY_NEEDS_ATTENTION")
        else:
            self.assertEqual(result.review.quality_status, "LENGTH_NEEDS_ATTENTION")
        self.assertGreaterEqual(count_quality_chars(result.chapter.content), 800)

    def test_exhausted_length_repair_is_unreviewed_not_zero_score(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        repo = SQLiteRepository(Path(tmp.name) / "length-exhausted.db")
        service = NovelAgentService(
            repo,
            NonExpandingDraftGateway(),
            DisabledSearchAdapter(),
            max_revision_attempts=0,
            story_skills=StorySkillsRuntime.disabled(),
            writing_skills=OhStoryWritingRuntime.disabled(),
        )
        project = service.create_novel(
            NovelCreateRequest(
                genre="末世",
                experiences=["爽文"],
                elements=["囤货"],
                protagonist_tags=["普通人成长"],
                idea="字数补写失败不应伪装成零分审核。",
                require_plan_confirmation=False,
                chapter_target_chars=3000,
            )
        )

        result = service.generate_next_chapter(project.id)

        self.assertEqual(result.chapter.status, ChapterStatus.FAILED)
        self.assertEqual(result.review.quality_status, "LENGTH_NEEDS_ATTENTION")
        self.assertTrue(result.review.preflight_only)
        self.assertEqual(result.review.review_attempt, 0)
        self.assertEqual(result.review.score_trace, [])
        self.assertIsNone(result.review.selected_score)
        diagnostics = repo.list_chapter_failure_diagnostics(project.id)
        self.assertEqual(len(diagnostics), 1)
        self.assertIsNone(diagnostics[0]["score"])
        self.assertIsNone(diagnostics[0]["selected_score"])
        self.assertTrue(diagnostics[0]["preflight_only"])


if __name__ == "__main__":
    unittest.main()

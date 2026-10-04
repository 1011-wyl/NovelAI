from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from novel_agent.features.chapter_review.quality_gate import readability_context
from novel_agent.features.chapter_review.quality_spec import (
    READABILITY_DIMENSIONS,
    build_writer_quality_contract,
)
from novel_agent.integrations.llm.offline import OfflineLLMGateway
from novel_agent.integrations.search.disabled import DisabledSearchAdapter
from novel_agent.models import ChapterStatus, NovelCreateRequest, ReviewDecision, ReviewReport
from novel_agent.repository import SQLiteRepository
from novel_agent.service import NovelAgentService
from novel_agent.story_skills import StorySkillsRuntime
from novel_agent.writing_skills import OhStoryWritingRuntime


class ChapterOneContractTests(unittest.TestCase):
    def test_chapter_one_contract_has_opening_requirements_not_previous_chapter(self) -> None:
        contract = build_writer_quality_contract(
            chapter_number=1,
            target_chars=3000,
            previous_chapter_excerpt="这不该被当成上一章。",
        )
        self.assertTrue(contract["is_chapter_one"])
        self.assertFalse(contract["has_previous_chapter"])
        blob = "\n".join(contract["hard_rules"])
        self.assertIn("主角基本定位", blob)
        self.assertIn("禁止检查或要求承接不存在的前文", blob)
        self.assertNotIn("直接承接上一章", blob)

    def test_chapter_one_readability_context_drops_previous_excerpt(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        repo = SQLiteRepository(Path(tmp.name) / "ch1.db")
        service = NovelAgentService(
            repo,
            OfflineLLMGateway(),
            DisabledSearchAdapter(),
            story_skills=StorySkillsRuntime.disabled(),
            writing_skills=OhStoryWritingRuntime.disabled(),
            max_revision_attempts=0,
        )
        project = service.create_novel(
            NovelCreateRequest(
                genre="末世",
                experiences=["爽文"],
                elements=["囤货"],
                protagonist_tags=["普通人成长"],
                idea="第一章不得检查上一章。",
                require_plan_confirmation=False,
            )
        )
        result = service.generate_next_chapter(project.id)
        self.assertEqual(result.chapter.status, ChapterStatus.READY)
        assert result.chapter.plan is not None
        ctx = readability_context(
            project,
            result.chapter.plan,
            result.chapter.content or "正文",
            "承接上一章的幽灵摘录",
        )
        self.assertEqual(ctx.previous_chapter_excerpt, "")
        self.assertEqual(result.review.decision, ReviewDecision.PASS)
        self.assertFalse(
            any("任务档案" in issue.message or "上一章" in issue.message for issue in result.review.issues)
        )


class FakeContinuityGateway(OfflineLLMGateway):
    def review_readability(self, context):
        excerpt = context.previous_chapter_excerpt or ""
        issues = []
        if excerpt:
            from novel_agent.models import IssueSeverity, ReviewIssue

            issues.append(
                ReviewIssue(
                    category="continuity",
                    severity=IssueSeverity.MAJOR,
                    message="违反不存在的前文章节档案",
                    suggestion="删除",
                    evidence=[excerpt[:20]],
                )
            )
        return ReviewReport(
            decision=ReviewDecision.PASS,
            score=80,
            checks={key: 80.0 for key in READABILITY_DIMENSIONS},
            issues=issues,
        )


class ChapterOneNoFalseContinuityTests(unittest.TestCase):
    def test_chapter_one_does_not_run_previous_continuity_payload(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        repo = SQLiteRepository(Path(tmp.name) / "ch1b.db")
        service = NovelAgentService(
            repo,
            FakeContinuityGateway(),
            DisabledSearchAdapter(),
            story_skills=StorySkillsRuntime.disabled(),
            writing_skills=OhStoryWritingRuntime.disabled(),
            max_revision_attempts=0,
        )
        project = service.create_novel(
            NovelCreateRequest(
                genre="末世",
                experiences=["爽文"],
                elements=["囤货"],
                protagonist_tags=["普通人成长"],
                idea="第一章误报回归。",
                require_plan_confirmation=False,
            )
        )
        result = service.generate_next_chapter(project.id)
        self.assertEqual(result.chapter.status, ChapterStatus.READY)
        self.assertFalse(
            any("前文章节档案" in issue.message for issue in result.review.issues)
        )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from novel_agent.features.chapter_review.candidates import ChapterCandidate, choose_best
from novel_agent.features.chapter_review.quality_spec import READABILITY_DIMENSIONS
from novel_agent.integrations.llm.offline import OfflineLLMGateway
from novel_agent.integrations.search.disabled import DisabledSearchAdapter
from novel_agent.models import (
    ChapterStatus,
    IssueSeverity,
    NovelCreateRequest,
    ReviewDecision,
    ReviewIssue,
    ReviewReport,
)
from novel_agent.repository import SQLiteRepository
from novel_agent.service import NovelAgentService
from novel_agent.story_skills import StorySkillsRuntime
from novel_agent.writing_skills import OhStoryWritingRuntime


class ChooseBestTests(unittest.TestCase):
    def test_91_61_77_keeps_91(self) -> None:
        first = ChapterCandidate(content="A" * 2800, quality_score=91.0, source="initial", attempt_index=1)
        second = ChapterCandidate(content="B" * 2800, quality_score=61.0, source="revision_1", attempt_index=2)
        third = ChapterCandidate(content="C" * 2800, quality_score=77.0, source="revision_2", attempt_index=3)
        best = choose_best(first, second, target_chars=3000)
        best = choose_best(best, third, target_chars=3000)
        self.assertEqual(best.quality_score, 91.0)
        self.assertEqual(best.attempt_index, 1)
        self.assertTrue(best.content.startswith("A"))

    def test_tie_prefers_in_range_length(self) -> None:
        short = ChapterCandidate(content="短" * 2000, quality_score=70.0, attempt_index=1)
        ok = ChapterCandidate(content="长" * 3000, quality_score=70.0, attempt_index=2)
        best = choose_best(short, ok, target_chars=3000)
        self.assertEqual(best.attempt_index, 2)


class SequenceGateway(OfflineLLMGateway):
    def __init__(self, scores: list[float]) -> None:
        self.scores = list(scores)
        self.revise_calls = 0

    def review_readability(self, context):
        score = self.scores.pop(0) if self.scores else 90.0
        return ReviewReport(
            decision=ReviewDecision.REVISE,
            score=score,
            issues=[
                ReviewIssue(
                    category="readability.opening_hook",
                    severity=IssueSeverity.MAJOR,
                    message=f"candidate-score={score:.1f}",
                    suggestion="定向改善开篇",
                    evidence=[f"score={score:.1f}"],
                )
            ],
            checks={key: score for key in READABILITY_DIMENSIONS},
        )

    def revise_chapter(self, context) -> str:
        self.revise_calls += 1
        return super().revise_chapter(context) + f"\n【候选{self.revise_calls}】"


class MonotonicRevisionIntegrationTests(unittest.TestCase):
    def _service(self, gateway, max_revision_attempts: int = 2):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        repo = SQLiteRepository(Path(tmp.name) / "cand.db")
        return NovelAgentService(
            repo,
            gateway,
            DisabledSearchAdapter(),
            max_revision_attempts=max_revision_attempts,
            story_skills=StorySkillsRuntime.disabled(),
            writing_skills=OhStoryWritingRuntime.disabled(),
        ), repo

    def test_first_pass_score_is_kept_without_later_overwrite(self) -> None:
        gateway = SequenceGateway([91.0, 61.0, 77.0])
        service, repo = self._service(gateway)
        project = service.create_novel(
            NovelCreateRequest(
                genre="末世",
                experiences=["爽文"],
                elements=["囤货"],
                protagonist_tags=["普通人成长"],
                idea="首稿 91 分应直接通过。",
                require_plan_confirmation=False,
                chapter_target_chars=800,
            )
        )
        result = service.generate_next_chapter(project.id)
        self.assertEqual(result.chapter.status, ChapterStatus.READY)
        self.assertEqual(result.review.selected_score, 91.0)
        self.assertEqual(result.review.score_trace, [91.0])
        self.assertEqual(gateway.revise_calls, 0)
        chapter = repo.get_chapter_by_number(project.id, 1)
        assert chapter is not None
        self.assertNotIn("【候选", chapter.content or "")

    def test_56_68_selects_68_and_passes(self) -> None:
        gateway = SequenceGateway([56.0, 68.0])
        service, _ = self._service(gateway)
        project = service.create_novel(
            NovelCreateRequest(
                genre="末世",
                experiences=["爽文"],
                elements=["囤货"],
                protagonist_tags=["普通人成长"],
                idea="从 56 升到 68。",
                require_plan_confirmation=False,
                chapter_target_chars=800,
            )
        )
        result = service.generate_next_chapter(project.id)
        self.assertEqual(result.chapter.status, ChapterStatus.READY)
        self.assertEqual(result.review.selected_score, 68.0)

    def test_56_54_59_keeps_59_and_needs_attention(self) -> None:
        gateway = SequenceGateway([56.0, 54.0, 59.0])
        service, repo = self._service(gateway)
        project = service.create_novel(
            NovelCreateRequest(
                genre="末世",
                experiences=["爽文"],
                elements=["囤货"],
                protagonist_tags=["普通人成长"],
                idea="三次均低于通过线。",
                require_plan_confirmation=False,
                chapter_target_chars=800,
            )
        )
        result = service.generate_next_chapter(project.id)
        self.assertEqual(result.chapter.status, ChapterStatus.FAILED)
        self.assertEqual(result.review.selected_score, 59.0)
        self.assertEqual(result.review.quality_status, "QUALITY_NEEDS_ATTENTION")
        chapter = repo.get_chapter_by_number(project.id, 1)
        assert chapter is not None
        latest = repo.get_latest_review_report(chapter.id)
        assert latest is not None
        self.assertEqual(latest.selected_score, 59.0)

    def test_best_content_keeps_its_own_review_report(self) -> None:
        gateway = SequenceGateway([59.0, 54.0, 58.0])
        service, repo = self._service(gateway)
        project = service.create_novel(
            NovelCreateRequest(
                genre="末世",
                experiences=["爽文"],
                elements=["囤货"],
                protagonist_tags=["普通人成长"],
                idea="低分修订不能把自己的审核报告贴到最佳稿上。",
                require_plan_confirmation=False,
                chapter_target_chars=800,
            )
        )
        result = service.generate_next_chapter(project.id)
        self.assertEqual(result.chapter.status, ChapterStatus.FAILED)
        self.assertEqual(result.review.selected_score, 59.0)
        self.assertEqual(result.review.score, 59.0)
        self.assertTrue(
            any(issue.message == "candidate-score=59.0" for issue in result.review.issues)
        )
        self.assertFalse(
            any(issue.message == "candidate-score=58.0" for issue in result.review.issues)
        )
        latest = repo.get_latest_review_report(result.chapter.id)
        assert latest is not None
        self.assertEqual(latest.score, 59.0)
        self.assertTrue(
            any(issue.message == "candidate-score=59.0" for issue in latest.issues)
        )


if __name__ == "__main__":
    unittest.main()

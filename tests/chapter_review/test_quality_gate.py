from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from novel_agent.features.chapter_review.quality_gate import (
    ChapterQualityGate,
    review_structural,
)
from novel_agent.features.chapter_review.quality_spec import READABILITY_DIMENSIONS
from novel_agent.integrations.llm.offline import OfflineLLMGateway
from novel_agent.integrations.search.disabled import DisabledSearchAdapter
from novel_agent.models import (
    ChapterDraftUpdate,
    ChapterRevisionCommitRequest,
    ChapterStatus,
    NovelCreateRequest,
    ReviewDecision,
    ReviewReport,
)
from novel_agent.repository import SQLiteRepository
from novel_agent.service import NovelAgentService
from novel_agent.story_skills import StorySkillsRuntime
from novel_agent.writing_skills import OhStoryWritingRuntime


class LocalHumanHintGateway(OfflineLLMGateway):
    def review_readability(self, context):
        if "【模型误报人工处理】" in (context.current_draft or ""):
            return ReviewReport(
                decision=ReviewDecision.HUMAN_REQUIRED,
                score=77.0,
                checks={name: 77.0 for name in READABILITY_DIMENSIONS},
            )
        return super().review_readability(context)


class SharedQualityGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = SQLiteRepository(Path(self.tmp.name) / "quality.db")
        self.service = NovelAgentService(
            self.repo,
            LocalHumanHintGateway(),
            DisabledSearchAdapter(),
            story_skills=StorySkillsRuntime.disabled(),
            writing_skills=OhStoryWritingRuntime.disabled(),
            max_revision_attempts=0,
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _failed(self, **kwargs) -> str:
        payload = {
            "idea": "__E2E_FAIL_REVIEW__ 神纹仓库管理员抢先机",
            "genre": "末世",
            "require_plan_confirmation": False,
        }
        payload.update(kwargs)
        project = self.service.create_novel(NovelCreateRequest(**payload))
        result = self.service.generate_next_chapter(project.id)
        self.assertEqual(result.chapter.status, ChapterStatus.FAILED)
        return project.id

    def _submit(self, project_id: str, content: str):
        workspace = self.service.get_chapter_workspace(project_id, 1)
        draft = self.service.save_chapter_edit_draft(
            project_id,
            1,
            ChapterDraftUpdate(
                base_version=workspace["chapter"].version,
                title=workspace["chapter"].title,
                content=content,
            ),
        )
        return self.service.submit_failed_chapter_review(
            project_id,
            1,
            ChapterRevisionCommitRequest(
                base_version=workspace["chapter"].version,
                expected_draft_hash=draft.content_hash,
            ),
        )

    def test_short_exclude_and_missing_protagonist_cannot_pass(self) -> None:
        project_id = self._failed(exclude=["禁词XYZ"])
        project = self.repo.get_project(project_id)
        chapter = self.repo.get_chapter_by_number(project_id, 1)
        assert chapter is not None and chapter.plan is not None
        short = review_structural(
            project, chapter.plan, project.brief.protagonist_name, "短文禁词XYZ", False
        )
        self.assertNotEqual(short.decision, ReviewDecision.PASS)
        self.assertTrue(
            any(
                "长度" in issue.message or "排除" in issue.message or "禁词" in issue.message
                for issue in short.issues
            )
        )
        repeated = "\n\n".join(["同一段重复"] * 6)
        originality = review_structural(
            project, chapter.plan, "不存在的主角名", repeated, False
        )
        self.assertTrue(
            any(issue.category in {"repetition", "character"} for issue in originality.issues)
        )
        result = self._submit(project_id, "过短且缺少主角")
        self.assertFalse(result["passed"])
        still = self.repo.get_chapter_by_number(project_id, 1)
        assert still is not None
        self.assertEqual(still.status, ChapterStatus.FAILED)
        self.assertIsNotNone(self.repo.get_chapter_edit_draft(project_id, 1))
        self.assertIsNotNone(result.get("review"))

    def test_blocker_cannot_pass_even_when_average_score_is_high(self) -> None:
        project_id = self._failed(exclude=["禁词XYZ"])
        project = self.repo.get_project(project_id)
        chapter = self.repo.get_chapter_by_number(project_id, 1)
        assert chapter is not None and chapter.plan is not None
        content = (
            f"{project.brief.protagonist_name} {chapter.plan.hook} 禁词XYZ 推进情节。"
            * 300
        )

        report = review_structural(
            project,
            chapter.plan,
            project.brief.protagonist_name,
            content,
            False,
        )

        self.assertGreater(report.score, 60)
        self.assertEqual(report.decision, ReviewDecision.REVISE)
        self.assertTrue(
            any(issue.severity.value == "BLOCKER" for issue in report.issues)
        )

    def test_short_content_cannot_pass_with_other_checks_satisfied(self) -> None:
        project_id = self._failed()
        project = self.repo.get_project(project_id)
        chapter = self.repo.get_chapter_by_number(project_id, 1)
        assert chapter is not None and chapter.plan is not None
        content = f"{project.brief.protagonist_name}发现异常。{chapter.plan.hook}"

        report = review_structural(
            project,
            chapter.plan,
            project.brief.protagonist_name,
            content,
            not chapter.plan.research_questions,
        )

        self.assertEqual(report.decision, ReviewDecision.REVISE)
        self.assertTrue(any("长度" in issue.message for issue in report.issues))

    def test_passing_marker_uses_same_gate_as_workflow(self) -> None:
        project_id = self._failed()
        project = self.repo.get_project(project_id)
        chapter = self.repo.get_chapter_by_number(project_id, 1)
        assert chapter is not None and chapter.plan is not None
        workspace = self.service.get_chapter_workspace(project_id, 1)
        long_pass = (workspace["chapter"].content or "正文") + "【送审修正】"
        gate = ChapterQualityGate(
            self.service.gateway,
            self.service.story_skills,
            self.service.writing_skills,
        )
        report = gate.review(
            repository=self.repo,
            project=project,
            plan=chapter.plan,
            content=long_pass,
            protagonist_name=project.brief.protagonist_name,
            previous_chapter_excerpt="",
            has_research=False,
            characters=self.repo.list_characters(project_id),
        )
        structural = review_structural(
            project, chapter.plan, project.brief.protagonist_name, long_pass, False
        )
        for key, value in structural.checks.items():
            self.assertEqual(report.checks.get(key), value)
        self.assertTrue(any(key.startswith("structural.") for key in report.checks))
        passed = self._submit(project_id, long_pass)
        self.assertTrue(passed["passed"])
        ready = self.repo.get_chapter_by_number(project_id, 1)
        assert ready is not None
        self.assertEqual(ready.status, ChapterStatus.READY)

    def test_manual_resubmit_ignores_model_human_hint_above_pass_line(self) -> None:
        project_id = self._failed()
        workspace = self.service.get_chapter_workspace(project_id, 1)
        content = (workspace["chapter"].content or "正文") + "【模型误报人工处理】"
        result = self._submit(project_id, content)
        self.assertTrue(result["passed"])
        self.assertEqual(result["review"].score, 77.0)
        self.assertEqual(result["review"].decision, ReviewDecision.PASS)
        ready = self.repo.get_chapter_by_number(project_id, 1)
        assert ready is not None
        self.assertEqual(ready.status, ChapterStatus.READY)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from novel_agent.features.chapter_review.issue_policy import can_accept_with_warnings
from novel_agent.features.chapter_review.revision_context import ChapterRevisionContext
from novel_agent.integrations.llm.offline import OfflineLLMGateway
from novel_agent.integrations.search.disabled import DisabledSearchAdapter
from novel_agent.models import (
    ChapterAcceptWithWarningsRequest,
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
from novel_agent.text_normalize import draft_content_hash
from novel_agent.writing_skills import OhStoryWritingRuntime


class RecordingGateway(OfflineLLMGateway):
    def __init__(self) -> None:
        self.revise_calls = 0
        self.plan_calls = 0
        self.write_calls = 0
        self.review_calls = 0
        self.revision_contexts: list[ChapterRevisionContext] = []
        self.memory_calls = 0

    def plan_chapter(self, *args, **kwargs):
        self.plan_calls += 1
        return super().plan_chapter(*args, **kwargs)

    def write_chapter(self, *args, **kwargs):
        self.write_calls += 1
        return super().write_chapter(*args, **kwargs)

    def review_readability(self, context):
        self.review_calls += 1
        return super().review_readability(context)

    def revise_chapter(self, context: ChapterRevisionContext) -> str:
        self.revise_calls += 1
        self.revision_contexts.append(context)
        return super().revise_chapter(context)

    def extract_character_memories(self, *args, **kwargs):
        self.memory_calls += 1
        return super().extract_character_memories(*args, **kwargs)


class AutoRevisionTests(unittest.TestCase):
    def _service(self, gateway: OfflineLLMGateway, max_revision_attempts: int = 2):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        repo = SQLiteRepository(Path(tmp.name) / "auto.db")
        return NovelAgentService(
            repo,
            gateway,
            DisabledSearchAdapter(),
            max_revision_attempts=max_revision_attempts,
            story_skills=StorySkillsRuntime.disabled(),
            writing_skills=OhStoryWritingRuntime.disabled(),
        ), repo

    def _request(self, idea: str) -> NovelCreateRequest:
        return NovelCreateRequest(
            genre="末世",
            experiences=["爽文"],
            elements=["囤货"],
            protagonist_tags=["普通人成长"],
            idea=idea,
            chapter_target_chars=1000,
            require_plan_confirmation=False,
        )

    def test_first_pass_does_not_revise(self) -> None:
        gateway = RecordingGateway()
        service, _ = self._service(gateway)
        project = service.create_novel(self._request("正常生成并通过。"))
        result = service.generate_next_chapter(project.id)
        self.assertEqual(result.chapter.status, ChapterStatus.READY)
        self.assertEqual(gateway.revise_calls, 0)
        self.assertEqual(gateway.review_calls, 1)
        self.assertEqual(gateway.memory_calls, 1)

    def test_one_revision_then_pass(self) -> None:
        gateway = RecordingGateway()
        service, repo = self._service(gateway)
        project = service.create_novel(self._request("__E2E_AUTO_REVISE_ONCE__ 一次修订。"))
        result = service.generate_next_chapter(project.id)
        self.assertEqual(result.chapter.status, ChapterStatus.READY)
        self.assertEqual(gateway.revise_calls, 1)
        self.assertEqual(gateway.review_calls, 2)
        versions = repo.list_chapter_versions(project.id, 1)
        self.assertGreaterEqual(len(versions), 2)
        ctx = gateway.revision_contexts[0]
        self.assertIn("chapter_plan", ctx.model_dump())
        self.assertIn("quality_contract", ctx.model_dump())
        self.assertTrue(ctx.character_archives or ctx.world_rules is not None)

    def test_two_revisions_then_pass(self) -> None:
        gateway = RecordingGateway()
        service, _ = self._service(gateway)
        project = service.create_novel(self._request("__E2E_AUTO_REVISE_TWICE__ 两次修订。"))
        result = service.generate_next_chapter(project.id)
        self.assertEqual(result.chapter.status, ChapterStatus.READY)
        self.assertEqual(gateway.revise_calls, 2)
        self.assertEqual(gateway.review_calls, 3)

    def test_exhaust_keeps_failed_and_all_attempts(self) -> None:
        gateway = RecordingGateway()
        service, repo = self._service(gateway)
        project = service.create_novel(self._request("__E2E_AUTO_REVISE_EXHAUST__ 耗尽。"))
        result = service.generate_next_chapter(project.id)
        self.assertEqual(result.chapter.status, ChapterStatus.FAILED)
        self.assertEqual(gateway.revise_calls, 2)
        self.assertEqual(gateway.review_calls, 3)
        self.assertEqual(gateway.memory_calls, 0)
        versions = repo.list_chapter_versions(project.id, 1)
        reports = []
        with repo.connection() as conn:
            rows = conn.execute(
                "SELECT report_json FROM review_reports WHERE chapter_id=? ORDER BY created_at",
                (result.chapter.id,),
            ).fetchall()
            reports = list(rows)
        self.assertGreaterEqual(len(versions), 3)
        self.assertGreaterEqual(len(reports), 3)

    def test_zero_attempts_only_reviews_initial(self) -> None:
        gateway = RecordingGateway()
        service, _ = self._service(gateway, max_revision_attempts=0)
        project = service.create_novel(self._request("__E2E_AUTO_REVISE_ONCE__ 零次修订。"))
        result = service.generate_next_chapter(project.id)
        self.assertEqual(result.chapter.status, ChapterStatus.FAILED)
        self.assertEqual(gateway.revise_calls, 0)
        self.assertEqual(gateway.review_calls, 1)

    def test_structural_failure_triggers_replan_once(self) -> None:
        gateway = RecordingGateway()
        service, _ = self._service(gateway)
        project = service.create_novel(self._request("__E2E_AUTO_REPLAN__ 结构失败。"))
        result = service.generate_next_chapter(project.id)
        self.assertEqual(result.chapter.status, ChapterStatus.READY)
        self.assertGreaterEqual(gateway.plan_calls, 2)
        self.assertGreaterEqual(gateway.write_calls, 2)

    def test_accept_with_warnings_cannot_bypass_score_line(self) -> None:
        soft = ReviewReport(
            decision=ReviewDecision.REVISE,
            score=58,
            issues=[
                ReviewIssue(
                    category="readability.opening_hook",
                    severity=IssueSeverity.MAJOR,
                    message="开篇钩子偏弱",
                    suggestion="重写开篇",
                    evidence=["维度 opening_hook 得分 58"],
                )
            ],
        )
        self.assertFalse(can_accept_with_warnings(soft, "有正文"))
        self.assertFalse(can_accept_with_warnings(soft, ""))

        gateway = RecordingGateway()
        service, _ = self._service(gateway, max_revision_attempts=0)
        project = service.create_novel(self._request("__E2E_SOFT_FAIL__ 软问题。"))
        result = service.generate_next_chapter(project.id)
        self.assertEqual(result.chapter.status, ChapterStatus.FAILED)
        workspace = service.get_chapter_workspace(project.id, 1)
        self.assertFalse(workspace["capabilities"]["accept_with_warnings"])

    def test_hard_block_rejects_accept(self) -> None:
        gateway = RecordingGateway()
        service, _ = self._service(gateway, max_revision_attempts=0)
        project = service.create_novel(self._request("__E2E_HARD_FAIL__ 硬阻断。"))
        result = service.generate_next_chapter(project.id)
        self.assertEqual(result.chapter.status, ChapterStatus.FAILED)
        workspace = service.get_chapter_workspace(project.id, 1)
        self.assertFalse(workspace["capabilities"]["accept_with_warnings"])
        content = workspace["chapter"].content or "正文"
        title = workspace["chapter"].title
        hash_value = draft_content_hash(title, content)
        from novel_agent.features.chapter_review.errors import QualityOverrideNotAllowedError

        with self.assertRaises(QualityOverrideNotAllowedError):
            service.accept_failed_chapter_with_warnings(
                project.id,
                1,
                ChapterAcceptWithWarningsRequest(
                    confirm=True,
                    base_version=workspace["chapter"].version,
                    expected_draft_hash=hash_value,
                ),
            )


if __name__ == "__main__":
    unittest.main()

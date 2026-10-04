from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from novel_agent.features.opening_repair.errors import OpeningRepairError
from novel_agent.features.opening_repair.models import OpeningRepairApplyRequest
from novel_agent.features.opening_repair.service import OpeningRepairService
from novel_agent.features.opening_repair.errors import ChapterActionNotAllowedError
from novel_agent.integrations.llm.offline import OfflineLLMGateway
from novel_agent.integrations.search.disabled import DisabledSearchAdapter
from novel_agent.models import (
    ChapterDraftUpdate,
    ChapterRevisionCommitRequest,
    ChapterStatus,
    NovelCreateRequest,
)
from novel_agent.repository import SQLiteRepository
from novel_agent.service import NovelAgentService


class OpeningRepairAndFailedReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = SQLiteRepository(Path(self.tmp.name) / "repair.db")
        self.service = NovelAgentService(
            self.repo, OfflineLLMGateway(), DisabledSearchAdapter()
        )
        self.repair = OpeningRepairService(self.repo, self.repo.opening_repair)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _failed_project(self) -> str:
        project = self.service.create_novel(
            NovelCreateRequest(
                idea="__E2E_FAIL_REVIEW__ 神纹仓库管理员抢先机",
                genre="末世",
                elements=["囤货"],
                experiences=["爽文"],
                require_plan_confirmation=False,
            )
        )
        result = self.service.generate_next_chapter(project.id)
        self.assertEqual(result.chapter.status, ChapterStatus.FAILED)
        return project.id

    def test_preview_does_not_mutate_and_apply_needs_fresh_lock(self) -> None:
        project_id = self._failed_project()
        before = [
            (item.name, (item.current_state or {}).get("relationships"))
            for item in self.repo.list_characters(project_id)
        ]
        preview = self.repair.preview(project_id)
        self.assertTrue(preview.eligible)
        after = [
            (item.name, (item.current_state or {}).get("relationships"))
            for item in self.repo.list_characters(project_id)
        ]
        self.assertEqual(before, after)
        with self.assertRaises(OpeningRepairError) as stale:
            self.repair.apply(
                project_id,
                OpeningRepairApplyRequest(confirm=True, expected_project_updated_at="stale"),
            )
        self.assertEqual(stale.exception.code, "OPENING_REPAIR_PREVIEW_STALE")
        applied = self.repair.apply(
            project_id,
            OpeningRepairApplyRequest(
                confirm=True, expected_project_updated_at=preview.project_updated_at
            ),
        )
        self.assertTrue(applied.snapshot_id)
        rolled = self.repair.rollback(project_id, applied.snapshot_id)
        self.assertTrue(rolled["rolled_back"])

    def test_formal_chapter_is_not_eligible_and_does_not_affect_other_projects(self) -> None:
        ready = self.service.create_novel(
            NovelCreateRequest(
                idea="正常离线生成",
                genre="末世",
                require_plan_confirmation=False,
            )
        )
        self.service.generate_next_chapter(ready.id)
        other = self._failed_project()
        preview = self.repair.preview(ready.id)
        self.assertFalse(preview.eligible)
        self.assertTrue(any("正式章节" in item for item in preview.reasons))
        failed_preview = self.repair.preview(other)
        applied = self.repair.apply(
            other,
            OpeningRepairApplyRequest(
                confirm=True,
                expected_project_updated_at=failed_preview.project_updated_at,
            ),
        )
        ready_chapter = self.repo.get_chapter_by_number(ready.id, 1)
        assert ready_chapter is not None
        self.assertEqual(ready_chapter.status, ChapterStatus.READY)
        self.assertTrue(applied.snapshot_id)

    def test_failed_workspace_can_edit_ai_but_not_commit_until_review_pass(self) -> None:
        project_id = self._failed_project()
        workspace = self.service.get_chapter_workspace(project_id, 1)
        self.assertTrue(workspace["capabilities"]["edit_draft"])
        self.assertTrue(workspace["capabilities"]["use_assistant"])
        self.assertFalse(workspace["capabilities"]["commit_revision"])
        self.assertTrue(workspace["capabilities"]["submit_for_review"])
        draft = self.service.save_chapter_edit_draft(
            project_id,
            1,
            ChapterDraftUpdate(
                base_version=workspace["chapter"].version,
                title=workspace["chapter"].title,
                content=(workspace["chapter"].content or "草稿") + "补写",
            ),
        )
        session = self.service.create_assistant_session(project_id, 1)
        self.assertTrue(session.id)
        with self.assertRaises(ChapterActionNotAllowedError) as blocked:
            self.service.commit_chapter_edit_draft(
                project_id,
                1,
                ChapterRevisionCommitRequest(
                    base_version=workspace["chapter"].version,
                    expected_draft_hash=draft.content_hash,
                ),
            )
        self.assertEqual(blocked.exception.code, "FAILED_DRAFT_REVIEW_REQUIRED")
        still_failed = self.service.submit_failed_chapter_review(
            project_id,
            1,
            ChapterRevisionCommitRequest(
                base_version=workspace["chapter"].version,
                expected_draft_hash=draft.content_hash,
            ),
        )
        self.assertFalse(still_failed["passed"])
        chapter = self.repo.get_chapter_by_number(project_id, 1)
        assert chapter is not None
        self.assertEqual(chapter.status, ChapterStatus.FAILED)
        self.assertIsNotNone(self.repo.get_chapter_edit_draft(project_id, 1))
        passing = self.service.save_chapter_edit_draft(
            project_id,
            1,
            ChapterDraftUpdate(
                base_version=chapter.version,
                title=chapter.title,
                content=draft.content + "【送审修正】",
                expected_draft_hash=draft.content_hash,
            ),
        )
        passed = self.service.submit_failed_chapter_review(
            project_id,
            1,
            ChapterRevisionCommitRequest(
                base_version=chapter.version,
                expected_draft_hash=passing.content_hash,
            ),
        )
        self.assertTrue(passed["passed"])
        ready = self.repo.get_chapter_by_number(project_id, 1)
        assert ready is not None
        self.assertEqual(ready.status, ChapterStatus.READY)


if __name__ == "__main__":
    unittest.main()


from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from novel_agent.features.chapter_planning.errors import ReworkModeNotAllowedError
from novel_agent.features.opening_repair.errors import OpeningRepairError
from novel_agent.features.opening_repair.models import OpeningRepairApplyRequest
from novel_agent.features.opening_repair.service import OpeningRepairService
from novel_agent.infrastructure.persistence.opening_repair_store import OpeningRepairStoreError
from novel_agent.integrations.llm.offline import OfflineLLMGateway
from novel_agent.integrations.search.disabled import DisabledSearchAdapter
from novel_agent.memory_manager import MemoryManager
from novel_agent.models import (
    ChapterRecord,
    ChapterStatus,
    IssueSeverity,
    NovelCreateRequest,
    ReviewDecision,
    ReviewIssue,
    ReviewReport,
    new_id,
    utc_now,
)
from novel_agent.repository import SQLiteRepository
from novel_agent.service import NovelAgentService


class OpeningRepairRollbackSafetyTests(unittest.TestCase):
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
                require_plan_confirmation=False,
            )
        )
        result = self.service.generate_next_chapter(project.id)
        self.assertEqual(result.chapter.status, ChapterStatus.FAILED)
        return project.id

    def _apply(self, project_id: str):
        preview = self.repair.preview(project_id)
        return self.repair.apply(
            project_id,
            OpeningRepairApplyRequest(
                confirm=True,
                expected_project_updated_at=preview.project_updated_at,
            ),
        )

    def _insert_planned_chapter_two(self, project_id: str) -> ChapterRecord:
        now = utc_now()
        chapter = self.repo.create_chapter(
            ChapterRecord(
                id=new_id("chapter"),
                project_id=project_id,
                number=2,
                title="第2章 待规划",
                status=ChapterStatus.PLANNED,
                created_at=now,
                updated_at=now,
            )
        )
        self.repo.save_draft_version(chapter.id, "第二章草稿", {"kind": "PLANNED"})
        run_id = new_id("run")
        self.repo.create_run(run_id, project_id, chapter.id)
        self.repo.save_review_report(
            chapter.id,
            run_id,
            ReviewReport(decision=ReviewDecision.REVISE, score=40),
        )
        now = utc_now()
        with self.repo.transaction() as conn:
            conn.execute(
                """INSERT INTO chapter_edit_drafts
                (chapter_id,project_id,base_version,title,content,source,
                 applied_change_ids_json,content_hash,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    chapter.id,
                    project_id,
                    chapter.version,
                    chapter.title,
                    "第二章工作草稿",
                    "manual",
                    "[]",
                    "draft-ch2",
                    now,
                    now,
                ),
            )
        return self.repo.get_chapter(chapter.id)

    def test_rollback_keeps_snapshot_and_chapter_two_tree(self) -> None:
        project_id = self._failed_project()
        other = self.service.create_novel(
            NovelCreateRequest(idea="旁路项目", genre="末世", require_plan_confirmation=False)
        )
        chapter_one = self.repo.get_chapter_by_number(project_id, 1)
        assert chapter_one is not None
        sources = self.repo.save_research_sources(
            project_id,
            chapter_one.id,
            [{"title": "错误开篇资料", "excerpt": "污染第一章", "reliability": 0.99}],
        )
        with self.repo.transaction() as conn:
            conn.execute(
                "UPDATE research_sources SET chapter_id=NULL WHERE id=?",
                (sources[0]["id"],),
            )
        self.repo.upsert_semantic_documents(
            project_id,
            [
                {
                    "source_type": "research_source",
                    "source_id": str(sources[0]["id"]),
                    "chapter_id": chapter_one.id,
                    "content": "污染索引",
                }
            ],
            [[0.2, 0.8]],
            "test-embedding",
        )
        other_ch = self.service.generate_next_chapter(other.id).chapter
        self.repo.save_research_sources(
            other.id,
            other_ch.id,
            [{"title": "其他项目资料", "excerpt": "应保留", "reliability": 0.9}],
        )
        chapter_two = self._insert_planned_chapter_two(project_id)
        two_before = {
            "id": chapter_two.id,
            "status": chapter_two.status,
            "title": chapter_two.title,
            "version": chapter_two.version,
        }
        with self.repo.connection() as conn:
            versions_before = conn.execute(
                "SELECT COUNT(*) AS n FROM chapter_versions WHERE chapter_id=?",
                (chapter_two.id,),
            ).fetchone()["n"]
            runs_before = conn.execute(
                "SELECT COUNT(*) AS n FROM runs WHERE chapter_id=?",
                (chapter_two.id,),
            ).fetchone()["n"]
            reports_before = conn.execute(
                "SELECT COUNT(*) AS n FROM review_reports WHERE chapter_id=?",
                (chapter_two.id,),
            ).fetchone()["n"]
        draft_before = self.repo.get_chapter_edit_draft(project_id, 2)
        assert draft_before is not None
        characters_before = [(item.name, item.current_state) for item in self.repo.list_characters(project_id)]
        brief_before = self.repo.get_project(project_id).brief.model_dump(mode="json")
        research_before = self.repo.list_research_sources(project_id)
        semantic_before = self.repo.semantic_document_count(project_id)

        applied = self._apply(project_id)
        self.assertEqual(self.repo.list_research_sources(project_id), [])
        self.assertEqual(self.repo.semantic_document_count(project_id), 0)
        compact = MemoryManager().build_context(
            characters=self.repo.list_characters(project_id),
            world_facts=self.repo.list_world_facts(project_id),
            timeline=self.repo.list_timeline(project_id),
            research_sources=self.repo.list_research_sources(project_id),
            current_chapter=1,
        )
        self.assertEqual(compact.get("compact_research"), [])
        other_sources = self.repo.list_research_sources(other.id)
        self.assertTrue(any(item["title"] == "其他项目资料" for item in other_sources))

        latest = self.repair.latest_snapshot(project_id)
        self.assertEqual(latest["snapshot"]["id"], applied.snapshot_id)
        self.assertTrue(latest["snapshot"]["rollback_allowed"])

        rolled = self.repair.rollback(project_id, applied.snapshot_id)
        self.assertTrue(rolled["rolled_back"])
        with self.repo.connection() as conn:
            snap = conn.execute(
                "SELECT status, rolled_back_at FROM project_repair_snapshots WHERE id=?",
                (applied.snapshot_id,),
            ).fetchone()
            project_rows = conn.execute(
                "SELECT COUNT(*) AS n FROM projects WHERE id=?", (project_id,)
            ).fetchone()["n"]
        self.assertEqual(snap["status"], "rolled_back")
        self.assertTrue(snap["rolled_back_at"])
        self.assertEqual(project_rows, 1)

        restored_two = self.repo.get_chapter(chapter_two.id)
        self.assertEqual(restored_two.status, two_before["status"])
        self.assertEqual(restored_two.title, two_before["title"])
        self.assertEqual(restored_two.id, two_before["id"])
        with self.repo.connection() as conn:
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) AS n FROM chapter_versions WHERE chapter_id=?",
                    (chapter_two.id,),
                ).fetchone()["n"],
                versions_before,
            )
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) AS n FROM runs WHERE chapter_id=?",
                    (chapter_two.id,),
                ).fetchone()["n"],
                runs_before,
            )
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) AS n FROM review_reports WHERE chapter_id=?",
                    (chapter_two.id,),
                ).fetchone()["n"],
                reports_before,
            )
        draft_after = self.repo.get_chapter_edit_draft(project_id, 2)
        assert draft_after is not None
        self.assertEqual(draft_after.content, draft_before.content)
        self.assertEqual(
            [(item.name, item.current_state) for item in self.repo.list_characters(project_id)],
            characters_before,
        )
        self.assertEqual(self.repo.get_project(project_id).brief.model_dump(mode="json"), brief_before)
        self.assertEqual(len(self.repo.list_research_sources(project_id)), len(research_before))
        self.assertEqual(self.repo.semantic_document_count(project_id), semantic_before)
        restored_one = self.repo.get_chapter_by_number(project_id, 1)
        assert restored_one is not None
        self.assertEqual(restored_one.status, ChapterStatus.FAILED)

        with self.assertRaises(OpeningRepairError) as second:
            self.repair.rollback(project_id, applied.snapshot_id)
        self.assertEqual(second.exception.code, "OPENING_REPAIR_ROLLBACK_UNSAFE")
        self.assertIsNone(self.repair.latest_snapshot(project_id)["snapshot"])
        other_ready = self.repo.get_chapter_by_number(other.id, 1)
        assert other_ready is not None
        self.assertEqual(other_ready.status, ChapterStatus.READY)

    def test_rollback_transaction_restores_pre_rollback_state(self) -> None:
        project_id = self._failed_project()
        applied = self._apply(project_id)
        original = self.repair.store.mark_rolled_back

        def boom(*_args, **_kwargs):
            raise OpeningRepairStoreError("injected")

        self.repair.store.mark_rolled_back = boom  # type: ignore[method-assign]
        with self.assertRaises(OpeningRepairError):
            self.repair.rollback(project_id, applied.snapshot_id)
        self.repair.store.mark_rolled_back = original  # type: ignore[method-assign]
        with self.repo.connection() as conn:
            snap = conn.execute(
                "SELECT status, rolled_back_at FROM project_repair_snapshots WHERE id=?",
                (applied.snapshot_id,),
            ).fetchone()
        self.assertEqual(snap["status"], "applied")
        self.assertIsNone(snap["rolled_back_at"])
        self.assertEqual(self.repo.list_research_sources(project_id), [])

    def test_structural_reuse_plan_is_rejected(self) -> None:
        project_id = self._failed_project()
        chapter = self.repo.get_chapter_by_number(project_id, 1)
        assert chapter is not None
        self.repo.save_review_report(
            chapter.id,
            "review-structural",
            ReviewReport(
                decision=ReviewDecision.REVISE,
                score=40,
                issues=[
                    ReviewIssue(
                        category="character state",
                        severity=IssueSeverity.MAJOR,
                        message="人物关系写成未来效忠",
                        suggestion="回到初态",
                    )
                ],
            ),
        )
        with self.assertRaises(ReworkModeNotAllowedError) as blocked:
            self.service.rework_chapter(project_id, 1, mode="reuse_plan")
        self.assertEqual(blocked.exception.code, "REWORK_MODE_NOT_ALLOWED")


if __name__ == "__main__":
    unittest.main()

import tempfile
import unittest
from pathlib import Path

from novel_agent.integrations.llm.offline import OfflineLLMGateway
from novel_agent.integrations.search.disabled import DisabledSearchAdapter
from novel_agent.models import (
    AssistantMessageCreate,
    AssistantMode,
    ChapterDraftUpdate,
    ChapterRevisionCommitRequest,
    NovelCreateRequest,
    new_id,
    utc_now,
)
from novel_agent.repository import SCHEMA_VERSION, SQLiteRepository
from novel_agent.service import NovelAgentService
from novel_agent.text_normalize import draft_content_hash


class RevisionWorkspaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = SQLiteRepository(Path(self._tmp.name) / "rev.db")
        self.service = NovelAgentService(
            repository=self.repo,
            gateway=OfflineLLMGateway(),
            search=DisabledSearchAdapter(),
        )
        request = NovelCreateRequest(
            idea="旧港来信修订测试",
            genre="悬疑",
            elements=["推理"],
            experiences=["紧张"],
            require_plan_confirmation=False,
        )
        self.project = self.service.create_novel(request)
        self._seed_ready_chapters()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _seed_ready_chapters(self) -> None:
        now = utc_now()
        with self.repo.transaction() as conn:
            for number, title, content in (
                (1, "第一章 旧港", "旧港的风很冷。\n\n林夏推开锈门。"),
                (2, "第二章 灯火", "灯火在雾中晃动。\n\n她继续向前。"),
            ):
                chapter_id = new_id("chapter")
                conn.execute(
                    """INSERT INTO chapters
                    (id,project_id,number,title,status,plan_json,content,summary,version,locked,created_at,updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        chapter_id,
                        self.project.id,
                        number,
                        title,
                        "READY",
                        None,
                        content,
                        f"{title}摘要",
                        1,
                        0,
                        now,
                        now,
                    ),
                )
                conn.execute(
                    """INSERT INTO chapter_versions
                    (chapter_id,version,kind,content,metadata_json,created_at,title,source,is_official)
                    VALUES (?,?,?,?,?,?,?,?,?)""",
                    (
                        chapter_id,
                        1,
                        "FINAL",
                        content,
                        "{}",
                        now,
                        title,
                        "agent",
                        1,
                    ),
                )

    def test_schema_version_is_six(self) -> None:
        self.assertEqual(SCHEMA_VERSION, 6)
        with self.repo.connection() as conn:
            rows = {
                int(row["version"])
                for row in conn.execute("SELECT version FROM schema_migrations").fetchall()
            }
            self.assertIn(6, rows)
            columns = {
                row["name"] for row in conn.execute("PRAGMA table_info(chapter_versions)").fetchall()
            }
            self.assertTrue({"title", "source", "is_official"} <= columns)
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            self.assertIn("project_repair_snapshots", tables)

    def test_draft_autosave_does_not_change_official_chapter(self) -> None:
        draft = self.service.save_chapter_edit_draft(
            self.project.id,
            1,
            ChapterDraftUpdate(
                base_version=1,
                title="第一章 旧港来信",
                content="旧港的风更冷了。\n\n林夏推开锈门。",
            ),
        )
        chapter = self.repo.get_chapter_by_number(self.project.id, 1)
        assert chapter is not None
        self.assertEqual(chapter.version, 1)
        self.assertEqual(chapter.title, "第一章 旧港")
        self.assertEqual(draft.source, "manual")
        self.assertEqual(
            draft.content_hash,
            draft_content_hash("第一章 旧港来信", "旧港的风更冷了。\n\n林夏推开锈门。"),
        )

    def test_assistant_approve_then_commit_resets_later_with_archive(self) -> None:
        draft = self.service.save_chapter_edit_draft(
            self.project.id,
            1,
            ChapterDraftUpdate(
                base_version=1,
                title="第一章 旧港",
                content="旧港的风很冷。\n\n林夏推开锈门。",
            ),
        )
        session = self.service.create_assistant_session(self.project.id, 1)
        result = self.service.send_assistant_message(
            session.id,
            AssistantMessageCreate(content="全文修订", mode=AssistantMode.EDITOR),
        )
        self.assertIsNotNone(result["change_set"])
        approved = self.service.approve_assistant_change(result["change_set"].id)
        self.assertEqual(approved["draft"].source, "mixed")
        chapter_before = self.repo.get_chapter_by_number(self.project.id, 1)
        assert chapter_before is not None
        self.assertEqual(chapter_before.version, 1)

        commit = self.service.commit_chapter_edit_draft(
            self.project.id,
            1,
            ChapterRevisionCommitRequest(
                base_version=1,
                expected_draft_hash=approved["draft"].content_hash,
            ),
        )
        self.assertEqual(commit.chapter.version, 2)
        self.assertEqual(commit.reset_chapters, [2])
        later = self.repo.get_chapter_by_number(self.project.id, 2)
        assert later is not None
        self.assertEqual(later.status.value, "PLANNED")
        self.assertIsNone(later.content)
        versions = self.repo.list_chapter_versions(self.project.id, 2)
        self.assertTrue(any(item["kind"] == "RESET_ARCHIVE" for item in versions))
        self.assertIsNone(self.repo.get_chapter_edit_draft(self.project.id, 1))
        # Original seed draft unused in commit path after approve; silence linters.
        self.assertTrue(draft.content_hash)

    def test_ai_cannot_write_official_without_approve(self) -> None:
        self.service.save_chapter_edit_draft(
            self.project.id,
            1,
            ChapterDraftUpdate(
                base_version=1,
                title="第一章 旧港",
                content="旧港的风很冷。\n\n林夏推开锈门。",
            ),
        )
        session = self.service.create_assistant_session(self.project.id, 1)
        result = self.service.send_assistant_message(
            session.id,
            AssistantMessageCreate(content="改写", mode=AssistantMode.EDITOR),
        )
        chapter = self.repo.get_chapter_by_number(self.project.id, 1)
        assert chapter is not None
        self.assertEqual(chapter.version, 1)
        self.assertNotIn("离线修订", chapter.content or "")
        self.assertEqual(result["change_set"].status.value, "PENDING")


if __name__ == "__main__":
    unittest.main()

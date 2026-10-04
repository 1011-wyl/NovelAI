from __future__ import annotations

import json
import tempfile
import unittest
from http import HTTPStatus
from pathlib import Path
from typing import Any

from novel_agent.api import AppContext, NovelAgentHandler
from novel_agent.config import Settings
from novel_agent.features.projects.models import ProjectMetadataUpdate, ProjectSummary
from novel_agent.integrations.llm.offline import OfflineLLMGateway
from novel_agent.integrations.search.disabled import DisabledSearchAdapter
from novel_agent.models import ChapterStatus, NovelCreateRequest, ProjectStatus
from novel_agent.repository import SQLiteRepository
from novel_agent.service import NovelAgentService
from novel_agent.text_metrics import count_content_chars


class ProjectSummaryStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = tempfile.TemporaryDirectory()
        self.repository = SQLiteRepository(Path(self.folder.name) / "summary.db")
        self.service = NovelAgentService(
            self.repository, OfflineLLMGateway(), DisabledSearchAdapter()
        )

    def tearDown(self) -> None:
        self.folder.cleanup()

    def test_empty_list_and_summary_shape(self) -> None:
        summaries = self.repository.list_project_summaries()
        self.assertEqual(summaries, [])
        project = self.service.create_novel(
            NovelCreateRequest(
                preferred_title="书架书名",
                genre="末世",
                idea="资源社区。",
                chapter_target_chars=800,
            )
        )
        summaries = self.repository.list_project_summaries()
        self.assertEqual(len(summaries), 1)
        summary = summaries[0]
        self.assertIsInstance(summary, ProjectSummary)
        payload = summary.model_dump()
        self.assertEqual(
            set(payload),
            {
                "id",
                "title",
                "status",
                "confirmed",
                "audience_channel",
                "genre",
                "chapter_count",
                "content_chars",
                "current_chapter",
                "created_at",
                "updated_at",
            },
        )
        self.assertNotIn("request", payload)
        self.assertNotIn("brief", payload)
        self.assertEqual(summary.id, project.id)
        self.assertEqual(summary.title, "书架书名")
        self.assertEqual(summary.chapter_count, 0)
        self.assertEqual(summary.content_chars, 0)

    def test_summary_counts_non_whitespace_and_orders_by_updated_at(self) -> None:
        older = self.service.create_novel(
            NovelCreateRequest(
                preferred_title="旧书",
                genre="末世",
                idea="旧想法。",
                chapter_target_chars=800,
            )
        )
        newer = self.service.create_novel(
            NovelCreateRequest(
                preferred_title="新书",
                genre="悬疑",
                idea="新想法。",
                chapter_target_chars=800,
            )
        )
        self.service.confirm_novel(newer.id)
        result = self.service.generate_next_chapter(newer.id)
        self.assertIsNotNone(result)

        summaries = self.repository.list_project_summaries()
        self.assertEqual([item.id for item in summaries], [newer.id, older.id])
        focused = next(item for item in summaries if item.id == newer.id)
        chapters = self.repository.list_chapters(newer.id)
        expected_chars = sum(
            count_content_chars(chapter.content)
            for chapter in chapters
            if chapter.content
        )
        self.assertEqual(focused.chapter_count, len(chapters))
        self.assertEqual(focused.content_chars, expected_chars)
        self.assertGreater(focused.content_chars, 0)
        # Empty-content chapters still count toward chapter_count.
        empty_ready = [c for c in chapters if c.status == ChapterStatus.READY]
        self.assertTrue(empty_ready)


class ProjectMetadataServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = tempfile.TemporaryDirectory()
        self.repository = SQLiteRepository(Path(self.folder.name) / "meta.db")
        self.service = NovelAgentService(
            self.repository, OfflineLLMGateway(), DisabledSearchAdapter()
        )

    def tearDown(self) -> None:
        self.folder.cleanup()

    def test_rename_strips_syncs_brief_and_appends_version(self) -> None:
        project = self.service.create_novel(
            NovelCreateRequest(
                preferred_title="原书名",
                genre="末世",
                idea="资源社区。",
                chapter_target_chars=800,
            )
        )
        confirmed = self.service.confirm_novel(project.id)
        summary = self.service.projects.update_metadata(  # type: ignore[union-attr]
            project.id,
            ProjectMetadataUpdate(title="  新的书名  "),
        )
        self.assertEqual(summary.title, "新的书名")
        refreshed = self.repository.get_project(project.id)
        self.assertEqual(refreshed.title, "新的书名")
        self.assertEqual(refreshed.brief.selected_title, "新的书名")
        self.assertEqual(refreshed.brief.title_candidates[0], "新的书名")
        self.assertEqual(refreshed.status, confirmed.status)
        self.assertTrue(refreshed.confirmed)
        self.assertEqual(refreshed.current_chapter, confirmed.current_chapter)
        versions = self.repository.list_brief_versions(project.id)
        self.assertEqual(versions[0]["source"], "metadata_edit")
        self.assertEqual(versions[0]["brief"].selected_title, "新的书名")

    def test_empty_title_rejected(self) -> None:
        with self.assertRaises(Exception):
            ProjectMetadataUpdate(title="   ")


class ProjectMetadataRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        root = Path(self._tmpdir.name)
        web = root / "web"
        web.mkdir()
        (web / "index.html").write_text("<html></html>", encoding="utf-8")
        self.repository = SQLiteRepository(root / "db.sqlite")
        self.service = NovelAgentService(
            self.repository, OfflineLLMGateway(), DisabledSearchAdapter()
        )
        self.context = AppContext(
            Settings.load(Path.cwd()), self.service, self.repository, web
        )

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _request(
        self, method: str, path: str, payload: dict[str, Any] | None = None
    ) -> tuple[int, dict[str, Any]]:
        body = b""
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        class FakeHandler(NovelAgentHandler):
            def __init__(self) -> None:
                self.command = method
                self.path = path
                self.headers = {"Content-Length": str(len(body))}
                self.rfile = type("R", (), {"read": lambda _self, n: body})()
                self.context = self_outer.context
                self._status = 0
                self._body = b""

            def send_response(self, code: int, message: str | None = None) -> None:
                self._status = code

            def send_header(self, keyword: str, value: str) -> None:
                return None

            def end_headers(self) -> None:
                return None

            def _cors_headers(self) -> None:
                return None

            @property
            def wfile(self):  # noqa: ANN201
                handler = self

                class Writer:
                    def write(self, data: bytes) -> int:
                        handler._body += data
                        return len(data)

                return Writer()

        self_outer = self
        fake = FakeHandler()
        getattr(fake, f"do_{method}")()
        return fake._status, json.loads(fake._body.decode("utf-8") or "{}")

    def test_list_returns_summaries_by_default(self) -> None:
        status, empty = self._request("GET", "/api/novels")
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(empty, {"items": []})

        created = self.service.create_novel(
            NovelCreateRequest(
                preferred_title="列表书名",
                genre="末世",
                idea="资源社区。",
                chapter_target_chars=800,
            )
        )
        status, listed = self._request("GET", "/api/novels")
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(len(listed["items"]), 1)
        item = listed["items"][0]
        self.assertEqual(item["id"], created.id)
        self.assertNotIn("request", item)
        self.assertNotIn("brief", item)

        status, full = self._request("GET", "/api/novels?detail=full")
        self.assertEqual(status, HTTPStatus.OK)
        self.assertIn("request", full["items"][0])

    def test_metadata_put_validation_and_success(self) -> None:
        created = self.service.create_novel(
            NovelCreateRequest(
                preferred_title="改名原标题",
                genre="末世",
                idea="资源社区。",
                chapter_target_chars=800,
            )
        )
        status, bad = self._request(
            "PUT", f"/api/novels/{created.id}/metadata", {"title": ""}
        )
        self.assertEqual(status, HTTPStatus.UNPROCESSABLE_ENTITY)

        status, extra = self._request(
            "PUT",
            f"/api/novels/{created.id}/metadata",
            {"title": "合法", "extra": 1},
        )
        self.assertEqual(status, HTTPStatus.UNPROCESSABLE_ENTITY)

        status, missing = self._request(
            "PUT", "/api/novels/novel_missing/metadata", {"title": "幽灵"}
        )
        self.assertEqual(status, HTTPStatus.NOT_FOUND)

        status, ok = self._request(
            "PUT", f"/api/novels/{created.id}/metadata", {"title": " 改后书名 "}
        )
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(ok["title"], "改后书名")
        self.assertEqual(ok["status"], ProjectStatus.DRAFT.value)
        self.assertFalse(ok["confirmed"])
        self.assertNotIn("brief", ok)
        self.assertNotIn("request", ok)


if __name__ == "__main__":
    unittest.main()

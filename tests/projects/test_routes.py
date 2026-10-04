from __future__ import annotations

import json
import tempfile
import unittest
from http import HTTPStatus
from pathlib import Path
from typing import Any

from novel_agent.integrations.llm.offline import OfflineLLMGateway
from novel_agent.integrations.search.disabled import DisabledSearchAdapter
from novel_agent.api import AppContext, NovelAgentHandler
from novel_agent.config import Settings
from novel_agent.interfaces.http.routes.projects import (
    dispatch_projects_delete,
    dispatch_projects_get,
    dispatch_projects_post,
)
from novel_agent.models import NovelCreateRequest, ProjectRecord
from novel_agent.repository import SQLiteRepository
from novel_agent.service import NovelAgentService


class RecordingProjectService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    def list_projects(self) -> list[ProjectRecord]:
        self.calls.append(("list_projects", (), {}))
        return []

    def list_project_summaries(self) -> list[Any]:
        self.calls.append(("list_project_summaries", (), {}))
        return []

    def get_detail(self, project_id: str) -> dict[str, object]:
        self.calls.append(("get_detail", (project_id,), {}))
        return {"project": {"id": project_id}}

    def confirm(self, project_id: str) -> dict[str, object]:
        self.calls.append(("confirm", (project_id,), {}))
        return {"id": project_id, "confirmed": True}

    def pause(self, project_id: str) -> dict[str, object]:
        self.calls.append(("pause", (project_id,), {}))
        return {"id": project_id, "status": "PAUSED"}

    def resume(self, project_id: str) -> dict[str, object]:
        self.calls.append(("resume", (project_id,), {}))
        return {"id": project_id, "status": "ACTIVE"}

    def recover(self, project_id: str) -> dict[str, object]:
        self.calls.append(("recover", (project_id,), {}))
        return {"id": project_id, "status": "ACTIVE"}

    def update_metadata(self, project_id: str, update: Any) -> dict[str, object]:
        self.calls.append(("update_metadata", (project_id, update), {}))
        return {"id": project_id, "title": getattr(update, "title", "")}

    def delete(
        self, project_id: str, confirmation_title: str | None = None
    ) -> None:
        self.calls.append(
            ("delete", (project_id,), {"confirmation_title": confirmation_title})
        )


class ProjectsRouteDispatchTests(unittest.TestCase):
    def test_unmatched_path_returns_none(self) -> None:
        service = RecordingProjectService()
        self.assertIsNone(dispatch_projects_get("/api/tags", {}, service))  # type: ignore[arg-type]
        self.assertIsNone(
            dispatch_projects_post("/api/novels", {}, service)  # type: ignore[arg-type]
        )
        self.assertEqual(service.calls, [])

    def test_list_detail_lifecycle_and_recover_proxy(self) -> None:
        service = RecordingProjectService()
        listed = dispatch_projects_get("/api/novels", {}, service)  # type: ignore[arg-type]
        detail = dispatch_projects_get("/api/novels/novel_1", {}, service)  # type: ignore[arg-type]
        confirm = dispatch_projects_post(
            "/api/novels/novel_1/confirm", {}, service  # type: ignore[arg-type]
        )
        recover = dispatch_projects_post(
            "/api/novels/novel_1/recover", {}, service  # type: ignore[arg-type]
        )
        deleted = dispatch_projects_delete(
            "/api/novels/novel_1",
            {"confirmation_title": "书名"},
            service,  # type: ignore[arg-type]
        )
        assert listed and detail and confirm and recover and deleted
        self.assertEqual(listed.payload, {"items": []})
        self.assertEqual(
            [call[0] for call in service.calls],
            ["list_project_summaries", "get_detail", "confirm", "recover", "delete"],
        )
        self.assertEqual(service.calls[-1][2]["confirmation_title"], "书名")


class ProjectsRouteCharacterizationTests(unittest.TestCase):
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
        self.context = AppContext(Settings.load(Path.cwd()), self.service, self.repository, web)
        self.assertIsNotNone(self.context.projects)
        self.assertIs(self.context.projects, self.service.projects)

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
        if method == "GET":
            fake.do_GET()
        elif method == "POST":
            fake.do_POST()
        elif method == "PUT":
            fake.do_PUT()
        elif method == "DELETE":
            fake.do_DELETE()
        else:
            raise AssertionError(method)
        return fake._status, json.loads(fake._body.decode("utf-8") or "{}")

    def test_list_detail_confirm_pause_resume_delete_paths(self) -> None:
        status, empty = self._request("GET", "/api/novels")
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(empty, {"items": []})

        created = self.service.create_novel(
            NovelCreateRequest(
                preferred_title="路由书名",
                genre="末世",
                idea="资源社区。",
                chapter_target_chars=800,
            )
        )
        status, detail = self._request("GET", f"/api/novels/{created.id}")
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(
            set(detail),
            {
                "project",
                "chapters",
                "latest_events",
                "characters",
                "world_facts",
                "timeline",
                "research_sources",
                "semantic_document_count",
                "reserve_count",
                "skills",
                "chapter_failures",
            },
        )

        status, confirmed = self._request("POST", f"/api/novels/{created.id}/confirm", {})
        self.assertEqual(status, HTTPStatus.OK)
        self.assertTrue(confirmed["confirmed"])

        status, paused = self._request("POST", f"/api/novels/{created.id}/pause", {})
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(paused["status"], "PAUSED")

        status, resumed = self._request("POST", f"/api/novels/{created.id}/resume", {})
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(resumed["status"], "ACTIVE")

        draft = self.service.create_novel(
            NovelCreateRequest(
                preferred_title="草稿删除",
                genre="悬疑",
                idea="调查。",
                chapter_target_chars=800,
            )
        )
        status, deleted = self._request("DELETE", f"/api/novels/{draft.id}", {})
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(deleted["deleted"], True)
        self.assertEqual(deleted["project_id"], draft.id)


if __name__ == "__main__":
    unittest.main()

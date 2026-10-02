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
from novel_agent.interfaces.http.routes.story_design import (
    dispatch_story_design_get,
    dispatch_story_design_post,
    dispatch_story_design_put,
)
from novel_agent.models import CreativeBrief, NovelCreateRequest
from novel_agent.repository import SQLiteRepository
from novel_agent.service import NovelAgentService


class RecordingStoryDesignService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    def list_versions(self, project_id: str) -> list[dict[str, object]]:
        self.calls.append(("list_versions", (project_id,)))
        return [{"version": 1}]

    def create_story(self, request: NovelCreateRequest) -> dict[str, object]:
        self.calls.append(("create_story", (request.preferred_title,)))
        return {"id": "novel_x", "brief": {"synopsis": "x"}}

    def regenerate_brief(
        self, project_id: str, change: Any
    ) -> dict[str, object]:
        self.calls.append(("regenerate_brief", (project_id, tuple(change.sections))))
        return {"id": project_id}

    def restore_brief(self, project_id: str, version: int) -> dict[str, object]:
        self.calls.append(("restore_brief", (project_id, version)))
        return {"id": project_id}

    def update_brief(self, project_id: str, brief: CreativeBrief) -> dict[str, object]:
        self.calls.append(("update_brief", (project_id, brief.synopsis)))
        return {"id": project_id, "brief": brief.model_dump(mode="json")}


class StoryDesignRouteDispatchTests(unittest.TestCase):
    def test_unmatched_path_returns_none(self) -> None:
        service = RecordingStoryDesignService()
        self.assertIsNone(
            dispatch_story_design_get("/api/novels", {}, service)  # type: ignore[arg-type]
        )
        self.assertIsNone(
            dispatch_story_design_put("/api/settings", {}, service)  # type: ignore[arg-type]
        )
        self.assertEqual(service.calls, [])

    def test_create_versions_put_regenerate_restore_dispatch(self) -> None:
        service = RecordingStoryDesignService()
        created = dispatch_story_design_post(
            "/api/novels",
            {
                "preferred_title": "派发书名",
                "genre": "末世",
                "idea": "资源社区。",
                "chapter_target_chars": 800,
            },
            service,  # type: ignore[arg-type]
        )
        versions = dispatch_story_design_get(
            "/api/novels/novel_x/brief-versions", {}, service  # type: ignore[arg-type]
        )
        brief = OfflineLLMGateway().create_brief(
            NovelCreateRequest(
                preferred_title="派发书名",
                genre="末世",
                idea="资源社区。",
                chapter_target_chars=800,
            )
        ).model_dump(mode="json")
        brief["synopsis"] = "手工"
        updated = dispatch_story_design_put(
            "/api/novels/novel_x/brief",
            brief,
            service,  # type: ignore[arg-type]
        )
        regenerated = dispatch_story_design_post(
            "/api/novels/novel_x/brief-regenerate",
            {"sections": ["title"]},
            service,  # type: ignore[arg-type]
        )
        restored = dispatch_story_design_post(
            "/api/novels/novel_x/brief-restore",
            {"version": 1},
            service,  # type: ignore[arg-type]
        )
        assert created and versions and updated and regenerated and restored
        self.assertEqual(created.status, HTTPStatus.CREATED)
        self.assertEqual(
            [call[0] for call in service.calls],
            [
                "create_story",
                "list_versions",
                "update_brief",
                "regenerate_brief",
                "restore_brief",
            ],
        )


class StoryDesignRouteCharacterizationTests(unittest.TestCase):
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
        self.assertIsNotNone(self.context.story_design)
        self.assertIs(self.context.story_design, self.service.story_design)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _request(
        self, method: str, path: str, payload: dict[str, Any] | None = None
    ) -> tuple[int, Any]:
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
        return fake._status, json.loads(fake._body.decode("utf-8") or "null")

    def test_tags_create_brief_versions_put_regenerate_restore(self) -> None:
        status, tags = self._request("GET", "/api/tags")
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(tags["default_channel"], "男频")
        self.assertIn("channels", tags)

        status, project = self._request(
            "POST",
            "/api/novels",
            {
                "preferred_title": "方案路由",
                "audience_channel": "男频",
                "genre": "末世",
                "idea": "资源社区。",
                "chapter_target_chars": 800,
            },
        )
        self.assertEqual(status, HTTPStatus.CREATED)
        project_id = project["id"]

        status, versions = self._request("GET", f"/api/novels/{project_id}/brief-versions")
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(len(versions["items"]), 1)

        brief = CreativeBrief.model_validate(project["brief"]).model_dump(mode="json")
        brief["synopsis"] = "路由手工简介"
        status, updated = self._request("PUT", f"/api/novels/{project_id}/brief", brief)
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(updated["brief"]["synopsis"], "路由手工简介")

        status, regenerated = self._request(
            "POST",
            f"/api/novels/{project_id}/brief-regenerate",
            {"sections": ["title"]},
        )
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(regenerated["brief"]["synopsis"], updated["brief"]["synopsis"])

        status, restored = self._request(
            "POST",
            f"/api/novels/{project_id}/brief-restore",
            {"version": 1},
        )
        self.assertEqual(status, HTTPStatus.OK)
        versions = self.repository.list_brief_versions(project_id)
        self.assertEqual(versions[0]["source"], "restore")
        self.assertEqual(restored["brief"]["synopsis"], project["brief"]["synopsis"])


if __name__ == "__main__":
    unittest.main()

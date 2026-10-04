from __future__ import annotations

import errno
import json
import mimetypes
import re
import traceback
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from pydantic import BaseModel, ValidationError

from novel_agent.integrations.errors import APIConfigurationRequired
from novel_agent.integrations.llm.errors import (
    LLMAuthenticationError,
    LLMProviderError,
    LLMRateLimitError,
    LLMResponseError,
    LLMTimeoutError,
)
from novel_agent.config import Settings
from novel_agent.features.analytics.errors import AnalyticsValidationError
from novel_agent.features.analytics.service import AnalyticsService
from novel_agent.features.chapter_planning.errors import ReworkModeNotAllowedError
from novel_agent.features.chapter_review.errors import QualityOverrideNotAllowedError
from novel_agent.features.opening_repair.errors import (
    ChapterActionNotAllowedError,
    OpeningRepairError,
)
from novel_agent.features.opening_repair.service import OpeningRepairService
from novel_agent.features.projects.service import ProjectService
from novel_agent.features.story_design.service import StoryDesignService
from novel_agent.features.llm_settings.errors import LLMSettingsError
from novel_agent.features.llm_settings.service import LLMSettingsService
from novel_agent.interfaces.http.routes.analytics import dispatch_analytics_get
from novel_agent.interfaces.http.routes.llm_settings import (
    dispatch_llm_settings_delete,
    dispatch_llm_settings_get,
    dispatch_llm_settings_post,
    dispatch_llm_settings_put,
    llm_settings_error_result,
)
from novel_agent.interfaces.http.routes.opening_repair import (
    dispatch_opening_repair_get,
    dispatch_opening_repair_post,
)
from novel_agent.interfaces.http.routes.projects import (
    dispatch_projects_delete,
    dispatch_projects_get,
    dispatch_projects_post,
    dispatch_projects_put,
)
from novel_agent.interfaces.http.routes.story_design import (
    dispatch_story_design_get,
    dispatch_story_design_post,
    dispatch_story_design_put,
)
from novel_agent.models import (
    AssistantMessageCreate,
    AssistantRollbackRequest,
    ChapterAcceptWithWarningsRequest,
    ChapterDraftUpdate,
    ChapterRevisionCommitRequest,
    ChapterStatus,
)
from novel_agent.repository import RepositoryError, SQLiteRepository
from novel_agent.requirements import RequirementConflict
from novel_agent.revision_errors import (
    AssistantChangeStaleError,
    AssistantChangeStateError,
    ChapterNotEditableError,
    EditConflictError,
    RevisionAnalysisError,
)
from novel_agent.service import NovelAgentService
from novel_agent.tags import public_tag_catalog
from novel_agent.workflow import WorkflowBlocked

_CLIENT_DISCONNECT_ERRNOS = {
    errno.EPIPE,
    errno.ECONNRESET,
    getattr(errno, "ECONNABORTED", 53),
}
_CLIENT_DISCONNECT_WINERRORS = {10053, 10054}


def _is_client_disconnect(exc: BaseException) -> bool:
    """True when the browser aborted or the TCP connection was already closed."""
    if isinstance(exc, (BrokenPipeError, ConnectionResetError, ConnectionAbortedError)):
        return True
    if isinstance(exc, OSError):
        winerror = getattr(exc, "winerror", None)
        if winerror in _CLIENT_DISCONNECT_WINERRORS:
            return True
        if getattr(exc, "errno", None) in _CLIENT_DISCONNECT_ERRNOS:
            return True
    return False


def _jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


@dataclass(slots=True)
class AppContext:
    """HTTP app context. Four positional args remain compatible.

    analytics / projects / story_design are migration-period Feature fields;
    bootstrap injects them explicitly, __post_init__ only fills defaults.
    """

    settings: Settings
    service: NovelAgentService
    repository: SQLiteRepository
    web_root: Path
    analytics: AnalyticsService | None = None
    projects: ProjectService | None = None
    story_design: StoryDesignService | None = None
    opening_repair: OpeningRepairService | None = None
    llm_settings: LLMSettingsService | None = None

    def __post_init__(self) -> None:
        if self.analytics is None:
            self.analytics = AnalyticsService(self.repository.analytics)
        if self.story_design is None:
            self.story_design = self.service.story_design
        if self.projects is None:
            self.projects = self.service.projects
        if self.opening_repair is None:
            self.opening_repair = OpeningRepairService(
                self.repository, self.repository.opening_repair
            )

    def bind_llm_task(self) -> None:
        gateway = self.service.gateway
        begin = getattr(gateway, "begin_task", None)
        if callable(begin):
            begin()


class NovelAgentHandler(BaseHTTPRequestHandler):
    server_version = "NovelAgent/0.1"
    context: AppContext

    def log_message(self, format: str, *args: object) -> None:
        print(f"[api] {self.address_string()} - {format % args}")

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self._cors_headers()
        self.end_headers()

    def do_GET(self) -> None:
        try:
            self.context.bind_llm_task()
            path = urlsplit(self.path).path
            params = self._query_params()
            assert self.context.analytics is not None
            analytics_result = dispatch_analytics_get(
                path, params, self.context.analytics
            )
            if analytics_result is not None:
                self._send_json(analytics_result.payload, analytics_result.status)
                return
            assert self.context.projects is not None
            projects_result = dispatch_projects_get(
                path, params, self.context.projects
            )
            if projects_result is not None:
                self._send_json(projects_result.payload, projects_result.status)
                return
            assert self.context.story_design is not None
            story_result = dispatch_story_design_get(
                path, params, self.context.story_design
            )
            if story_result is not None:
                self._send_json(story_result.payload, story_result.status)
                return
            if self.context.opening_repair is not None:
                repair_result = dispatch_opening_repair_get(
                    path, self.context.opening_repair
                )
                if repair_result is not None:
                    self._send_json(repair_result.payload, repair_result.status)
                    return
            if self.context.llm_settings is not None:
                llm_result = dispatch_llm_settings_get(path, self.context.llm_settings)
                if llm_result is not None:
                    self._send_json(llm_result.payload, llm_result.status)
                    return
            if path == "/api/health":
                self._send_json(
                    {
                        "status": "ok",
                        "version": "0.1.0",
                        "mode": self.context.settings.mode,
                        "database": "ready",
                        "apis": self._runtime_readiness(),
                    }
                )
                return
            if path == "/api/tags":
                self._send_json(public_tag_catalog())
                return
            match = re.fullmatch(r"/api/novels/([^/]+)/chapters", path)
            if match:
                self._send_json({"items": self.context.repository.list_chapters(match.group(1))})
                return
            match = re.fullmatch(r"/api/novels/([^/]+)/chapters/(\d+)/versions", path)
            if match:
                self._send_json(
                    {
                        "items": self.context.repository.list_chapter_versions(
                            match.group(1), int(match.group(2))
                        )
                    }
                )
                return
            match = re.fullmatch(r"/api/novels/([^/]+)/chapters/(\d+)/workspace", path)
            if match:
                self._send_json(
                    self.context.service.get_chapter_workspace(
                        match.group(1), int(match.group(2))
                    )
                )
                return
            match = re.fullmatch(
                r"/api/novels/([^/]+)/chapters/(\d+)/assistant/sessions", path
            )
            if match:
                self._send_json(
                    {
                        "items": self.context.service.list_assistant_sessions(
                            match.group(1), int(match.group(2))
                        )
                    }
                )
                return
            match = re.fullmatch(r"/api/assistant/sessions/([^/]+)/messages", path)
            if match:
                self._send_json(
                    {
                        "items": self.context.service.get_assistant_messages(
                            match.group(1)
                        )
                    }
                )
                return
            match = re.fullmatch(r"/api/assistant/sessions/([^/]+)/changes", path)
            if match:
                self._send_json(
                    {
                        "items": self.context.service.list_assistant_changes(
                            match.group(1)
                        )
                    }
                )
                return
            match = re.fullmatch(r"/api/novels/([^/]+)/characters", path)
            if match:
                self._send_json({"items": self.context.repository.list_characters(match.group(1))})
                return
            match = re.fullmatch(r"/api/novels/([^/]+)/world", path)
            if match:
                project_id = match.group(1)
                self._send_json(
                    {
                        "facts": self.context.repository.list_world_facts(project_id),
                        "timeline": self.context.repository.list_timeline(project_id),
                    }
                )
                return
            match = re.fullmatch(r"/api/novels/([^/]+)/research", path)
            if match:
                self._send_json(
                    {"items": self.context.repository.list_research_sources(match.group(1))}
                )
                return
            match = re.fullmatch(r"/api/runs/([^/]+)/events", path)
            if match:
                self._send_sse(self.context.repository.list_events(match.group(1)))
                return
            if path == "/api/settings":
                prefs = {
                    key: value
                    for key, value in self.context.repository.list_settings().items()
                    if not str(key).startswith("llm.")
                }
                self._send_json(
                    {
                        "runtime": self._runtime_readiness(),
                        "preferences": prefs,
                    }
                )
                return
            if path == "/api/usage":
                self._send_json(self.context.service.get_usage())
                return
            if path == "/api/publishing":
                self._send_json(
                    {
                        "provider": self.context.settings.publisher_provider,
                        "mode": "mock-only",
                        "real_publish_enabled": False,
                        "message": "真实番茄发布适配器未实现，避免账号与平台风险。",
                    }
                )
                return
            self._serve_static(path)
        except Exception as exc:
            self._handle_error(exc)

    def do_POST(self) -> None:
        try:
            self.context.bind_llm_task()
            path = self.path.split("?", 1)[0]
            payload = self._read_json()
            if self.context.llm_settings is not None:
                llm_result = dispatch_llm_settings_post(
                    path, payload, self.context.llm_settings
                )
                if llm_result is not None:
                    self._send_json(llm_result.payload, llm_result.status)
                    return
            assert self.context.story_design is not None
            story_result = dispatch_story_design_post(
                path, payload, self.context.story_design
            )
            if story_result is not None:
                self._send_json(story_result.payload, story_result.status)
                return
            assert self.context.projects is not None
            projects_result = dispatch_projects_post(
                path, payload, self.context.projects
            )
            if projects_result is not None:
                self._send_json(projects_result.payload, projects_result.status)
                return
            if self.context.opening_repair is not None:
                repair_result = dispatch_opening_repair_post(
                    path, payload, self.context.opening_repair
                )
                if repair_result is not None:
                    self._send_json(repair_result.payload, repair_result.status)
                    return
            match = re.fullmatch(r"/api/novels/([^/]+)/runs", path)
            if match:
                project_id = match.group(1)
                count = max(1, min(int(payload.get("count", 1)), 10))
                results = []
                for _ in range(count):
                    result = self.context.service.generate_next_chapter(project_id)
                    results.append(result)
                    if result.chapter.status == ChapterStatus.FAILED:
                        break
                self._send_json({"items": results})
                return
            match = re.fullmatch(r"/api/novels/([^/]+)/characters/rebuild", path)
            if match:
                self._send_json(
                    self.context.service.rebuild_character_archives(match.group(1))
                )
                return
            match = re.fullmatch(r"/api/novels/([^/]+)/semantic-search", path)
            if match:
                self._send_json(
                    {
                        "items": self.context.service.semantic_search(
                            match.group(1),
                            str(payload.get("query", "")),
                            int(payload.get("limit", 6)),
                        )
                    }
                )
                return
            match = re.fullmatch(r"/api/novels/([^/]+)/chapters/(\d+)/rework", path)
            if match:
                project_id = match.group(1)
                chapter_number = int(match.group(2))
                feedback = str(payload.get("feedback", "")).strip()[:2000]
                mode = str(payload.get("mode", "auto")).strip() or "auto"
                self._send_json(
                    self.context.service.rework_chapter(
                        project_id, chapter_number, feedback=feedback, mode=mode
                    )
                )
                return
            match = re.fullmatch(
                r"/api/novels/([^/]+)/chapters/(\d+)/review-submit", path
            )
            if match:
                request = ChapterRevisionCommitRequest.model_validate(payload)
                payload_out = self.context.service.submit_failed_chapter_review(
                    match.group(1), int(match.group(2)), request
                )
                self._send_json(payload_out, HTTPStatus.OK)
                return
            match = re.fullmatch(
                r"/api/novels/([^/]+)/chapters/(\d+)/accept-with-warnings", path
            )
            if match:
                request = ChapterAcceptWithWarningsRequest.model_validate(payload)
                payload_out = self.context.service.accept_failed_chapter_with_warnings(
                    match.group(1), int(match.group(2)), request
                )
                self._send_json(payload_out, HTTPStatus.OK)
                return
            match = re.fullmatch(r"/api/novels/([^/]+)/chapters/(\d+)/revisions", path)
            if match:
                request = ChapterRevisionCommitRequest.model_validate(payload)
                self._send_json(
                    self.context.service.commit_chapter_edit_draft(
                        match.group(1), int(match.group(2)), request
                    )
                )
                return
            match = re.fullmatch(
                r"/api/novels/([^/]+)/chapters/(\d+)/versions/(\d+)/restore", path
            )
            if match:
                self._send_json(
                    self.context.service.restore_chapter_version(
                        match.group(1), int(match.group(2)), int(match.group(3))
                    )
                )
                return
            match = re.fullmatch(
                r"/api/novels/([^/]+)/chapters/(\d+)/assistant/sessions", path
            )
            if match:
                self._send_json(
                    self.context.service.create_assistant_session(
                        match.group(1), int(match.group(2))
                    ),
                    HTTPStatus.CREATED,
                )
                return
            match = re.fullmatch(r"/api/assistant/sessions/([^/]+)/messages", path)
            if match:
                request = AssistantMessageCreate.model_validate(payload)
                self._send_json(
                    self.context.service.send_assistant_message(match.group(1), request)
                )
                return
            match = re.fullmatch(r"/api/assistant/sessions/([^/]+)/rollback", path)
            if match:
                request = AssistantRollbackRequest.model_validate(payload)
                self._send_json(
                    self.context.service.rollback_assistant_session(
                        match.group(1),
                        to_message_id=request.to_message_id,
                        expected_draft_hash=request.expected_draft_hash,
                    )
                )
                return
            match = re.fullmatch(r"/api/assistant/changes/([^/]+)/approve", path)
            if match:
                self._send_json(
                    self.context.service.approve_assistant_change(match.group(1))
                )
                return
            match = re.fullmatch(r"/api/assistant/changes/([^/]+)/reject", path)
            if match:
                self._send_json(
                    self.context.service.reject_assistant_change(match.group(1))
                )
                return
            self._send_json({"error": "NOT_FOUND", "message": "接口不存在"}, HTTPStatus.NOT_FOUND)
        except Exception as exc:
            self._handle_error(exc)

    def do_PUT(self) -> None:
        try:
            self.context.bind_llm_task()
            path = self.path.split("?", 1)[0]
            payload = self._read_json()
            if self.context.llm_settings is not None:
                llm_result = dispatch_llm_settings_put(
                    path, payload, self.context.llm_settings
                )
                if llm_result is not None:
                    self._send_json(llm_result.payload, llm_result.status)
                    return
            assert self.context.projects is not None
            projects_result = dispatch_projects_put(
                path, payload, self.context.projects
            )
            if projects_result is not None:
                self._send_json(projects_result.payload, projects_result.status)
                return
            assert self.context.story_design is not None
            story_result = dispatch_story_design_put(
                path, payload, self.context.story_design
            )
            if story_result is not None:
                self._send_json(story_result.payload, story_result.status)
                return
            match = re.fullmatch(r"/api/novels/([^/]+)/chapters/(\d+)/edit-draft", path)
            if match:
                update = ChapterDraftUpdate.model_validate(payload)
                self._send_json(
                    self.context.service.save_chapter_edit_draft(
                        match.group(1), int(match.group(2)), update
                    )
                )
                return
            if path != "/api/settings":
                self._send_json({"error": "NOT_FOUND", "message": "接口不存在"}, HTTPStatus.NOT_FOUND)
                return
            allowed = {"daily_chapters", "reserve_target", "debug_mode", "budget_limit"}
            for key, value in payload.items():
                if key not in allowed:
                    raise ValueError(f"设置项不可写：{key}")
                self.context.repository.save_setting(key, value)
            prefs = {
                key: value
                for key, value in self.context.repository.list_settings().items()
                if not str(key).startswith("llm.")
            }
            self._send_json(
                {
                    "preferences": prefs,
                    "runtime": self._runtime_readiness(),
                }
            )
        except Exception as exc:
            self._handle_error(exc)

    def do_DELETE(self) -> None:
        try:
            self.context.bind_llm_task()
            path = self.path.split("?", 1)[0]
            if self.context.llm_settings is not None:
                llm_result = dispatch_llm_settings_delete(path, self.context.llm_settings)
                if llm_result is not None:
                    self._send_json(llm_result.payload, llm_result.status)
                    return
            match = re.fullmatch(r"/api/novels/([^/]+)/chapters/(\d+)/edit-draft", path)
            if match:
                self.context.service.discard_chapter_edit_draft(
                    match.group(1), int(match.group(2))
                )
                self._send_json({"deleted": True})
                return
            match = re.fullmatch(r"/api/assistant/sessions/([^/]+)", path)
            if match:
                self.context.service.delete_assistant_session(match.group(1))
                self._send_json({"deleted": True, "session_id": match.group(1)})
                return
            payload = self._read_json()
            assert self.context.projects is not None
            projects_result = dispatch_projects_delete(
                path, payload, self.context.projects
            )
            if projects_result is not None:
                self._send_json(projects_result.payload, projects_result.status)
                return
            self._send_json(
                {"error": "NOT_FOUND", "message": "接口不存在"},
                HTTPStatus.NOT_FOUND,
            )
        except Exception as exc:
            self._handle_error(exc)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length > 1_000_000:
            raise ValueError("请求体过大")
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _query_params(self) -> dict[str, str]:
        query = parse_qs(urlsplit(self.path).query, keep_blank_values=True)
        return {key: values[-1] if values else "" for key, values in query.items()}

    def _runtime_readiness(self) -> dict[str, dict[str, object]]:
        runtime = self.context.settings.api_readiness()
        if self.context.llm_settings is not None:
            runtime["llm"] = self.context.llm_settings.runtime_card()
        runtime["story_skills"] = self.context.service.story_skills.readiness()
        runtime["oh_story"] = self.context.service.writing_skills.readiness()
        return runtime

    def _send_json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(_jsonable(payload), ensure_ascii=False).encode("utf-8")
        try:
            self.send_response(status)
            self._cors_headers()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as exc:
            if _is_client_disconnect(exc):
                return
            raise

    def _send_sse(self, events: list[Any]) -> None:
        lines: list[str] = []
        for event in events:
            lines.append(f"id: {event.id}")
            lines.append("event: workflow")
            lines.append(
                "data: "
                + json.dumps(_jsonable(event), ensure_ascii=False, separators=(",", ":"))
            )
            lines.append("")
        body = ("\n".join(lines) + "\n").encode("utf-8")
        try:
            self.send_response(HTTPStatus.OK)
            self._cors_headers()
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as exc:
            if _is_client_disconnect(exc):
                return
            raise

    def _serve_static(self, path: str) -> None:
        relative = "index.html" if path in {"/", ""} else path.lstrip("/")
        target = (self.context.web_root / relative).resolve()
        if self.context.web_root.resolve() not in target.parents and target != self.context.web_root.resolve():
            self._send_json({"error": "INVALID_PATH"}, HTTPStatus.BAD_REQUEST)
            return
        asset_suffixes = {
            ".js",
            ".css",
            ".map",
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".webp",
            ".svg",
            ".ico",
            ".woff",
            ".woff2",
        }
        if not target.is_file():
            suffix = Path(relative).suffix.lower()
            if suffix in asset_suffixes:
                self.send_error(HTTPStatus.NOT_FOUND, "Not Found")
                return
            target = self.context.web_root / "index.html"
        body = target.read_bytes()
        try:
            self.send_response(HTTPStatus.OK)
            content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            if target.suffix.lower() == ".js":
                content_type = "text/javascript; charset=utf-8"
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            if target.name == "index.html":
                self.send_header("Cache-Control", "no-store, max-age=0")
            elif "/assets/" in relative.replace("\\", "/") or target.suffix.lower() in {
                ".js",
                ".css",
                ".woff",
                ".woff2",
                ".svg",
                ".png",
                ".jpg",
                ".jpeg",
                ".webp",
            }:
                self.send_header("Cache-Control", "public, max-age=31536000, immutable")
            self.end_headers()
            self.wfile.write(body)
        except Exception as exc:
            if _is_client_disconnect(exc):
                return
            raise

    def _cors_headers(self) -> None:
        origin = self.headers.get("Origin", "").rstrip("/")
        host = self.headers.get("Host", "")
        if origin and host and origin in {f"http://{host}", f"https://{host}"}:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,OPTIONS")

    def _handle_error(self, exc: Exception) -> None:
        if _is_client_disconnect(exc):
            return
        status = HTTPStatus.INTERNAL_SERVER_ERROR
        error = type(exc).__name__
        message = str(exc)
        details: Any = None
        if isinstance(exc, ValidationError):
            status = HTTPStatus.UNPROCESSABLE_ENTITY
            error = "VALIDATION_ERROR"
            details = exc.errors(include_url=False)
        elif isinstance(exc, LLMSettingsError):
            mapped = llm_settings_error_result(exc)
            status = mapped.status
            error = exc.code
            message = exc.message
            details = None
        elif isinstance(exc, ChapterNotEditableError):
            status = HTTPStatus.CONFLICT
            error = "CHAPTER_NOT_EDITABLE"
        elif isinstance(exc, ChapterActionNotAllowedError):
            status = HTTPStatus.CONFLICT
            error = getattr(exc, "code", None) or "CHAPTER_ACTION_NOT_ALLOWED"
            details = getattr(exc, "details", None)
        elif isinstance(exc, QualityOverrideNotAllowedError):
            status = HTTPStatus.CONFLICT
            error = exc.code
            details = getattr(exc, "details", None)
        elif isinstance(exc, OpeningRepairError):
            status = getattr(exc, "status", HTTPStatus.CONFLICT)
            error = getattr(exc, "code", None) or "OPENING_REPAIR_NOT_ELIGIBLE"
            details = getattr(exc, "details", None)
        elif isinstance(exc, ReworkModeNotAllowedError):
            status = HTTPStatus.CONFLICT
            error = exc.code
            details = getattr(exc, "details", None)
        elif isinstance(exc, EditConflictError):
            status = HTTPStatus.CONFLICT
            error = "EDIT_CONFLICT"
        elif isinstance(exc, AssistantChangeStaleError):
            status = HTTPStatus.CONFLICT
            error = "ASSISTANT_CHANGE_STALE"
        elif isinstance(exc, AssistantChangeStateError):
            status = HTTPStatus.CONFLICT
            error = "ASSISTANT_CHANGE_STATE"
        elif isinstance(exc, RevisionAnalysisError):
            status = HTTPStatus.UNPROCESSABLE_ENTITY
            error = "REVISION_ANALYSIS_FAILED"
        elif isinstance(exc, RequirementConflict):
            status = HTTPStatus.CONFLICT
            error = "REQUIREMENT_CONFLICT"
            details = exc.conflicts
        elif isinstance(exc, AnalyticsValidationError):
            status = HTTPStatus.BAD_REQUEST
            error = "BAD_REQUEST"
        elif isinstance(exc, RepositoryError):
            message = str(exc)
            if any(
                marker in message
                for marker in ("非法", "必须", "不能早于", "只能是")
            ):
                status = HTTPStatus.BAD_REQUEST
                error = "BAD_REQUEST"
            else:
                status = HTTPStatus.NOT_FOUND
                error = "NOT_FOUND"
        elif isinstance(exc, ValueError):
            status = HTTPStatus.BAD_REQUEST
            error = "BAD_REQUEST"
        elif isinstance(exc, WorkflowBlocked):
            status = HTTPStatus.CONFLICT
            error = getattr(exc, "code", None) or "WORKFLOW_BLOCKED"
            details = getattr(exc, "details", None)
        elif isinstance(exc, (ValueError, json.JSONDecodeError)):
            status = HTTPStatus.BAD_REQUEST
            error = "BAD_REQUEST"
        elif isinstance(exc, APIConfigurationRequired):
            status = HTTPStatus.SERVICE_UNAVAILABLE
            error = "LLM_NOT_CONFIGURED" if "尚未配置" in str(exc) else "API_NOT_CONFIGURED"
        elif isinstance(exc, LLMAuthenticationError):
            status = HTTPStatus.BAD_GATEWAY
            error = "LLM_AUTH_ERROR"
        elif isinstance(exc, LLMRateLimitError):
            status = HTTPStatus.TOO_MANY_REQUESTS
            error = "LLM_RATE_LIMITED"
        elif isinstance(exc, LLMTimeoutError):
            status = HTTPStatus.GATEWAY_TIMEOUT
            error = "LLM_TIMEOUT"
        elif isinstance(exc, LLMResponseError):
            status = HTTPStatus.BAD_GATEWAY
            error = "LLM_RESPONSE_ERROR"
        elif isinstance(exc, LLMProviderError):
            status = HTTPStatus.BAD_GATEWAY
            error = "LLM_PROVIDER_ERROR"
        else:
            traceback.print_exc()
        try:
            self._send_json({"error": error, "message": message, "details": details}, status)
        except Exception as send_exc:
            if _is_client_disconnect(send_exc):
                return
            raise


def serve(context: AppContext) -> None:
    index = context.web_root / "index.html"
    if not index.is_file():
        raise SystemExit(
            "前端构建产物缺失：找不到 apps/web/dist/index.html。\n"
            "请先执行：\n"
            "  cd apps/web\n"
            "  npm ci\n"
            "  npm run build\n"
            "然后再运行 python -m novel_agent serve"
        )
    handler = type("ConfiguredNovelAgentHandler", (NovelAgentHandler,), {"context": context})
    server = ThreadingHTTPServer((context.settings.host, context.settings.port), handler)
    print(f"Novel Agent 已启动：http://{context.settings.host}:{context.settings.port}")
    print(f"运行模式：{context.settings.mode}；模型适配器：{context.service.gateway.name}")
    print(f"静态站点：{context.web_root}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n正在停止 Novel Agent…")
    finally:
        server.server_close()

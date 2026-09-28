from __future__ import annotations

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

from novel_agent.adapters import APIConfigurationRequired
from novel_agent.adapters_remote import (
    LLMAuthenticationError,
    LLMProviderError,
    LLMRateLimitError,
    LLMResponseError,
    LLMTimeoutError,
)
from novel_agent.config import Settings
from novel_agent.models import (
    AssistantMessageCreate,
    AssistantRollbackRequest,
    BriefRegenerateRequest,
    ChapterDraftUpdate,
    ChapterRevisionCommitRequest,
    ChapterStatus,
    CreativeBrief,
    NovelCreateRequest,
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
    settings: Settings
    service: NovelAgentService
    repository: SQLiteRepository
    web_root: Path


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
            path = self.path.split("?", 1)[0]
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
            if path == "/api/novels":
                self._send_json({"items": self.context.repository.list_projects()})
                return
            match = re.fullmatch(r"/api/novels/([^/]+)", path)
            if match:
                self._send_json(self.context.service.project_detail(match.group(1)))
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
            match = re.fullmatch(r"/api/novels/([^/]+)/brief-versions", path)
            if match:
                self._send_json(
                    {"items": self.context.repository.list_brief_versions(match.group(1))}
                )
                return
            match = re.fullmatch(r"/api/runs/([^/]+)/events", path)
            if match:
                self._send_sse(self.context.repository.list_events(match.group(1)))
                return
            if path == "/api/settings":
                self._send_json(
                    {
                        "runtime": self._runtime_readiness(),
                        "preferences": self.context.repository.list_settings(),
                    }
                )
                return
            if path == "/api/usage":
                self._send_json(self.context.service.get_usage())
                return
            if path == "/api/token/statistics":
                query = dict(
                    item.split("=", 1)
                    for item in self.path.split("?", 1)[1].split("&")
                    if "=" in item
                ) if "?" in self.path else {}
                self._send_json(
                    self.context.service.get_token_statistics(
                        start_date=query.get("start_date", ""),
                        end_date=query.get("end_date", ""),
                    )
                )
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
            if path == "/api/dashboard/writing":
                self._send_json(self._dashboard_writing())
                return
            if path == "/api/dashboard/llm-api/records":
                self._send_json(self._dashboard_llm_records())
                return
            if path == "/api/dashboard/llm-api/stats":
                self._send_json(self._dashboard_llm_stats())
                return
            self._serve_static(path)
        except Exception as exc:
            self._handle_error(exc)

    def do_POST(self) -> None:
        try:
            path = self.path.split("?", 1)[0]
            payload = self._read_json()
            if path == "/api/novels":
                request = NovelCreateRequest.model_validate(payload)
                self._send_json(self.context.service.create_novel(request), HTTPStatus.CREATED)
                return
            match = re.fullmatch(r"/api/novels/([^/]+)/(confirm|pause|resume|recover)", path)
            if match:
                project_id, action = match.groups()
                method = {
                    "confirm": self.context.service.confirm_novel,
                    "pause": self.context.service.pause_novel,
                    "resume": self.context.service.resume_novel,
                    "recover": self.context.service.recover_known_issue,
                }[action]
                self._send_json(method(project_id))
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
            match = re.fullmatch(r"/api/novels/([^/]+)/brief-regenerate", path)
            if match:
                change = BriefRegenerateRequest.model_validate(payload)
                self._send_json(
                    self.context.service.regenerate_draft_brief(match.group(1), change)
                )
                return
            match = re.fullmatch(r"/api/novels/([^/]+)/brief-restore", path)
            if match:
                self._send_json(
                    self.context.service.restore_draft_brief(
                        match.group(1), int(payload.get("version", 0))
                    )
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
                self._send_json(
                    self.context.service.rework_chapter(
                        project_id, chapter_number, feedback=feedback
                    )
                )
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
            path = self.path.split("?", 1)[0]
            payload = self._read_json()
            match = re.fullmatch(r"/api/novels/([^/]+)/brief", path)
            if match:
                brief = CreativeBrief.model_validate(payload)
                self._send_json(
                    self.context.service.update_draft_brief(match.group(1), brief)
                )
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
            self._send_json({"preferences": self.context.repository.list_settings()})
        except Exception as exc:
            self._handle_error(exc)

    def do_DELETE(self) -> None:
        try:
            path = self.path.split("?", 1)[0]
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
            match = re.fullmatch(r"/api/novels/([^/]+)", path)
            if not match:
                self._send_json(
                    {"error": "NOT_FOUND", "message": "接口不存在"},
                    HTTPStatus.NOT_FOUND,
                )
                return
            payload = self._read_json()
            self.context.service.delete_novel(
                match.group(1),
                confirmation_title=str(payload.get("confirmation_title", "")).strip()
                or None,
            )
            self._send_json({"deleted": True, "project_id": match.group(1)})
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

    def _optional_query(self, params: dict[str, str], *keys: str) -> dict[str, str | None]:
        return {key: (params.get(key) or None) for key in keys}

    def _dashboard_writing(self) -> dict[str, Any]:
        params = self._query_params()
        return self.context.repository.get_writing_dashboard(
            project_id=params.get("project_id") or None,
            source=params.get("source") or None,
            start_at=params.get("start_at") or None,
            end_at=params.get("end_at") or None,
            timezone_name=params.get("timezone") or "UTC",
        )

    def _dashboard_llm_stats(self) -> dict[str, Any]:
        params = self._query_params()
        return self.context.repository.get_llm_dashboard_stats(
            project_id=params.get("project_id") or None,
            model_provider=params.get("model_provider") or None,
            model_id=params.get("model_id") or None,
            category=params.get("category") or None,
            operation=params.get("operation") or None,
            status=params.get("status") or None,
            start_at=params.get("start_at") or None,
            end_at=params.get("end_at") or None,
        )

    def _dashboard_llm_records(self) -> dict[str, Any]:
        params = self._query_params()
        page = int(params.get("page") or "1")
        page_size = int(params.get("page_size") or "20")
        return self.context.repository.list_llm_call_records(
            project_id=params.get("project_id") or None,
            model_provider=params.get("model_provider") or None,
            model_id=params.get("model_id") or None,
            category=params.get("category") or None,
            operation=params.get("operation") or None,
            status=params.get("status") or None,
            start_at=params.get("start_at") or None,
            end_at=params.get("end_at") or None,
            search=params.get("search") or None,
            page=page,
            page_size=page_size,
            sort_by=params.get("sort_by") or "created_at",
            sort_order=params.get("sort_order") or "desc",
        )

    def _runtime_readiness(self) -> dict[str, dict[str, object]]:
        runtime = self.context.settings.api_readiness()
        runtime["story_skills"] = self.context.service.story_skills.readiness()
        runtime["oh_story"] = self.context.service.writing_skills.readiness()
        return runtime

    def _send_json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(_jsonable(payload), ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self._cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

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
        self.send_response(HTTPStatus.OK)
        self._cors_headers()
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_static(self, path: str) -> None:
        relative = "index.html" if path in {"/", ""} else path.lstrip("/")
        target = (self.context.web_root / relative).resolve()
        if self.context.web_root.resolve() not in target.parents and target != self.context.web_root.resolve():
            self._send_json({"error": "INVALID_PATH"}, HTTPStatus.BAD_REQUEST)
            return
        if not target.is_file():
            target = self.context.web_root / "index.html"
        body = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        if target.suffix.lower() in {".js", ".css", ".html"}:
            self.send_header("Cache-Control", "no-store, max-age=0")
        self.end_headers()
        self.wfile.write(body)

    def _cors_headers(self) -> None:
        origin = self.headers.get("Origin", "").rstrip("/")
        host = self.headers.get("Host", "")
        if origin and host and origin in {f"http://{host}", f"https://{host}"}:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,OPTIONS")

    def _handle_error(self, exc: Exception) -> None:
        status = HTTPStatus.INTERNAL_SERVER_ERROR
        error = type(exc).__name__
        message = str(exc)
        details: Any = None
        if isinstance(exc, ValidationError):
            status = HTTPStatus.UNPROCESSABLE_ENTITY
            error = "VALIDATION_ERROR"
            details = exc.errors(include_url=False)
        elif isinstance(exc, ChapterNotEditableError):
            status = HTTPStatus.CONFLICT
            error = "CHAPTER_NOT_EDITABLE"
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
            error = "WORKFLOW_BLOCKED"
        elif isinstance(exc, (ValueError, json.JSONDecodeError)):
            status = HTTPStatus.BAD_REQUEST
            error = "BAD_REQUEST"
        elif isinstance(exc, APIConfigurationRequired):
            status = HTTPStatus.SERVICE_UNAVAILABLE
            error = "API_NOT_CONFIGURED"
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
        self._send_json({"error": error, "message": message, "details": details}, status)


def serve(context: AppContext) -> None:
    handler = type("ConfiguredNovelAgentHandler", (NovelAgentHandler,), {"context": context})
    server = ThreadingHTTPServer((context.settings.host, context.settings.port), handler)
    print(f"Novel Agent 已启动：http://{context.settings.host}:{context.settings.port}")
    print(f"运行模式：{context.settings.mode}；模型适配器：{context.service.gateway.name}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n正在停止 Novel Agent…")
    finally:
        server.server_close()

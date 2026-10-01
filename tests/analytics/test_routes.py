from __future__ import annotations

import json
import tempfile
import unittest
from http import HTTPStatus
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from novel_agent.integrations.llm.offline import OfflineLLMGateway
from novel_agent.integrations.search.disabled import DisabledSearchAdapter
from novel_agent.api import AppContext, NovelAgentHandler
from novel_agent.config import Settings
from novel_agent.features.analytics.errors import AnalyticsValidationError
from novel_agent.features.analytics.models import (
    LLMRecordsQuery,
    LLMStatsQuery,
    WritingDashboardQuery,
)
from novel_agent.features.analytics.service import AnalyticsService
from novel_agent.interfaces.http.routes.analytics import dispatch_analytics_get
from novel_agent.repository import SQLiteRepository
from novel_agent.service import NovelAgentService


class RecordingAnalyticsService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []

    def get_token_statistics(self, start_date: str, end_date: str) -> dict[str, Any]:
        self.calls.append(("get_token_statistics", (start_date, end_date)))
        return {"dates": [], "total_tokens": [], "today_tokens": 0}

    def get_writing_dashboard(self, query: WritingDashboardQuery) -> dict[str, Any]:
        self.calls.append(("get_writing_dashboard", query))
        return {"summary": {"active_days": 0, "creative_chapters": 0}, "time_series": []}

    def get_llm_dashboard_stats(self, query: LLMStatsQuery) -> dict[str, Any]:
        self.calls.append(("get_llm_dashboard_stats", query))
        return {"summary": {"calls_total": 0}, "options": {}}

    def list_llm_call_records(self, query: LLMRecordsQuery) -> dict[str, Any]:
        self.calls.append(("list_llm_call_records", query))
        return {
            "options": {},
            "records": {
                "items": [],
                "total": 0,
                "page": query.page,
                "page_size": query.page_size,
            },
        }


class AnalyticsRouteDispatchTests(unittest.TestCase):
    def test_unmatched_path_returns_none(self) -> None:
        service = RecordingAnalyticsService()
        self.assertIsNone(dispatch_analytics_get("/api/usage", {}, service))  # type: ignore[arg-type]
        self.assertEqual(service.calls, [])

    def test_token_statistics_and_defaults(self) -> None:
        service = RecordingAnalyticsService()
        result = dispatch_analytics_get(
            "/api/token/statistics",
            {"start_date": "2026-09-01", "end_date": "2026-09-30"},
            service,  # type: ignore[arg-type]
        )
        assert result is not None
        self.assertEqual(result.status, HTTPStatus.OK)
        self.assertEqual(
            service.calls[0],
            ("get_token_statistics", ("2026-09-01", "2026-09-30")),
        )

    def test_writing_and_llm_queries_are_constructed(self) -> None:
        service = RecordingAnalyticsService()
        writing = dispatch_analytics_get(
            "/api/dashboard/writing",
            {
                "project_id": "novel_a",
                "source": "agent",
                "timezone": "Asia/Shanghai",
                "start_at": "2026-09-01T00:00:00Z",
            },
            service,  # type: ignore[arg-type]
        )
        stats = dispatch_analytics_get(
            "/api/dashboard/llm-api/stats",
            {"model_id": "deepseek-v4-pro", "status": "success"},
            service,  # type: ignore[arg-type]
        )
        records = dispatch_analytics_get(
            "/api/dashboard/llm-api/records",
            {"search": "a%20b", "page": "", "page_size": ""},
            service,  # type: ignore[arg-type]
        )
        assert writing is not None and stats is not None and records is not None
        writing_query = service.calls[0][1]
        assert isinstance(writing_query, WritingDashboardQuery)
        self.assertEqual(writing_query.project_id, "novel_a")
        self.assertEqual(writing_query.timezone_name, "Asia/Shanghai")
        records_query = service.calls[2][1]
        assert isinstance(records_query, LLMRecordsQuery)
        self.assertEqual(records_query.page, 1)
        self.assertEqual(records_query.page_size, 20)

    def test_invalid_page_raises_validation_error(self) -> None:
        service = RecordingAnalyticsService()
        with self.assertRaises(AnalyticsValidationError):
            dispatch_analytics_get(
                "/api/dashboard/llm-api/records",
                {"page": "abc"},
                service,  # type: ignore[arg-type]
            )


class AnalyticsRouteHttpTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        root = Path(self._tmpdir.name)
        web = root / "apps" / "web"
        web.mkdir(parents=True)
        (web / "index.html").write_text("<html></html>", encoding="utf-8")
        repository = SQLiteRepository(root / "data" / "test.db")
        service = NovelAgentService(
            repository=repository,
            gateway=OfflineLLMGateway(),
            search=DisabledSearchAdapter(),
        )
        settings = Settings.load(Path.cwd())
        self.context = AppContext(
            settings,
            service,
            repository,
            web,
            analytics=AnalyticsService(repository.analytics),
        )
        self.handler_cls = type(
            "Handler",
            (NovelAgentHandler,),
            {"context": self.context},
        )

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _get(self, path: str) -> tuple[int, dict]:
        class FakeHandler(self.handler_cls):  # type: ignore[misc,valid-type]
            def __init__(self) -> None:
                self.path = path
                self.request_version = "HTTP/1.1"
                self.headers = {}
                self._status = 200
                self._body = b""

            def send_response(self, code: int, message: str | None = None) -> None:
                self._status = int(code) if not isinstance(code, HTTPStatus) else int(code)

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

        fake = FakeHandler()
        fake.do_GET()
        return fake._status, json.loads(fake._body.decode("utf-8"))

    def test_urlsplit_parse_qs_handles_encoded_search(self) -> None:
        raw = "/api/dashboard/llm-api/records?search=%25_%5C&sort_by=created_at"
        params = parse_qs(urlsplit(raw).query, keep_blank_values=True)
        self.assertEqual(params["search"][0], "%_\\")
        status, payload = self._get(raw)
        self.assertEqual(status, 200)
        self.assertEqual(payload["records"]["total"], 0)

    def test_invalid_integer_date_timezone_source_sort_return_400(self) -> None:
        cases = [
            ("/api/dashboard/llm-api/records?page=nope", "page 必须是整数"),
            ("/api/dashboard/llm-api/records?page_size=x", "page_size 必须是整数"),
            ("/api/dashboard/writing?start_at=not-a-date", "非法日期时间"),
            ("/api/dashboard/writing?timezone=Mars/Olympus", "非法时区"),
            ("/api/dashboard/writing?source=robot", "非法来源筛选"),
            ("/api/dashboard/llm-api/records?sort_by=evil", "非法排序字段"),
            ("/api/dashboard/llm-api/records?sort_order=sideways", "sort_order 只能是"),
        ]
        for path, marker in cases:
            status, payload = self._get(path)
            self.assertEqual(status, 400, path)
            self.assertEqual(payload["error"], "BAD_REQUEST", path)
            self.assertIn(marker, payload["message"], path)

    def test_handler_does_not_call_repository_dashboard_facade(self) -> None:
        called: list[str] = []

        def boom(*_args: Any, **_kwargs: Any) -> Any:
            called.append("repository")
            raise AssertionError("route must not use repository analytics facade")

        self.context.repository.get_writing_dashboard = boom  # type: ignore[method-assign]
        self.context.repository.get_llm_dashboard_stats = boom  # type: ignore[method-assign]
        self.context.repository.list_llm_call_records = boom  # type: ignore[method-assign]
        self.context.repository.get_token_statistics = boom  # type: ignore[method-assign]
        for path in (
            "/api/dashboard/writing",
            "/api/dashboard/llm-api/stats",
            "/api/dashboard/llm-api/records",
            "/api/token/statistics?start_date=2026-09-01&end_date=2026-09-30",
        ):
            status, _payload = self._get(path)
            self.assertEqual(status, 200, path)
        self.assertEqual(called, [])


if __name__ == "__main__":
    unittest.main()

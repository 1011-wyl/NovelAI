from __future__ import annotations

import tempfile
import unittest
from http import HTTPStatus
from pathlib import Path

from novel_agent.integrations.llm.offline import OfflineLLMGateway
from novel_agent.integrations.search.disabled import DisabledSearchAdapter
from novel_agent.api import AppContext, NovelAgentHandler, _is_client_disconnect
from novel_agent.config import Settings
from novel_agent.features.analytics.service import AnalyticsService
from novel_agent.repository import SQLiteRepository
from novel_agent.service import NovelAgentService

REPO_ROOT = Path(__file__).resolve().parents[1]


class ClientDisconnectHelpersTests(unittest.TestCase):
    def test_detects_common_disconnect_exceptions(self) -> None:
        self.assertTrue(_is_client_disconnect(BrokenPipeError()))
        self.assertTrue(_is_client_disconnect(ConnectionResetError()))
        self.assertTrue(_is_client_disconnect(ConnectionAbortedError()))
        self.assertFalse(_is_client_disconnect(ValueError("not disconnect")))


class ClientDisconnectHttpTests(unittest.TestCase):
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

    def test_broken_pipe_during_json_write_does_not_send_second_error(self) -> None:
        writes = {"count": 0}

        class FakeHandler(self.handler_cls):  # type: ignore[misc,valid-type]
            def __init__(self) -> None:
                self.path = "/api/health"
                self.request_version = "HTTP/1.1"
                self.headers = {}
                self._status = 200
                self._error_calls = 0

            def send_response(self, code: int, message: str | None = None) -> None:
                self._status = int(code) if not isinstance(code, HTTPStatus) else int(code)

            def send_header(self, keyword: str, value: str) -> None:
                return None

            def end_headers(self) -> None:
                return None

            def _cors_headers(self) -> None:
                return None

            def _handle_error(self, exc: Exception) -> None:  # type: ignore[override]
                self._error_calls += 1
                super()._handle_error(exc)

            @property
            def wfile(self):  # noqa: ANN201
                class Writer:
                    def write(self, data: bytes) -> int:
                        writes["count"] += 1
                        raise BrokenPipeError()

                return Writer()

        fake = FakeHandler()
        fake.do_GET()
        self.assertEqual(writes["count"], 1)
        self.assertEqual(fake._error_calls, 0)


class AnalyticsAbortSourceTests(unittest.TestCase):
    def test_cancellable_getter_invalidates_inflight_generation(self) -> None:
        """Vue analytics uses createCancellableGetter; abort must bump generation."""
        http_client = (REPO_ROOT / "apps" / "web" / "src" / "api" / "http-client.ts").read_text(
            encoding="utf-8"
        )
        analytics_api = (
            REPO_ROOT / "apps" / "web" / "src" / "features" / "analytics" / "api" / "analytics.api.ts"
        ).read_text(encoding="utf-8")
        self.assertIn("createCancellableGetter", http_client)
        self.assertIn("generation += 1", http_client)
        abort_block = http_client.split("abort()", 1)[1].split("async run", 1)[0]
        self.assertIn("generation += 1", abort_block)
        self.assertIn("createCancellableGetter", analytics_api)
        self.assertIn("abortAnalyticsRequests", analytics_api)
        self.assertIn("writingHeroGetter.abort()", analytics_api)


if __name__ == "__main__":
    unittest.main()

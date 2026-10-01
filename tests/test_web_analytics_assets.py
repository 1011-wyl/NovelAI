from __future__ import annotations

import re
import tempfile
import unittest
from http import HTTPStatus
from pathlib import Path

from novel_agent.integrations.llm.offline import OfflineLLMGateway
from novel_agent.integrations.search.disabled import DisabledSearchAdapter
from novel_agent.api import AppContext, NovelAgentHandler
from novel_agent.config import Settings
from novel_agent.features.analytics.service import AnalyticsService
from novel_agent.repository import SQLiteRepository
from novel_agent.service import NovelAgentService


WEB_ROOT = Path(__file__).resolve().parents[1] / "apps" / "web"
ANALYTICS_IDS = (
    "analyticsTitle",
    "tabWriting",
    "tabLlm",
    "tabRecords",
    "writingPanel",
    "llmPanel",
    "recordsPanel",
    "writingHeatmap",
    "chartWritingTrend",
    "chartLlmCallTrend",
    "recordsTableBody",
    "recordsSearch",
)


class WebAnalyticsAssetTests(unittest.TestCase):
    def test_index_html_local_assets_exist_and_drop_legacy_dashboard(self) -> None:
        html = (WEB_ROOT / "index.html").read_text(encoding="utf-8")
        self.assertEqual(html.count('id="analyticsView"'), 1)
        self.assertNotIn("/dashboard.js", html)
        self.assertNotIn("/dashboard.css", html)
        self.assertIn("/styles/features/analytics.css", html)
        app_js = (WEB_ROOT / "app.js").read_text(encoding="utf-8")
        self.assertIn('import("/js/features/analytics/index.js")', app_js)
        self.assertNotIn("NovelDashboard", app_js)
        refs = re.findall(r'(?:href|src)="(/[^"?]+)', html)
        for ref in refs:
            if ref.startswith("/api/"):
                continue
            target = WEB_ROOT / ref.lstrip("/")
            self.assertTrue(target.is_file(), f"missing asset: {ref}")

    def test_analytics_template_contains_critical_ids_and_aria(self) -> None:
        template = (
            WEB_ROOT / "js" / "features" / "analytics" / "template.js"
        ).read_text(encoding="utf-8")
        for item in ANALYTICS_IDS:
            self.assertIn(f'id="{item}"', template)
        self.assertIn('role="tablist"', template)
        self.assertIn('role="tab"', template)
        self.assertIn('role="tabpanel"', template)
        self.assertIn('aria-selected="true"', template)
        self.assertIn('aria-controls="writingPanel"', template)

    def test_es_module_imports_stay_inside_web_root(self) -> None:
        js_root = WEB_ROOT / "js"
        for path in js_root.rglob("*.js"):
            text = path.read_text(encoding="utf-8")
            for match in re.finditer(
                r"""from\s+["']([^"']+)["']|import\s*\(\s*["']([^"']+)["']\s*\)""",
                text,
            ):
                spec = match.group(1) or match.group(2)
                if spec.startswith("http://") or spec.startswith("https://"):
                    self.fail(f"external import not allowed: {path} -> {spec}")
                if spec.startswith("/"):
                    target = (WEB_ROOT / spec.lstrip("/")).resolve()
                else:
                    target = (path.parent / spec).resolve()
                self.assertTrue(
                    str(target).startswith(str(WEB_ROOT.resolve())),
                    f"import escapes web root: {path} -> {spec}",
                )
                self.assertTrue(target.is_file(), f"missing module: {path} -> {spec}")


class StaticAssetHttpTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        root = Path(self._tmpdir.name)
        self.web = root / "apps" / "web"
        self.web.mkdir(parents=True)
        (self.web / "index.html").write_text("<html>fallback</html>", encoding="utf-8")
        (self.web / "exists.js").write_text("export const ok = 1;\n", encoding="utf-8")
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
            self.web,
            analytics=AnalyticsService(repository.analytics),
        )
        self.handler_cls = type(
            "Handler",
            (NovelAgentHandler,),
            {"context": self.context},
        )

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _get(self, path: str) -> tuple[int, bytes, dict[str, str]]:
        headers: dict[str, str] = {}

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
                headers[keyword.lower()] = value

            def end_headers(self) -> None:
                return None

            def send_error(self, code: int, message: str | None = None) -> None:
                self._status = int(code)
                payload = (message or "Not Found").encode("utf-8")
                self._body = payload
                headers["content-type"] = "text/html; charset=utf-8"
                headers["content-length"] = str(len(payload))

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
        return fake._status, fake._body, headers

    def test_missing_js_and_css_return_404_not_index_html(self) -> None:
        for path in ("/missing.js", "/styles/missing.css"):
            status, body, _headers = self._get(path)
            self.assertEqual(status, 404, path)
            self.assertNotIn(b"fallback", body)

    def test_existing_js_is_served_as_javascript(self) -> None:
        status, body, headers = self._get("/exists.js")
        self.assertEqual(status, 200)
        self.assertIn(b"export const ok", body)
        self.assertIn("javascript", headers.get("content-type", ""))


if __name__ == "__main__":
    unittest.main()

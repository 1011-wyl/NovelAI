"""Static frontend build and SPA fallback checks for Vue dist."""

from __future__ import annotations

import re
import tempfile
import unittest
from http import HTTPStatus
from pathlib import Path

from novel_agent.api import AppContext, NovelAgentHandler
from novel_agent.config import Settings
from novel_agent.integrations.llm.offline import OfflineLLMGateway
from novel_agent.integrations.search.disabled import DisabledSearchAdapter
from novel_agent.repository import SQLiteRepository
from novel_agent.service import NovelAgentService

REPO_ROOT = Path(__file__).resolve().parents[1]
DIST_ROOT = REPO_ROOT / "apps" / "web" / "dist"
DIST_BUILD_HINT = (
    "apps/web/dist/index.html missing. Build the SPA before Python SPA tests: "
    "cd apps/web && npm ci && npm run build "
    "(or run scripts/verify-frontend.ps1 from the repo root)."
)


def _require_dist_or_skip(test_case: unittest.TestCase) -> None:
    if (DIST_ROOT / "index.html").is_file():
        return
    # Controlled skip for fresh clones; CI / verify-frontend.ps1 must build first.
    test_case.skipTest(DIST_BUILD_HINT)


class VueDistAssetTests(unittest.TestCase):
    def test_dist_index_exists_and_is_minimal_spa_shell(self) -> None:
        _require_dist_or_skip(self)
        index = DIST_ROOT / "index.html"
        html = index.read_text(encoding="utf-8")
        self.assertIn('id="app"', html)
        self.assertNotIn("app.js", html)
        self.assertNotIn("reader-workspace.js", html)
        self.assertNotIn("__novelBasicSwitchView", html)
        self.assertRegex(html, r"/assets/[^\"']+\.js")
        self.assertTrue((DIST_ROOT / "favicon.ico").is_file(), "built dist should include favicon.ico")

    def test_hashed_assets_exist_beside_index(self) -> None:
        _require_dist_or_skip(self)
        html = (DIST_ROOT / "index.html").read_text(encoding="utf-8")
        refs = re.findall(r'(?:href|src)="(/assets/[^"?]+)', html)
        self.assertTrue(refs, "built index should reference /assets/*")
        for ref in refs:
            target = DIST_ROOT / ref.lstrip("/")
            self.assertTrue(target.is_file(), f"missing built asset: {ref}")


class VueSpaFallbackRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        _require_dist_or_skip(self)
        self._tmpdir = tempfile.TemporaryDirectory()
        root = Path(self._tmpdir.name)
        self.repository = SQLiteRepository(root / "spa.db")
        self.service = NovelAgentService(
            self.repository, OfflineLLMGateway(), DisabledSearchAdapter()
        )
        self.context = AppContext(
            Settings.load(REPO_ROOT),
            self.service,
            self.repository,
            DIST_ROOT,
        )

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _request(self, method: str, path: str) -> tuple[int, bytes, dict[str, str]]:
        headers: dict[str, str] = {}

        class FakeHandler(NovelAgentHandler):
            def __init__(self) -> None:
                self.command = method
                self.path = path
                self.headers = {"Content-Length": "0"}
                self.rfile = type("R", (), {"read": lambda _self, n: b""})()
                self.context = self_outer.context
                self.client_address = ("127.0.0.1", 0)
                self._status = 0
                self._body = b""

            def send_response(self, code: int, message: str | None = None) -> None:
                self._status = code

            def send_header(self, keyword: str, value: str) -> None:
                headers[keyword] = value

            def end_headers(self) -> None:
                return None

            def send_error(self, code: int, message: str | None = None) -> None:
                self._status = code
                self._body = (message or "Not Found").encode("utf-8")

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
        return fake._status, fake._body, headers

    def test_history_deep_link_returns_index_html(self) -> None:
        status, body, headers = self._request("GET", "/novels/demo/workbench")
        self.assertEqual(status, HTTPStatus.OK)
        self.assertIn(b'id="app"', body)
        self.assertIn("text/html", headers.get("Content-Type", ""))
        self.assertIn("no-store", headers.get("Cache-Control", ""))

    def test_missing_hashed_js_returns_404_not_html(self) -> None:
        status, body, headers = self._request("GET", "/assets/missing-chunk-abc123.js")
        self.assertEqual(status, HTTPStatus.NOT_FOUND)
        self.assertNotIn(b'id="app"', body)


if __name__ == "__main__":
    unittest.main()

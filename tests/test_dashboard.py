import json
import tempfile
import threading
import unittest
from http import HTTPStatus
from pathlib import Path

from novel_agent.integrations.llm.offline import OfflineLLMGateway
from novel_agent.integrations.search.disabled import DisabledSearchAdapter
from novel_agent.api import AppContext, NovelAgentHandler
from novel_agent.repository import DASHBOARD_MIGRATION_VERSION, SCHEMA_VERSION, SQLiteRepository
from novel_agent.service import NovelAgentService
from novel_agent.telemetry import LLMCallRecord, current_llm_context, llm_call_scope
from novel_agent.text_metrics import count_content_chars


class DashboardRepositoryTests(unittest.TestCase):
    def test_count_content_chars_skips_whitespace(self) -> None:
        self.assertEqual(count_content_chars("你好 世界\nABC"), 7)
        self.assertEqual(count_content_chars("  \n\t"), 0)

    def test_migration_is_idempotent_and_backfills_once(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / "dash.db"
            repository = SQLiteRepository(db)
            with repository.connection() as conn:
                conn.execute(
                    """INSERT INTO projects
                    (id,title,status,request_json,brief_json,confirmed,current_chapter,created_at,updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?)""",
                    (
                        "novel_1",
                        "测试书",
                        "ACTIVE",
                        "{}",
                        "{}",
                        1,
                        1,
                        "2026-01-01T00:00:00Z",
                        "2026-01-01T00:00:00Z",
                    ),
                )
                conn.execute(
                    """INSERT INTO chapters
                    (id,project_id,number,title,status,content,summary,version,locked,created_at,updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        "chapter_1",
                        "novel_1",
                        1,
                        "第一章",
                        "READY",
                        "正文内容一二三",
                        "摘要",
                        1,
                        0,
                        "2026-01-01T00:00:00Z",
                        "2026-01-02T08:00:00Z",
                    ),
                )
                conn.execute(
                    "DELETE FROM schema_migrations WHERE version=?",
                    (DASHBOARD_MIGRATION_VERSION,),
                )
            repository.migrate()
            repository.migrate()
            with repository.connection() as conn:
                count = conn.execute(
                    "SELECT COUNT(*) AS c FROM writing_activity_events WHERE operation='backfill'"
                ).fetchone()["c"]
                versions = {
                    int(row["version"])
                    for row in conn.execute("SELECT version FROM schema_migrations").fetchall()
                }
            self.assertEqual(count, 1)
            self.assertIn(SCHEMA_VERSION, versions)
            self.assertIn(DASHBOARD_MIGRATION_VERSION, versions)

    def test_writing_dashboard_groups_by_timezone(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            repository = SQLiteRepository(Path(folder) / "tz.db")
            repository.record_writing_activity(
                project_id="novel_a",
                chapter_id="c1",
                chapter_title="第一章",
                source="agent",
                operation="create",
                old_word_count=0,
                new_word_count=100,
                created_at="2026-09-27T16:30:00Z",
            )
            data = repository.get_writing_dashboard(
                timezone_name="Asia/Shanghai",
                start_at="2026-09-27T00:00:00+08:00",
                end_at="2026-09-28T23:59:59+08:00",
            )
            self.assertEqual(data["summary"]["active_days"], 1)
            self.assertEqual(data["time_series"][0]["date"], "2026-09-28")
            self.assertEqual(data["time_series"][0]["agent_word_delta"], 100)

    def test_llm_stats_and_records_filter_sort_search(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            repository = SQLiteRepository(Path(folder) / "llm.db")
            repository.record_llm_call(
                LLMCallRecord(
                    date="2026-09-28",
                    operation="write_chapter",
                    model="deepseek-v4-pro",
                    prompt_tokens=10,
                    completion_tokens=20,
                    total_tokens=30,
                    project_id="novel_a",
                    provider="deepseek",
                    status="success",
                    latency_ms=1200,
                )
            )
            repository.record_llm_call(
                LLMCallRecord(
                    date="2026-09-28",
                    operation="plan_chapter",
                    model="deepseek-v4-pro",
                    prompt_tokens=5,
                    completion_tokens=5,
                    total_tokens=10,
                    project_id="novel_a",
                    provider="deepseek",
                    status="failed",
                    latency_ms=800,
                    error_type="LLMTimeoutError",
                    error_message="timeout %_test",
                )
            )
            stats = repository.get_llm_dashboard_stats()
            self.assertEqual(stats["summary"]["calls_total"], 2)
            self.assertEqual(stats["summary"]["success_total"], 1)
            self.assertIsNone(stats["summary"]["avg_first_token_ms"])
            records = repository.list_llm_call_records(
                search="%_",
                sort_by="latency_ms",
                sort_order="asc",
                page=1,
                page_size=20,
            )
            self.assertEqual(records["records"]["total"], 1)
            self.assertEqual(records["records"]["items"][0]["status"], "failed")
            with self.assertRaises(Exception):
                repository.list_llm_call_records(sort_by="drop table")

    def test_llm_scope_is_context_local(self) -> None:
        seen: dict[str, str | None] = {}

        def worker(project_id: str, key: str) -> None:
            with llm_call_scope(project_id=project_id):
                seen[key] = current_llm_context().project_id

        threads = [
            threading.Thread(target=worker, args=("novel_a", "a")),
            threading.Thread(target=worker, args=("novel_b", "b")),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(seen["a"], "novel_a")
        self.assertEqual(seen["b"], "novel_b")


class DashboardApiTests(unittest.TestCase):
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
        from novel_agent.config import Settings

        settings = Settings.load(Path.cwd())
        self.context = AppContext(settings, service, repository, web)
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

    def test_dashboard_endpoints_empty_ok(self) -> None:
        status, payload = self._get("/api/dashboard/writing?timezone=Asia/Shanghai")
        self.assertEqual(status, 200)
        self.assertEqual(payload["summary"]["active_days"], 0)
        status, payload = self._get("/api/dashboard/llm-api/stats")
        self.assertEqual(status, 200)
        self.assertEqual(payload["summary"]["calls_total"], 0)
        status, payload = self._get("/api/dashboard/llm-api/records")
        self.assertEqual(status, 200)
        self.assertEqual(payload["records"]["total"], 0)

    def test_invalid_sort_returns_400(self) -> None:
        status, payload = self._get("/api/dashboard/llm-api/records?sort_by=evil")
        self.assertEqual(status, 400)
        self.assertIn("非法排序字段", payload["message"])


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from novel_agent.integrations.llm.offline import OfflineLLMGateway
from novel_agent.integrations.search.disabled import DisabledSearchAdapter
from novel_agent.api import AppContext
from novel_agent.config import Settings
from novel_agent.features.analytics.service import AnalyticsService
from novel_agent.repository import SQLiteRepository
from novel_agent.service import NovelAgentService


class AnalyticsCompatibilityTests(unittest.TestCase):
    def test_app_context_four_positional_args_still_wire_analytics(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            web = root / "web"
            web.mkdir()
            repository = SQLiteRepository(root / "db.sqlite")
            service = NovelAgentService(
                repository=repository,
                gateway=OfflineLLMGateway(),
                search=DisabledSearchAdapter(),
            )
            context = AppContext(Settings.load(Path.cwd()), service, repository, web)
            self.assertIsInstance(context.analytics, AnalyticsService)
            payload = context.analytics.get_token_statistics(  # type: ignore[union-attr]
                "2026-09-01", "2026-09-30"
            )
            self.assertIn("today_tokens", payload)
            self.assertIn("avg_daily", payload)

    def test_novel_agent_service_token_statistics_matches_analytics_service(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            repository = SQLiteRepository(Path(folder) / "compat.db")
            repository.save_token_usage("2026-09-28", "plan", "model", 10, 20, 30)
            repository.save_token_usage("2026-09-29", "write", "model", 5, 5, 10)
            service = NovelAgentService(
                repository=repository,
                gateway=OfflineLLMGateway(),
                search=DisabledSearchAdapter(),
            )
            analytics = AnalyticsService(
                repository.analytics,
                today=lambda: date(2026, 9, 30),
            )
            via_service = service.get_token_statistics("2026-09-28", "2026-09-29")
            via_analytics = analytics.get_token_statistics("2026-09-28", "2026-09-29")
            # Facade uses default today clock; compare shared period fields.
            for key in (
                "dates",
                "total_tokens",
                "period_tokens",
                "avg_daily",
                "max_date",
                "max_tokens",
                "total_calls",
                "total_retries",
            ):
                self.assertEqual(via_service[key], via_analytics[key], key)


if __name__ == "__main__":
    unittest.main()

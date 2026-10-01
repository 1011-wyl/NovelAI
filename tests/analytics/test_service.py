from __future__ import annotations

import unittest
from datetime import date
from typing import Any

from novel_agent.features.analytics.models import (
    LLMRecordsQuery,
    LLMStatsQuery,
    WritingDashboardQuery,
)
from novel_agent.features.analytics.service import AnalyticsService


class FakeAnalyticsStore:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.token_stats = {
            "dates": ["2026-09-28", "2026-09-29"],
            "total_tokens": [10, 40],
            "input_tokens": [4, 16],
            "output_tokens": [6, 24],
        }
        self.period_summary = {
            "total_tokens": 50,
            "total_input": 20,
            "total_output": 30,
            "total_calls": 3,
            "total_retries": 1,
            "days": 2,
        }
        self.today_summary = {
            "total_tokens": 7,
            "total_input": 3,
            "total_output": 4,
            "total_calls": 1,
            "total_retries": 0,
            "days": 1,
        }

    def get_token_statistics(self, start_date: str, end_date: str) -> dict[str, Any]:
        self.calls.append(("get_token_statistics", (start_date, end_date)))
        return self.token_stats

    def get_token_daily_summary(self, start_date: str, end_date: str) -> dict[str, Any]:
        self.calls.append(("get_token_daily_summary", (start_date, end_date)))
        if start_date == end_date == "2026-09-30":
            return self.today_summary
        return self.period_summary

    def get_writing_dashboard(self, query: WritingDashboardQuery) -> dict[str, Any]:
        self.calls.append(("get_writing_dashboard", query))
        return {"summary": {"active_days": 0, "creative_chapters": 0}, "time_series": []}

    def get_llm_dashboard_stats(self, query: LLMStatsQuery) -> dict[str, Any]:
        self.calls.append(("get_llm_dashboard_stats", query))
        return {"summary": {"calls_total": 0}}

    def list_llm_call_records(self, query: LLMRecordsQuery) -> dict[str, Any]:
        self.calls.append(("list_llm_call_records", query))
        return {"records": {"items": [], "total": 0, "page": query.page, "page_size": query.page_size}}


class AnalyticsServiceTests(unittest.TestCase):
    def test_token_statistics_combines_period_today_and_peak(self) -> None:
        store = FakeAnalyticsStore()
        service = AnalyticsService(store, today=lambda: date(2026, 9, 30))
        payload = service.get_token_statistics("2026-09-28", "2026-09-29")
        self.assertEqual(payload["today_tokens"], 7)
        self.assertEqual(payload["period_tokens"], 50)
        self.assertEqual(payload["avg_daily"], 25)
        self.assertEqual(payload["max_date"], "2026-09-29")
        self.assertEqual(payload["max_tokens"], 40)
        self.assertEqual(payload["total_calls"], 3)
        self.assertEqual(payload["total_retries"], 1)
        self.assertEqual(
            [name for name, _ in store.calls],
            [
                "get_token_statistics",
                "get_token_daily_summary",
                "get_token_daily_summary",
            ],
        )

    def test_empty_stats_have_zero_peak_and_average(self) -> None:
        store = FakeAnalyticsStore()
        store.token_stats = {
            "dates": [],
            "total_tokens": [],
            "input_tokens": [],
            "output_tokens": [],
        }
        store.period_summary = {
            "total_tokens": 0,
            "total_input": 0,
            "total_output": 0,
            "total_calls": 0,
            "total_retries": 0,
            "days": 0,
        }
        store.today_summary = store.period_summary
        service = AnalyticsService(store, today=lambda: date(2026, 9, 30))
        payload = service.get_token_statistics("2026-09-01", "2026-09-30")
        self.assertEqual(payload["avg_daily"], 0)
        self.assertEqual(payload["max_date"], "")
        self.assertEqual(payload["max_tokens"], 0)

    def test_query_methods_delegate_to_store(self) -> None:
        store = FakeAnalyticsStore()
        service = AnalyticsService(store)
        writing = WritingDashboardQuery(project_id="p1", timezone_name="Asia/Shanghai")
        stats = LLMStatsQuery(model_id="deepseek-v4-pro")
        records = LLMRecordsQuery(page=2, page_size=10, sort_by="latency_ms")
        service.get_writing_dashboard(writing)
        service.get_llm_dashboard_stats(stats)
        service.list_llm_call_records(records)
        self.assertEqual(store.calls[0], ("get_writing_dashboard", writing))
        self.assertEqual(store.calls[1], ("get_llm_dashboard_stats", stats))
        self.assertEqual(store.calls[2], ("list_llm_call_records", records))


if __name__ == "__main__":
    unittest.main()

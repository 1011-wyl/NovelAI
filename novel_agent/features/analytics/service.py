from __future__ import annotations

from datetime import date
from typing import Any, Callable

from novel_agent.features.analytics.models import (
    LLMRecordsQuery,
    LLMStatsQuery,
    WritingDashboardQuery,
)
from novel_agent.features.analytics.ports import AnalyticsQueryStore


class AnalyticsService:
    """Application entry for database-backed analytics queries."""

    def __init__(
        self,
        store: AnalyticsQueryStore,
        *,
        today: Callable[[], date] = date.today,
    ) -> None:
        self._store = store
        self._today = today

    def get_token_statistics(self, start_date: str, end_date: str) -> dict[str, Any]:
        stats = self._store.get_token_statistics(start_date, end_date)
        summary = self._store.get_token_daily_summary(start_date, end_date)
        today = self._today().strftime("%Y-%m-%d")
        today_summary = self._store.get_token_daily_summary(today, today)
        max_date = ""
        max_tokens = 0
        for index, day in enumerate(stats["dates"]):
            if stats["total_tokens"][index] > max_tokens:
                max_tokens = stats["total_tokens"][index]
                max_date = day
        avg_daily = summary["total_tokens"] // max(summary["days"], 1)
        return {
            **stats,
            "today_tokens": today_summary["total_tokens"],
            "period_tokens": summary["total_tokens"],
            "avg_daily": avg_daily,
            "max_date": max_date,
            "max_tokens": max_tokens,
            "total_calls": summary["total_calls"],
            "total_retries": summary["total_retries"],
        }

    def get_writing_dashboard(self, query: WritingDashboardQuery) -> dict[str, Any]:
        return self._store.get_writing_dashboard(query)

    def get_llm_dashboard_stats(self, query: LLMStatsQuery) -> dict[str, Any]:
        return self._store.get_llm_dashboard_stats(query)

    def list_llm_call_records(self, query: LLMRecordsQuery) -> dict[str, Any]:
        return self._store.list_llm_call_records(query)

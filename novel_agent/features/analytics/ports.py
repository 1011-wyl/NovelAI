from __future__ import annotations

from typing import Any, Protocol

from novel_agent.features.analytics.models import (
    LLMRecordsQuery,
    LLMStatsQuery,
    WritingDashboardQuery,
)
from novel_agent.telemetry import LLMCallRecord


class AnalyticsRecorder(Protocol):
    def save_token_usage(
        self,
        date: str,
        operation: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        retry_count: int = 0,
        **extra: Any,
    ) -> None: ...

    def record_llm_call(self, record: LLMCallRecord) -> None: ...

    def record_writing_activity(
        self,
        *,
        project_id: str,
        chapter_id: str | None,
        chapter_title: str | None,
        source: str,
        operation: str,
        old_word_count: int,
        new_word_count: int,
        run_id: str | None = None,
        created_at: str | None = None,
        conn: Any | None = None,
    ) -> None: ...


class AnalyticsQueryStore(Protocol):
    def get_token_statistics(self, start_date: str, end_date: str) -> dict[str, Any]: ...

    def get_token_daily_summary(self, start_date: str, end_date: str) -> dict[str, Any]: ...

    def get_writing_dashboard(self, query: WritingDashboardQuery) -> dict[str, Any]: ...

    def get_llm_dashboard_stats(self, query: LLMStatsQuery) -> dict[str, Any]: ...

    def list_llm_call_records(self, query: LLMRecordsQuery) -> dict[str, Any]: ...

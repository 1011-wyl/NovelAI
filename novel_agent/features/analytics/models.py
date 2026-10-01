from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DateRange:
    start_at: str | None = None
    end_at: str | None = None


@dataclass(frozen=True, slots=True)
class WritingDashboardQuery:
    project_id: str | None = None
    source: str | None = None
    start_at: str | None = None
    end_at: str | None = None
    timezone_name: str = "UTC"


@dataclass(frozen=True, slots=True)
class LLMStatsQuery:
    project_id: str | None = None
    model_provider: str | None = None
    model_id: str | None = None
    category: str | None = None
    operation: str | None = None
    status: str | None = None
    start_at: str | None = None
    end_at: str | None = None


@dataclass(frozen=True, slots=True)
class LLMRecordsQuery(LLMStatsQuery):
    search: str | None = None
    page: int = 1
    page_size: int = 20
    sort_by: str = "created_at"
    sort_order: str = "desc"

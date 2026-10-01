from __future__ import annotations

from dataclasses import asdict, dataclass
from http import HTTPStatus
from typing import Any, Mapping

from novel_agent.features.analytics.errors import AnalyticsValidationError
from novel_agent.features.analytics.models import (
    LLMRecordsQuery,
    LLMStatsQuery,
    WritingDashboardQuery,
)
from novel_agent.features.analytics.service import AnalyticsService

ANALYTICS_GET_PATHS = frozenset(
    {
        "/api/token/statistics",
        "/api/dashboard/writing",
        "/api/dashboard/llm-api/stats",
        "/api/dashboard/llm-api/records",
    }
)


@dataclass(frozen=True, slots=True)
class RouteResult:
    payload: Any
    status: HTTPStatus = HTTPStatus.OK


def dispatch_analytics_get(
    path: str,
    params: Mapping[str, str],
    service: AnalyticsService,
) -> RouteResult | None:
    """Handle Analytics GET routes; return None when path is outside this module."""
    if path not in ANALYTICS_GET_PATHS:
        return None
    if path == "/api/token/statistics":
        return RouteResult(
            service.get_token_statistics(
                start_date=params.get("start_date", ""),
                end_date=params.get("end_date", ""),
            )
        )
    if path == "/api/dashboard/writing":
        return RouteResult(
            service.get_writing_dashboard(
                WritingDashboardQuery(
                    project_id=_optional(params, "project_id"),
                    source=_optional(params, "source"),
                    start_at=_optional(params, "start_at"),
                    end_at=_optional(params, "end_at"),
                    timezone_name=params.get("timezone") or "UTC",
                )
            )
        )
    if path == "/api/dashboard/llm-api/stats":
        return RouteResult(service.get_llm_dashboard_stats(_llm_stats_query(params)))
    return RouteResult(
        service.list_llm_call_records(
            LLMRecordsQuery(
                **asdict(_llm_stats_query(params)),
                search=_optional(params, "search"),
                page=_parse_int(params.get("page"), default=1, field="page"),
                page_size=_parse_int(
                    params.get("page_size"), default=20, field="page_size"
                ),
                sort_by=params.get("sort_by") or "created_at",
                sort_order=params.get("sort_order") or "desc",
            )
        )
    )


def _optional(params: Mapping[str, str], key: str) -> str | None:
    return params.get(key) or None


def _parse_int(value: str | None, *, default: int, field: str) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise AnalyticsValidationError(f"{field} 必须是整数") from exc


def _llm_stats_query(params: Mapping[str, str]) -> LLMStatsQuery:
    return LLMStatsQuery(
        project_id=_optional(params, "project_id"),
        model_provider=_optional(params, "model_provider"),
        model_id=_optional(params, "model_id"),
        category=_optional(params, "category"),
        operation=_optional(params, "operation"),
        status=_optional(params, "status"),
        start_at=_optional(params, "start_at"),
        end_at=_optional(params, "end_at"),
    )

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from novel_agent.features.analytics.errors import AnalyticsError, AnalyticsValidationError
from novel_agent.features.analytics.models import (
    LLMRecordsQuery,
    LLMStatsQuery,
    WritingDashboardQuery,
)
from novel_agent.infrastructure.persistence.database import DatabaseSessionProvider
from novel_agent.models import utc_now
from novel_agent.telemetry import LLMCallRecord

_FIXED_TIMEZONES: dict[str, timezone] = {
    "UTC": timezone.utc,
    "Etc/UTC": timezone.utc,
    "Asia/Shanghai": timezone(timedelta(hours=8)),
    "Asia/Chongqing": timezone(timedelta(hours=8)),
    "Asia/Hong_Kong": timezone(timedelta(hours=8)),
    "Asia/Taipei": timezone(timedelta(hours=8)),
    "Asia/Singapore": timezone(timedelta(hours=8)),
    "Asia/Tokyo": timezone(timedelta(hours=9)),
    "America/New_York": timezone(timedelta(hours=-5)),
    "America/Los_Angeles": timezone(timedelta(hours=-8)),
    "Europe/London": timezone.utc,
    "Europe/Paris": timezone(timedelta(hours=1)),
}


class SQLiteAnalyticsStore:
    """SQLite-backed analytics recorder and dashboard query store."""

    def __init__(self, database: DatabaseSessionProvider):
        self._database = database

    @staticmethod
    def _required_row(row: sqlite3.Row | None, operation: str) -> sqlite3.Row:
        if row is None:
            raise AnalyticsError(f"数据库查询未返回结果：{operation}")
        return row

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
    ) -> None:
        record = LLMCallRecord(
            date=date,
            operation=operation,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            retry_count=retry_count,
            project_id=extra.get("project_id"),
            chapter_id=extra.get("chapter_id"),
            run_id=extra.get("run_id"),
            category=str(extra.get("category") or "agent"),
            provider=extra.get("provider"),
            status=str(extra.get("status") or "success"),
            latency_ms=extra.get("latency_ms"),
            first_token_ms=extra.get("first_token_ms"),
            cache_tokens=int(extra.get("cache_tokens") or 0),
            error_type=extra.get("error_type"),
            error_message=extra.get("error_message"),
            error_status_code=extra.get("error_status_code"),
        )
        self.record_llm_call(record)

    def record_llm_call(self, record: LLMCallRecord) -> None:
        with self._database.transaction() as conn:
            conn.execute(
                """INSERT INTO token_usage
                (date, operation, model, prompt_tokens, completion_tokens,
                 total_tokens, retry_count, created_at, project_id, chapter_id,
                 run_id, category, provider, status, latency_ms, first_token_ms,
                 cache_tokens, error_type, error_message, error_status_code)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    record.date,
                    record.operation,
                    record.model,
                    record.prompt_tokens,
                    record.completion_tokens,
                    record.total_tokens,
                    record.retry_count,
                    utc_now(),
                    record.project_id,
                    record.chapter_id,
                    record.run_id,
                    record.category or "agent",
                    record.provider,
                    record.status or "success",
                    record.latency_ms,
                    record.first_token_ms,
                    record.cache_tokens,
                    record.error_type,
                    record.error_message,
                    record.error_status_code,
                ),
            )

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
        conn: sqlite3.Connection | None = None,
    ) -> None:
        if source not in {"user", "agent", "import"}:
            raise AnalyticsValidationError(f"非法写作来源：{source}")
        payload = (
            created_at or utc_now(),
            project_id,
            chapter_id,
            chapter_title,
            source,
            operation,
            max(0, int(old_word_count)),
            max(0, int(new_word_count)),
            int(new_word_count) - int(old_word_count),
            run_id,
        )
        sql = """INSERT INTO writing_activity_events
            (created_at, project_id, chapter_id, chapter_title, source, operation,
             old_word_count, new_word_count, word_delta, run_id)
            VALUES (?,?,?,?,?,?,?,?,?,?)"""
        if conn is not None:
            # Join caller transaction; never begin/commit when conn is provided.
            conn.execute(sql, payload)
            return
        with self._database.transaction() as owned:
            owned.execute(sql, payload)

    def get_token_statistics(self, start_date: str, end_date: str) -> dict[str, Any]:
        with self._database.connection() as conn:
            rows = conn.execute(
                """SELECT date,
                   SUM(prompt_tokens) AS prompt_tokens,
                   SUM(completion_tokens) AS completion_tokens,
                   SUM(total_tokens) AS total_tokens,
                   COUNT(*) AS request_count,
                   SUM(retry_count) AS retry_count
                FROM token_usage
                WHERE date >= ? AND date <= ?
                GROUP BY date
                ORDER BY date""",
                (start_date, end_date),
            ).fetchall()
        dates: list[str] = []
        total_tokens: list[int] = []
        input_tokens: list[int] = []
        output_tokens: list[int] = []
        for row in rows:
            dates.append(row["date"])
            total_tokens.append(int(row["total_tokens"]))
            input_tokens.append(int(row["prompt_tokens"]))
            output_tokens.append(int(row["completion_tokens"]))
        return {
            "dates": dates,
            "total_tokens": total_tokens,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        }

    def get_token_daily_summary(self, start_date: str, end_date: str) -> dict[str, Any]:
        with self._database.connection() as conn:
            row = self._required_row(
                conn.execute(
                    """SELECT COUNT(DISTINCT date) AS days,
                       SUM(total_tokens) AS total,
                       SUM(prompt_tokens) AS prompt,
                       SUM(completion_tokens) AS completion,
                       COUNT(*) AS calls,
                       SUM(retry_count) AS retries
                    FROM token_usage
                    WHERE date >= ? AND date <= ?""",
                    (start_date, end_date),
                ).fetchone(),
                "汇总令牌用量",
            )
        return {
            "total_tokens": int(row["total"] or 0),
            "total_input": int(row["prompt"] or 0),
            "total_output": int(row["completion"] or 0),
            "total_calls": int(row["calls"] or 0),
            "total_retries": int(row["retries"] or 0),
            "days": int(row["days"] or 0),
        }

    @staticmethod
    def _parse_timezone(name: str) -> Any:
        key = (name or "UTC").strip() or "UTC"
        try:
            return ZoneInfo(key)
        except ZoneInfoNotFoundError:
            fixed = _FIXED_TIMEZONES.get(key)
            if fixed is not None:
                return fixed
            raise AnalyticsValidationError(f"非法时区：{name}") from None

    @staticmethod
    def _parse_iso_datetime(value: str | None) -> datetime | None:
        if not value:
            return None
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError as exc:
            raise AnalyticsValidationError(f"非法日期时间：{value}") from exc
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    @staticmethod
    def _local_date(iso_created_at: str, tz: Any) -> str:
        text = iso_created_at.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            parsed = datetime.strptime(text[:19], "%Y-%m-%dT%H:%M:%S").replace(
                tzinfo=timezone.utc
            )
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(tz).strftime("%Y-%m-%d")

    def get_writing_dashboard(self, query: WritingDashboardQuery) -> dict[str, Any]:
        tz = self._parse_timezone(query.timezone_name)
        start_dt = self._parse_iso_datetime(query.start_at)
        end_dt = self._parse_iso_datetime(query.end_at)
        if start_dt and end_dt and end_dt < start_dt:
            raise AnalyticsValidationError("结束时间不能早于开始时间")
        if query.source and query.source not in {"user", "agent", "import"}:
            raise AnalyticsValidationError(f"非法来源筛选：{query.source}")
        clauses = ["1=1"]
        params: list[Any] = []
        if query.project_id:
            clauses.append("project_id = ?")
            params.append(query.project_id)
        if query.source:
            clauses.append("source = ?")
            params.append(query.source)
        if start_dt:
            clauses.append("created_at >= ?")
            params.append(start_dt.isoformat().replace("+00:00", "Z"))
        if end_dt:
            clauses.append("created_at <= ?")
            params.append(end_dt.isoformat().replace("+00:00", "Z"))
        where = " AND ".join(clauses)
        with self._database.connection() as conn:
            rows = conn.execute(
                f"""SELECT created_at, source, word_delta, chapter_id
                FROM writing_activity_events
                WHERE {where}
                ORDER BY created_at""",
                params,
            ).fetchall()
        buckets: dict[str, dict[str, int]] = {}
        creative_chapters: set[str] = set()
        active_days: set[str] = set()
        for row in rows:
            day = self._local_date(row["created_at"], tz)
            bucket = buckets.setdefault(
                day,
                {"user_word_delta": 0, "agent_word_delta": 0, "import_word_delta": 0},
            )
            key = f"{row['source']}_word_delta"
            if key in bucket:
                bucket[key] += int(row["word_delta"] or 0)
            if row["source"] in {"user", "agent"}:
                active_days.add(day)
                if row["chapter_id"]:
                    creative_chapters.add(str(row["chapter_id"]))
        time_series = [{"date": day, **buckets[day]} for day in sorted(buckets.keys())]
        return {
            "summary": {
                "active_days": len(active_days),
                "creative_chapters": len(creative_chapters),
            },
            "time_series": time_series,
        }

    def get_dashboard_filter_options(self) -> dict[str, Any]:
        with self._database.connection() as conn:
            projects = conn.execute(
                """SELECT DISTINCT t.project_id AS value,
                          COALESCE(p.title, '') AS label
                   FROM token_usage t
                   LEFT JOIN projects p ON p.id = t.project_id
                   WHERE t.project_id IS NOT NULL AND t.project_id != ''
                   ORDER BY label, value"""
            ).fetchall()
            writing_projects = conn.execute(
                """SELECT DISTINCT e.project_id AS value,
                          COALESCE(p.title, '') AS label
                   FROM writing_activity_events e
                   LEFT JOIN projects p ON p.id = e.project_id
                   ORDER BY label, value"""
            ).fetchall()
            providers = [
                row["provider"]
                for row in conn.execute(
                    """SELECT DISTINCT provider FROM token_usage
                       WHERE provider IS NOT NULL AND provider != ''
                       ORDER BY provider"""
                ).fetchall()
            ]
            models = [
                row["model"]
                for row in conn.execute(
                    """SELECT DISTINCT model FROM token_usage
                       WHERE model IS NOT NULL AND model != ''
                       ORDER BY model"""
                ).fetchall()
            ]
            categories = [
                row["category"]
                for row in conn.execute(
                    """SELECT DISTINCT category FROM token_usage
                       WHERE category IS NOT NULL AND category != ''
                       ORDER BY category"""
                ).fetchall()
            ]
            operations = [
                row["operation"]
                for row in conn.execute(
                    """SELECT DISTINCT operation FROM token_usage
                       WHERE operation IS NOT NULL AND operation != ''
                       ORDER BY operation"""
                ).fetchall()
            ]
            statuses = [
                row["status"]
                for row in conn.execute(
                    """SELECT DISTINCT status FROM token_usage
                       WHERE status IS NOT NULL AND status != ''
                       ORDER BY status"""
                ).fetchall()
            ]
        project_map: dict[str, str] = {}
        for row in [*projects, *writing_projects]:
            value = str(row["value"])
            label = str(row["label"] or "").strip() or "未归属项目"
            project_map[value] = label
        project_options = [
            {"value": key, "label": project_map[key]} for key in sorted(project_map)
        ]
        return {
            "project_ids": [item["value"] for item in project_options],
            "model_providers": providers,
            "model_ids": models,
            "categories": categories,
            "operations": operations,
            "statuses": statuses,
            "project_options": project_options,
            "model_options": [{"value": model, "label": model} for model in models],
        }

    def _build_token_usage_filter(
        self,
        *,
        project_id: str | None = None,
        model_provider: str | None = None,
        model_id: str | None = None,
        category: str | None = None,
        operation: str | None = None,
        status: str | None = None,
        start_at: str | None = None,
        end_at: str | None = None,
        search: str | None = None,
        alias: str = "t",
    ) -> tuple[str, list[Any]]:
        start_dt = self._parse_iso_datetime(start_at)
        end_dt = self._parse_iso_datetime(end_at)
        if start_dt and end_dt and end_dt < start_dt:
            raise AnalyticsValidationError("结束时间不能早于开始时间")
        clauses = ["1=1"]
        params: list[Any] = []
        if project_id:
            clauses.append(f"{alias}.project_id = ?")
            params.append(project_id)
        if model_provider:
            clauses.append(f"{alias}.provider = ?")
            params.append(model_provider)
        if model_id:
            clauses.append(f"{alias}.model = ?")
            params.append(model_id)
        if category:
            clauses.append(f"{alias}.category = ?")
            params.append(category)
        if operation:
            clauses.append(f"{alias}.operation = ?")
            params.append(operation)
        if status:
            clauses.append(f"{alias}.status = ?")
            params.append(status)
        if start_dt:
            clauses.append(f"{alias}.created_at >= ?")
            params.append(start_dt.isoformat().replace("+00:00", "Z"))
        if end_dt:
            clauses.append(f"{alias}.created_at <= ?")
            params.append(end_dt.isoformat().replace("+00:00", "Z"))
        if search:
            escaped = (
                search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            )
            pattern = f"%{escaped}%"
            clauses.append(
                f"""(
                    {alias}.model LIKE ? ESCAPE '\\'
                    OR {alias}.operation LIKE ? ESCAPE '\\'
                    OR {alias}.category LIKE ? ESCAPE '\\'
                    OR COALESCE({alias}.error_type, '') LIKE ? ESCAPE '\\'
                    OR COALESCE({alias}.error_message, '') LIKE ? ESCAPE '\\'
                )"""
            )
            params.extend([pattern] * 5)
        return " AND ".join(clauses), params

    def get_llm_dashboard_stats(self, query: LLMStatsQuery) -> dict[str, Any]:
        where, params = self._build_token_usage_filter(
            project_id=query.project_id,
            model_provider=query.model_provider,
            model_id=query.model_id,
            category=query.category,
            operation=query.operation,
            status=query.status,
            start_at=query.start_at,
            end_at=query.end_at,
        )
        with self._database.connection() as conn:
            summary_row = self._required_row(
                conn.execute(
                    f"""SELECT COUNT(*) AS calls_total,
                           SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) AS success_total,
                           COALESCE(SUM(total_tokens), 0) AS tokens_total,
                           COALESCE(SUM(prompt_tokens), 0) AS tokens_input_total,
                           COALESCE(SUM(completion_tokens), 0) AS tokens_output_total,
                           AVG(latency_ms) AS avg_latency_ms,
                           AVG(first_token_ms) AS avg_first_token_ms
                        FROM token_usage t
                        WHERE {where}""",
                    params,
                ).fetchone(),
                "汇总 LLM 调用",
            )
            model_time_series = conn.execute(
                f"""SELECT substr(created_at, 1, 10) AS date,
                           model AS key,
                           model AS label,
                           COUNT(*) AS calls,
                           COALESCE(SUM(total_tokens), 0) AS tokens_total,
                           AVG(latency_ms) AS avg_latency_ms
                    FROM token_usage t
                    WHERE {where}
                    GROUP BY substr(created_at, 1, 10), model
                    ORDER BY date, key""",
                params,
            ).fetchall()
            by_model = conn.execute(
                f"""SELECT model AS key, model AS label,
                           COUNT(*) AS calls,
                           COALESCE(SUM(total_tokens), 0) AS tokens_total
                    FROM token_usage t
                    WHERE {where}
                    GROUP BY model
                    ORDER BY calls DESC, key""",
                params,
            ).fetchall()
            by_project = conn.execute(
                f"""SELECT COALESCE(t.project_id, '') AS key,
                           COALESCE(NULLIF(p.title, ''), '未归属项目') AS label,
                           COUNT(*) AS calls,
                           COALESCE(SUM(t.total_tokens), 0) AS tokens_total
                    FROM token_usage t
                    LEFT JOIN projects p ON p.id = t.project_id
                    WHERE {where}
                    GROUP BY COALESCE(t.project_id, ''), COALESCE(NULLIF(p.title, ''), '未归属项目')
                    ORDER BY calls DESC, label""",
                params,
            ).fetchall()
        avg_latency = summary_row["avg_latency_ms"]
        avg_first = summary_row["avg_first_token_ms"]
        return {
            "summary": {
                "calls_total": int(summary_row["calls_total"] or 0),
                "success_total": int(summary_row["success_total"] or 0),
                "tokens_total": int(summary_row["tokens_total"] or 0),
                "tokens_input_total": int(summary_row["tokens_input_total"] or 0),
                "tokens_output_total": int(summary_row["tokens_output_total"] or 0),
                "avg_latency_ms": float(avg_latency) if avg_latency is not None else None,
                "avg_first_token_ms": float(avg_first) if avg_first is not None else None,
            },
            "model_time_series": [
                {
                    "date": row["date"],
                    "key": row["key"],
                    "label": row["label"],
                    "calls": int(row["calls"]),
                    "tokens_total": int(row["tokens_total"]),
                    "avg_latency_ms": float(row["avg_latency_ms"])
                    if row["avg_latency_ms"] is not None
                    else None,
                }
                for row in model_time_series
            ],
            "by_model": [
                {
                    "key": row["key"],
                    "label": row["label"],
                    "calls": int(row["calls"]),
                    "tokens_total": int(row["tokens_total"]),
                }
                for row in by_model
            ],
            "by_project": [
                {
                    "key": row["key"] or "unassigned",
                    "label": row["label"],
                    "calls": int(row["calls"]),
                    "tokens_total": int(row["tokens_total"]),
                }
                for row in by_project
            ],
            "options": self.get_dashboard_filter_options(),
        }

    def list_llm_call_records(self, query: LLMRecordsQuery) -> dict[str, Any]:
        if query.page < 1:
            raise AnalyticsValidationError("page 必须大于等于 1")
        if query.page_size < 5 or query.page_size > 100:
            raise AnalyticsValidationError("page_size 必须在 5 到 100 之间")
        sort_map = {
            "created_at": "t.created_at",
            "tokens_input": "t.prompt_tokens",
            "tokens_output": "t.completion_tokens",
            "tokens_total": "t.total_tokens",
            "latency_ms": "t.latency_ms",
            "first_token_ms": "t.first_token_ms",
            "retry_count": "t.retry_count",
        }
        if query.sort_by not in sort_map:
            raise AnalyticsValidationError(f"非法排序字段：{query.sort_by}")
        if query.sort_order not in {"asc", "desc"}:
            raise AnalyticsValidationError("sort_order 只能是 asc 或 desc")
        where, params = self._build_token_usage_filter(
            project_id=query.project_id,
            model_provider=query.model_provider,
            model_id=query.model_id,
            category=query.category,
            operation=query.operation,
            status=query.status,
            start_at=query.start_at,
            end_at=query.end_at,
            search=query.search,
        )
        order_sql = f"{sort_map[query.sort_by]} {query.sort_order.upper()}, t.id DESC"
        offset = (query.page - 1) * query.page_size
        with self._database.connection() as conn:
            total_row = self._required_row(
                conn.execute(
                    f"SELECT COUNT(*) AS total FROM token_usage t WHERE {where}",
                    params,
                ).fetchone(),
                "统计调用记录总数",
            )
            rows = conn.execute(
                f"""SELECT t.id, t.created_at, t.project_id, p.title AS project_title,
                           t.chapter_id, t.category, t.operation, t.model AS model_id,
                           t.provider AS model_provider, t.prompt_tokens AS tokens_input,
                           t.completion_tokens AS tokens_output, t.total_tokens AS tokens_total,
                           t.cache_tokens AS token_cache, t.latency_ms, t.first_token_ms,
                           t.status, t.error_type, t.error_message, t.error_status_code,
                           t.retry_count
                    FROM token_usage t
                    LEFT JOIN projects p ON p.id = t.project_id
                    WHERE {where}
                    ORDER BY {order_sql}
                    LIMIT ? OFFSET ?""",
                [*params, query.page_size, offset],
            ).fetchall()
        items = [
            {
                "id": int(row["id"]),
                "created_at": row["created_at"],
                "project_id": row["project_id"],
                "project_title": row["project_title"],
                "chapter_id": row["chapter_id"],
                "category": row["category"],
                "operation": row["operation"],
                "model_id": row["model_id"],
                "model_provider": row["model_provider"],
                "tokens_input": int(row["tokens_input"] or 0),
                "tokens_output": int(row["tokens_output"] or 0),
                "tokens_total": int(row["tokens_total"] or 0),
                "token_cache": int(row["token_cache"] or 0),
                "latency_ms": row["latency_ms"],
                "first_token_ms": row["first_token_ms"],
                "status": row["status"],
                "error_type": row["error_type"],
                "error_message": row["error_message"],
                "error_status_code": row["error_status_code"],
                "retry_count": int(row["retry_count"] or 0),
            }
            for row in rows
        ]
        return {
            "options": self.get_dashboard_filter_options(),
            "records": {
                "items": items,
                "total": int(total_row["total"] or 0),
                "page": query.page,
                "page_size": query.page_size,
            },
        }

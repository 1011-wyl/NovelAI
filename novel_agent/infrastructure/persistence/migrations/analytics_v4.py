from __future__ import annotations

import sqlite3

from novel_agent.models import utc_now
from novel_agent.text_metrics import count_content_chars

DASHBOARD_MIGRATION_VERSION = 4


def apply_analytics_v4(conn: sqlite3.Connection) -> None:
    """Ensure Analytics tables/indexes exist and apply one-time writing backfill for v4."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS token_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            operation TEXT NOT NULL,
            model TEXT NOT NULL,
            prompt_tokens INTEGER NOT NULL DEFAULT 0,
            completion_tokens INTEGER NOT NULL DEFAULT 0,
            total_tokens INTEGER NOT NULL DEFAULT 0,
            retry_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            project_id TEXT,
            chapter_id TEXT,
            run_id TEXT,
            category TEXT NOT NULL DEFAULT 'agent',
            provider TEXT,
            status TEXT NOT NULL DEFAULT 'success',
            latency_ms INTEGER,
            first_token_ms INTEGER,
            cache_tokens INTEGER NOT NULL DEFAULT 0,
            error_type TEXT,
            error_message TEXT,
            error_status_code INTEGER
        );
        CREATE INDEX IF NOT EXISTS idx_token_usage_date
        ON token_usage(date);

        CREATE TABLE IF NOT EXISTS writing_activity_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            project_id TEXT NOT NULL,
            chapter_id TEXT,
            chapter_title TEXT,
            source TEXT NOT NULL CHECK(source IN ('user','agent','import')),
            operation TEXT NOT NULL,
            old_word_count INTEGER NOT NULL DEFAULT 0,
            new_word_count INTEGER NOT NULL DEFAULT 0,
            word_delta INTEGER NOT NULL DEFAULT 0,
            run_id TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_writing_activity_created
        ON writing_activity_events(created_at);
        CREATE INDEX IF NOT EXISTS idx_writing_activity_project_created
        ON writing_activity_events(project_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_writing_activity_source_created
        ON writing_activity_events(source, created_at);
        """
    )
    token_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(token_usage)").fetchall()
    }
    token_additions = {
        "project_id": "TEXT",
        "chapter_id": "TEXT",
        "run_id": "TEXT",
        "category": "TEXT NOT NULL DEFAULT 'agent'",
        "provider": "TEXT",
        "status": "TEXT NOT NULL DEFAULT 'success'",
        "latency_ms": "INTEGER",
        "first_token_ms": "INTEGER",
        "cache_tokens": "INTEGER NOT NULL DEFAULT 0",
        "error_type": "TEXT",
        "error_message": "TEXT",
        "error_status_code": "INTEGER",
    }
    for name, definition in token_additions.items():
        if name not in token_columns:
            conn.execute(f"ALTER TABLE token_usage ADD COLUMN {name} {definition}")
    conn.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_token_usage_created_at
        ON token_usage(created_at);
        CREATE INDEX IF NOT EXISTS idx_token_usage_project_created
        ON token_usage(project_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_token_usage_model_created
        ON token_usage(model, created_at);
        CREATE INDEX IF NOT EXISTS idx_token_usage_status_created
        ON token_usage(status, created_at);
        CREATE INDEX IF NOT EXISTS idx_token_usage_operation_created
        ON token_usage(operation, created_at);
        """
    )
    applied = {
        int(row["version"])
        for row in conn.execute("SELECT version FROM schema_migrations").fetchall()
    }
    if DASHBOARD_MIGRATION_VERSION not in applied:
        _backfill_writing_activity(conn)
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (DASHBOARD_MIGRATION_VERSION, utc_now()),
        )


def _backfill_writing_activity(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        """SELECT id, project_id, title, content, updated_at
        FROM chapters
        WHERE content IS NOT NULL AND TRIM(content) != ''
          AND NOT EXISTS (
            SELECT 1 FROM writing_activity_events e
            WHERE e.chapter_id = chapters.id AND e.operation = 'backfill'
          )"""
    ).fetchall()
    for row in rows:
        words = count_content_chars(row["content"])
        if words <= 0:
            continue
        conn.execute(
            """INSERT INTO writing_activity_events
            (created_at, project_id, chapter_id, chapter_title, source, operation,
             old_word_count, new_word_count, word_delta, run_id)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                row["updated_at"] or utc_now(),
                row["project_id"],
                row["id"],
                row["title"],
                "import",
                "backfill",
                0,
                words,
                words,
                None,
            ),
        )

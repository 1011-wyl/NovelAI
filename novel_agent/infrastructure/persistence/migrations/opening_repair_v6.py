from __future__ import annotations

import sqlite3

from novel_agent.models import utc_now

OPENING_REPAIR_MIGRATION_VERSION = 6


def apply_opening_repair_v6(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS project_repair_snapshots (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            kind TEXT NOT NULL,
            status TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            applied_at TEXT,
            rolled_back_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_repair_snapshots_project
        ON project_repair_snapshots(project_id, created_at);
        """
    )
    applied = {
        int(row["version"])
        for row in conn.execute("SELECT version FROM schema_migrations").fetchall()
    }
    if OPENING_REPAIR_MIGRATION_VERSION not in applied:
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (OPENING_REPAIR_MIGRATION_VERSION, utc_now()),
        )

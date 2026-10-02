"""SQLite brief-version store (read + narrow write helpers)."""

from __future__ import annotations

import sqlite3

from novel_agent.features.story_design.errors import BriefVersionNotFoundError
from novel_agent.features.story_design.models import CreativeBrief
from novel_agent.infrastructure.persistence.database import DatabaseSessionProvider
from novel_agent.infrastructure.persistence.json_util import dump_json


class SQLiteBriefsStore:
    def __init__(self, database: DatabaseSessionProvider):
        self._database = database

    @staticmethod
    def _required_row(row: sqlite3.Row | None, operation: str) -> sqlite3.Row:
        if row is None:
            raise BriefVersionNotFoundError(f"数据库查询未返回结果：{operation}")
        return row

    def next_version(self, conn: sqlite3.Connection, project_id: str) -> int:
        row = self._required_row(
            conn.execute(
                """SELECT COALESCE(MAX(version),0)+1 AS value
                FROM brief_versions WHERE project_id=?""",
                (project_id,),
            ).fetchone(),
            "计算创作方案版本",
        )
        return int(row["value"])

    def insert_brief_version(
        self,
        conn: sqlite3.Connection,
        *,
        project_id: str,
        version: int,
        brief: CreativeBrief,
        source: str,
        feedback: str | None,
        created_at: str,
    ) -> None:
        conn.execute(
            """INSERT INTO brief_versions
            (project_id,version,brief_json,source,feedback,created_at)
            VALUES (?,?,?,?,?,?)""",
            (
                project_id,
                version,
                dump_json(brief),
                source[:40],
                feedback,
                created_at,
            ),
        )

    def insert_initial_version(
        self,
        conn: sqlite3.Connection,
        *,
        project_id: str,
        brief: CreativeBrief,
        created_at: str,
    ) -> None:
        conn.execute(
            """INSERT INTO brief_versions
            (project_id,version,brief_json,source,feedback,created_at)
            VALUES (?,1,?,'initial',NULL,?)""",
            (project_id, dump_json(brief), created_at),
        )

    def list_brief_versions(self, project_id: str) -> list[dict[str, object]]:
        with self._database.connection() as conn:
            rows = conn.execute(
                """SELECT version,brief_json,source,feedback,created_at FROM brief_versions
                WHERE project_id=? ORDER BY version DESC""",
                (project_id,),
            ).fetchall()
        return [
            {
                "version": row["version"],
                "brief": CreativeBrief.model_validate_json(row["brief_json"]),
                "source": row["source"],
                "feedback": row["feedback"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def get_brief_version(self, project_id: str, version: int) -> CreativeBrief:
        with self._database.connection() as conn:
            row = conn.execute(
                "SELECT brief_json FROM brief_versions WHERE project_id=? AND version=?",
                (project_id, version),
            ).fetchone()
        if row is None:
            raise BriefVersionNotFoundError(f"找不到方案版本：v{version}")
        return CreativeBrief.model_validate_json(row["brief_json"])

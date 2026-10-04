from __future__ import annotations

import json
import sqlite3
from typing import Any

from novel_agent.infrastructure.persistence.json_util import dump_json
from novel_agent.models import new_id, utc_now


class OpeningRepairStoreError(RuntimeError):
    code = "OPENING_REPAIR_ROLLBACK_UNSAFE"


def _row_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


class SQLiteOpeningRepairStore:
    def __init__(self, database: Any):
        self._database = database

    def capture_snapshot(self, conn: sqlite3.Connection, project_id: str) -> dict[str, Any]:
        chapter_ids = [
            str(row["id"])
            for row in conn.execute(
                "SELECT id FROM chapters WHERE project_id=? AND number=1",
                (project_id,),
            ).fetchall()
        ]
        payload: dict[str, Any] = {
            "project": self._fetch_one(conn, "SELECT * FROM projects WHERE id=?", (project_id,)),
            "brief_versions": self._fetch_all(
                conn, "SELECT * FROM brief_versions WHERE project_id=? ORDER BY version", (project_id,)
            ),
            "chapters": self._fetch_all(
                conn, "SELECT * FROM chapters WHERE project_id=? AND number=1", (project_id,)
            ),
            "characters": self._fetch_all(
                conn, "SELECT * FROM characters WHERE project_id=?", (project_id,)
            ),
            "world_facts": self._fetch_all(
                conn, "SELECT * FROM world_facts WHERE project_id=?", (project_id,)
            ),
            "timeline_events": self._fetch_all(
                conn, "SELECT * FROM timeline_events WHERE project_id=?", (project_id,)
            ),
            "foreshadows": self._fetch_all(
                conn, "SELECT * FROM foreshadows WHERE project_id=?", (project_id,)
            ),
        }
        research_ids = self.list_opening_research_source_ids(conn, project_id, chapter_ids)
        payload["research_sources"] = self._fetch_research_rows(conn, project_id, research_ids)
        payload["semantic_documents"] = self._fetch_opening_semantic_documents(
            conn, project_id, chapter_ids, research_ids
        )
        if chapter_ids:
            placeholders = ",".join("?" for _ in chapter_ids)
            payload["chapter_versions"] = self._fetch_all(
                conn,
                f"SELECT * FROM chapter_versions WHERE chapter_id IN ({placeholders})",
                tuple(chapter_ids),
            )
            payload["chapter_edit_drafts"] = self._fetch_all(
                conn,
                f"SELECT * FROM chapter_edit_drafts WHERE chapter_id IN ({placeholders})",
                tuple(chapter_ids),
            )
            payload["runs"] = self._fetch_all(
                conn,
                f"SELECT * FROM runs WHERE project_id=? AND chapter_id IN ({placeholders})",
                (project_id, *chapter_ids),
            )
            run_ids = [str(item["id"]) for item in payload["runs"]]
            if run_ids:
                run_ph = ",".join("?" for _ in run_ids)
                payload["run_events"] = self._fetch_all(
                    conn,
                    f"SELECT * FROM run_events WHERE run_id IN ({run_ph})",
                    tuple(run_ids),
                )
            else:
                payload["run_events"] = []
            payload["review_reports"] = self._fetch_all(
                conn,
                f"SELECT * FROM review_reports WHERE chapter_id IN ({placeholders})",
                tuple(chapter_ids),
            )
            payload["assistant_sessions"] = self._fetch_all(
                conn,
                f"SELECT * FROM assistant_sessions WHERE project_id=? AND chapter_id IN ({placeholders})",
                (project_id, *chapter_ids),
            )
            session_ids = [str(item["id"]) for item in payload["assistant_sessions"]]
            if session_ids:
                sess_ph = ",".join("?" for _ in session_ids)
                payload["assistant_messages"] = self._fetch_all(
                    conn,
                    f"SELECT * FROM assistant_messages WHERE session_id IN ({sess_ph})",
                    tuple(session_ids),
                )
                payload["assistant_change_sets"] = self._fetch_all(
                    conn,
                    f"SELECT * FROM assistant_change_sets WHERE session_id IN ({sess_ph})",
                    tuple(session_ids),
                )
            else:
                payload["assistant_messages"] = []
                payload["assistant_change_sets"] = []
        return payload

    def list_legacy_null_research_ids(
        self, conn: sqlite3.Connection, project_id: str
    ) -> list[int]:
        rows = conn.execute(
            """SELECT id FROM research_sources
            WHERE project_id=? AND chapter_id IS NULL""",
            (project_id,),
        ).fetchall()
        return [int(row["id"]) for row in rows]

    def list_opening_research_source_ids(
        self,
        conn: sqlite3.Connection,
        project_id: str,
        chapter_ids: list[str],
    ) -> list[int]:
        ids = self.list_legacy_null_research_ids(conn, project_id)
        if chapter_ids:
            placeholders = ",".join("?" for _ in chapter_ids)
            rows = conn.execute(
                f"""SELECT id FROM research_sources
                WHERE project_id=? AND chapter_id IN ({placeholders})""",
                (project_id, *chapter_ids),
            ).fetchall()
            ids.extend(int(row["id"]) for row in rows)
        return list(dict.fromkeys(ids))

    def delete_polluted_opening_research(
        self,
        conn: sqlite3.Connection,
        project_id: str,
        chapter_ids: list[str],
    ) -> None:
        source_ids = self.list_opening_research_source_ids(conn, project_id, chapter_ids)
        if source_ids:
            source_keys = [str(item) for item in source_ids]
            placeholders = ",".join("?" for _ in source_keys)
            conn.execute(
                f"""DELETE FROM semantic_documents
                WHERE project_id=? AND source_type='research_source'
                AND source_id IN ({placeholders})""",
                (project_id, *source_keys),
            )
        if chapter_ids:
            placeholders = ",".join("?" for _ in chapter_ids)
            conn.execute(
                f"""DELETE FROM semantic_documents
                WHERE project_id=? AND chapter_id IN ({placeholders})""",
                (project_id, *chapter_ids),
            )
            conn.execute(
                f"DELETE FROM research_sources WHERE project_id=? AND chapter_id IN ({placeholders})",
                (project_id, *chapter_ids),
            )
        conn.execute(
            "DELETE FROM research_sources WHERE project_id=? AND chapter_id IS NULL",
            (project_id,),
        )

    def insert_snapshot(
        self,
        conn: sqlite3.Connection,
        *,
        project_id: str,
        payload: dict[str, Any],
        status: str,
    ) -> str:
        snapshot_id = new_id("repair")
        now = utc_now()
        conn.execute(
            """INSERT INTO project_repair_snapshots
            (id,project_id,kind,status,payload_json,created_at,applied_at,rolled_back_at)
            VALUES (?,?,?,?,?,?,?,NULL)""",
            (
                snapshot_id,
                project_id,
                "opening_repair",
                status,
                dump_json(payload),
                now,
                now if status == "applied" else None,
            ),
        )
        return snapshot_id

    def get_snapshot(self, snapshot_id: str) -> dict[str, Any] | None:
        with self._database.connection() as conn:
            row = conn.execute(
                "SELECT * FROM project_repair_snapshots WHERE id=?",
                (snapshot_id,),
            ).fetchone()
        if row is None:
            return None
        data = _row_dict(row)
        data["payload"] = json.loads(data["payload_json"])
        return data

    def get_latest_applied_snapshot(self, project_id: str) -> dict[str, Any] | None:
        with self._database.connection() as conn:
            row = conn.execute(
                """SELECT id,project_id,kind,status,created_at,applied_at,rolled_back_at
                FROM project_repair_snapshots
                WHERE project_id=? AND kind='opening_repair' AND status='applied'
                ORDER BY created_at DESC LIMIT 1""",
                (project_id,),
            ).fetchone()
        return _row_dict(row) if row is not None else None

    def mark_rolled_back(self, conn: sqlite3.Connection, snapshot_id: str) -> None:
        cursor = conn.execute(
            """UPDATE project_repair_snapshots SET status=?, rolled_back_at=?
            WHERE id=? AND status='applied'""",
            ("rolled_back", utc_now(), snapshot_id),
        )
        if cursor.rowcount != 1:
            raise OpeningRepairStoreError("未能标记快照为已回退")

    def update_project_from_snapshot(
        self,
        conn: sqlite3.Connection,
        project_id: str,
        project_row: dict[str, Any],
    ) -> None:
        if not project_row:
            raise OpeningRepairStoreError("快照缺少项目行")
        columns = [key for key in project_row.keys() if key != "id"]
        assignments = ",".join(f"{column}=?" for column in columns)
        cursor = conn.execute(
            f"UPDATE projects SET {assignments} WHERE id=?",
            tuple(project_row[column] for column in columns) + (project_id,),
        )
        if cursor.rowcount != 1:
            raise OpeningRepairStoreError("未能更新项目行，回退已中止")

    def restore_payload(self, conn: sqlite3.Connection, project_id: str, payload: dict[str, Any]) -> None:
        chapter_ids = [str(item["id"]) for item in payload.get("chapters") or []]
        self._clear_live_opening_state(conn, project_id, chapter_ids)
        project_row = payload.get("project")
        if project_row:
            self.update_project_from_snapshot(conn, project_id, project_row)
        self._restore_table(conn, "brief_versions", payload.get("brief_versions") or [])
        self._restore_table(conn, "chapters", payload.get("chapters") or [])
        self._restore_table(conn, "characters", payload.get("characters") or [])
        self._restore_table(conn, "world_facts", payload.get("world_facts") or [])
        self._restore_table(conn, "timeline_events", payload.get("timeline_events") or [])
        self._restore_table(conn, "foreshadows", payload.get("foreshadows") or [])
        self._restore_table(conn, "chapter_versions", payload.get("chapter_versions") or [])
        self._restore_table(conn, "chapter_edit_drafts", payload.get("chapter_edit_drafts") or [])
        self._restore_table(conn, "runs", payload.get("runs") or [])
        self._restore_table(conn, "run_events", payload.get("run_events") or [])
        self._restore_table(conn, "review_reports", payload.get("review_reports") or [])
        self._restore_table(conn, "research_sources", payload.get("research_sources") or [])
        self._restore_table(conn, "semantic_documents", payload.get("semantic_documents") or [])
        self._restore_table(conn, "assistant_sessions", payload.get("assistant_sessions") or [])
        self._restore_table(conn, "assistant_messages", payload.get("assistant_messages") or [])
        self._restore_table(conn, "assistant_change_sets", payload.get("assistant_change_sets") or [])

    def _clear_live_opening_state(
        self, conn: sqlite3.Connection, project_id: str, chapter_ids: list[str]
    ) -> None:
        conn.execute("DELETE FROM brief_versions WHERE project_id=?", (project_id,))
        conn.execute("DELETE FROM characters WHERE project_id=?", (project_id,))
        conn.execute("DELETE FROM world_facts WHERE project_id=?", (project_id,))
        conn.execute("DELETE FROM timeline_events WHERE project_id=?", (project_id,))
        conn.execute("DELETE FROM foreshadows WHERE project_id=?", (project_id,))
        self.delete_polluted_opening_research(conn, project_id, chapter_ids)
        if not chapter_ids:
            conn.execute("DELETE FROM chapters WHERE project_id=? AND number=1", (project_id,))
            return
        placeholders = ",".join("?" for _ in chapter_ids)
        conn.execute(
            f"DELETE FROM assistant_change_sets WHERE chapter_id IN ({placeholders})",
            tuple(chapter_ids),
        )
        session_ids = [
            str(row["id"])
            for row in conn.execute(
                f"SELECT id FROM assistant_sessions WHERE chapter_id IN ({placeholders})",
                tuple(chapter_ids),
            ).fetchall()
        ]
        if session_ids:
            sess_ph = ",".join("?" for _ in session_ids)
            conn.execute(
                f"DELETE FROM assistant_messages WHERE session_id IN ({sess_ph})",
                tuple(session_ids),
            )
        conn.execute(
            f"DELETE FROM assistant_sessions WHERE chapter_id IN ({placeholders})",
            tuple(chapter_ids),
        )
        conn.execute(
            f"DELETE FROM review_reports WHERE chapter_id IN ({placeholders})",
            tuple(chapter_ids),
        )
        conn.execute(
            f"DELETE FROM run_events WHERE run_id IN (SELECT id FROM runs WHERE chapter_id IN ({placeholders}))",
            tuple(chapter_ids),
        )
        conn.execute(
            f"DELETE FROM runs WHERE chapter_id IN ({placeholders})",
            tuple(chapter_ids),
        )
        conn.execute(
            f"DELETE FROM chapter_edit_drafts WHERE chapter_id IN ({placeholders})",
            tuple(chapter_ids),
        )
        conn.execute(
            f"DELETE FROM chapter_versions WHERE chapter_id IN ({placeholders})",
            tuple(chapter_ids),
        )
        conn.execute(
            f"DELETE FROM chapters WHERE id IN ({placeholders})",
            tuple(chapter_ids),
        )

    def _fetch_research_rows(
        self, conn: sqlite3.Connection, project_id: str, research_ids: list[int]
    ) -> list[dict[str, Any]]:
        if not research_ids:
            return []
        placeholders = ",".join("?" for _ in research_ids)
        return self._fetch_all(
            conn,
            f"SELECT * FROM research_sources WHERE project_id=? AND id IN ({placeholders})",
            (project_id, *research_ids),
        )

    def _fetch_opening_semantic_documents(
        self,
        conn: sqlite3.Connection,
        project_id: str,
        chapter_ids: list[str],
        research_ids: list[int],
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = [project_id]
        if chapter_ids:
            placeholders = ",".join("?" for _ in chapter_ids)
            clauses.append(f"chapter_id IN ({placeholders})")
            params.extend(chapter_ids)
        if research_ids:
            source_keys = [str(item) for item in research_ids]
            placeholders = ",".join("?" for _ in source_keys)
            clauses.append(
                f"(source_type='research_source' AND source_id IN ({placeholders}))"
            )
            params.extend(source_keys)
        if not clauses:
            return []
        return self._fetch_all(
            conn,
            f"SELECT * FROM semantic_documents WHERE project_id=? AND ({' OR '.join(clauses)})",
            tuple(params),
        )

    @staticmethod
    def _fetch_one(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...]) -> dict[str, Any] | None:
        row = conn.execute(sql, params).fetchone()
        return _row_dict(row) if row is not None else None

    @staticmethod
    def _fetch_all(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
        return [_row_dict(row) for row in conn.execute(sql, params).fetchall()]

    @staticmethod
    def _restore_table(
        conn: sqlite3.Connection,
        table: str,
        rows: list[dict[str, Any]],
        *,
        replace: bool = False,
    ) -> None:
        if not rows:
            return
        if table == "projects":
            raise OpeningRepairStoreError("projects 必须使用 UPDATE，禁止 REPLACE")
        columns = list(rows[0].keys())
        placeholders = ",".join("?" for _ in columns)
        column_sql = ",".join(columns)
        verb = "INSERT OR REPLACE" if replace else "INSERT"
        sql = f"{verb} INTO {table} ({column_sql}) VALUES ({placeholders})"
        for row in rows:
            conn.execute(sql, tuple(row[column] for column in columns))

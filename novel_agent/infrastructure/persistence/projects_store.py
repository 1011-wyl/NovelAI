"""SQLite projects store (list/get/status/confirm/delete + row mapping)."""

from __future__ import annotations

import sqlite3
from collections import defaultdict

from novel_agent.features.projects.errors import ProjectNotFoundError, ProjectStateError
from novel_agent.features.projects.models import ProjectRecord, ProjectStatus, ProjectSummary
from novel_agent.features.story_design.models import CreativeBrief, NovelCreateRequest
from novel_agent.infrastructure.persistence.database import DatabaseSessionProvider
from novel_agent.infrastructure.persistence.json_util import dump_json
from novel_agent.models import utc_now
from novel_agent.text_metrics import count_content_chars


class SQLiteProjectsStore:
    def __init__(self, database: DatabaseSessionProvider):
        self._database = database

    @staticmethod
    def project_from_row(row: sqlite3.Row) -> ProjectRecord:
        return ProjectRecord(
            id=row["id"],
            title=row["title"],
            status=ProjectStatus(row["status"]),
            request=NovelCreateRequest.model_validate_json(row["request_json"]),
            brief=CreativeBrief.model_validate_json(row["brief_json"]),
            confirmed=bool(row["confirmed"]),
            current_chapter=row["current_chapter"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def insert_project(self, conn: sqlite3.Connection, project: ProjectRecord) -> None:
        conn.execute(
            """INSERT INTO projects
            (id,title,status,request_json,brief_json,confirmed,current_chapter,
             created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                project.id,
                project.title,
                project.status.value,
                dump_json(project.request),
                dump_json(project.brief),
                int(project.confirmed),
                project.current_chapter,
                project.created_at,
                project.updated_at,
            ),
        )

    def fetch_project_row(
        self, conn: sqlite3.Connection, project_id: str
    ) -> sqlite3.Row | None:
        return conn.execute(
            "SELECT * FROM projects WHERE id=?", (project_id,)
        ).fetchone()

    def require_project_row(
        self, conn: sqlite3.Connection, project_id: str
    ) -> sqlite3.Row:
        row = self.fetch_project_row(conn, project_id)
        if row is None:
            raise ProjectNotFoundError(f"找不到小说项目：{project_id}")
        return row

    def update_title_and_brief(
        self,
        conn: sqlite3.Connection,
        project_id: str,
        *,
        title: str,
        brief: CreativeBrief,
        updated_at: str,
    ) -> None:
        conn.execute(
            """UPDATE projects SET title=?,brief_json=?,updated_at=? WHERE id=?""",
            (title, dump_json(brief), updated_at, project_id),
        )

    def list_projects(self) -> list[ProjectRecord]:
        with self._database.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM projects ORDER BY created_at DESC"
            ).fetchall()
        return [self.project_from_row(row) for row in rows]

    def list_project_summaries(self) -> list[ProjectSummary]:
        """Aggregate bookshelf rows in one pass (projects + chapter bodies)."""
        with self._database.connection() as conn:
            project_rows = conn.execute(
                """SELECT id,title,status,confirmed,current_chapter,created_at,updated_at,
                          request_json
                   FROM projects
                   ORDER BY updated_at DESC"""
            ).fetchall()
            chapter_rows = conn.execute(
                """SELECT project_id, content FROM chapters
                   WHERE project_id IN (SELECT id FROM projects)"""
            ).fetchall()

        chapter_counts: dict[str, int] = defaultdict(int)
        content_chars: dict[str, int] = defaultdict(int)
        for row in chapter_rows:
            project_id = str(row["project_id"])
            chapter_counts[project_id] += 1
            content = row["content"]
            if content:
                content_chars[project_id] += count_content_chars(content)

        summaries: list[ProjectSummary] = []
        for row in project_rows:
            request = NovelCreateRequest.model_validate_json(row["request_json"])
            project_id = str(row["id"])
            summaries.append(
                ProjectSummary(
                    id=project_id,
                    title=row["title"],
                    status=ProjectStatus(row["status"]),
                    confirmed=bool(row["confirmed"]),
                    audience_channel=request.audience_channel,
                    genre=request.genre,
                    chapter_count=chapter_counts[project_id],
                    content_chars=content_chars[project_id],
                    current_chapter=int(row["current_chapter"]),
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
            )
        return summaries

    def get_project(self, project_id: str) -> ProjectRecord:
        with self._database.connection() as conn:
            return self.project_from_row(self.require_project_row(conn, project_id))

    def update_project_status(
        self, project_id: str, status: ProjectStatus
    ) -> ProjectRecord:
        with self._database.transaction() as conn:
            updated = conn.execute(
                "UPDATE projects SET status=?, updated_at=? WHERE id=?",
                (status.value, utc_now(), project_id),
            ).rowcount
            if not updated:
                raise ProjectNotFoundError(f"找不到小说项目：{project_id}")
        return self.get_project(project_id)

    def confirm_project(self, project_id: str) -> ProjectRecord:
        with self._database.transaction() as conn:
            updated = conn.execute(
                "UPDATE projects SET confirmed=1,status=?,updated_at=? WHERE id=?",
                (ProjectStatus.ACTIVE.value, utc_now(), project_id),
            ).rowcount
            if not updated:
                raise ProjectNotFoundError(f"找不到小说项目：{project_id}")
        return self.get_project(project_id)

    def delete_project(self, project_id: str, *, force: bool = False) -> None:
        with self._database.transaction() as conn:
            project = conn.execute(
                "SELECT status,confirmed FROM projects WHERE id=?", (project_id,)
            ).fetchone()
            if project is None:
                raise ProjectNotFoundError(f"找不到小说项目：{project_id}")
            if not force:
                if project["status"] != ProjectStatus.DRAFT.value or bool(
                    project["confirmed"]
                ):
                    raise ProjectStateError("只能删除尚未确认的草稿项目")
            conn.execute("DELETE FROM publish_tasks WHERE project_id=?", (project_id,))
            conn.execute("DELETE FROM projects WHERE id=?", (project_id,))

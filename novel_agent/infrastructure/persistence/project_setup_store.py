"""Cross-table project create / draft-brief sync transaction coordinator."""

from __future__ import annotations

import sqlite3

from novel_agent.features.projects.errors import ProjectNotFoundError, ProjectStateError
from novel_agent.features.projects.models import ProjectRecord, ProjectStatus, ProjectSummary
from novel_agent.features.story_design.character_seed import seed_payloads_from_brief
from novel_agent.features.story_design.models import CreativeBrief, NovelCreateRequest
from novel_agent.infrastructure.persistence.briefs_store import SQLiteBriefsStore
from novel_agent.infrastructure.persistence.database import DatabaseSessionProvider
from novel_agent.infrastructure.persistence.json_util import dump_json
from novel_agent.infrastructure.persistence.projects_store import SQLiteProjectsStore
from novel_agent.models import CharacterRecord, WorldFactRecord, new_id, utc_now
from novel_agent.text_metrics import count_content_chars


class SQLiteProjectSetupStore:
    def __init__(
        self,
        database: DatabaseSessionProvider,
        projects: SQLiteProjectsStore,
        briefs: SQLiteBriefsStore,
    ):
        self._database = database
        self._projects = projects
        self._briefs = briefs

    @staticmethod
    def _required_row(row: sqlite3.Row | None, operation: str) -> sqlite3.Row:
        if row is None:
            raise ProjectStateError(f"数据库查询未返回结果：{operation}")
        return row

    def create_project_with_seed(
        self,
        project: ProjectRecord,
        characters: list[CharacterRecord],
        world_facts: list[WorldFactRecord],
    ) -> ProjectRecord:
        with self._database.transaction() as conn:
            self._projects.insert_project(conn, project)
            self._briefs.insert_initial_version(
                conn,
                project_id=project.id,
                brief=project.brief,
                created_at=project.created_at,
            )
            for character in characters:
                conn.execute(
                    """INSERT INTO characters
                    (id,project_id,name,role,immutable_facts_json,current_state_json,version)
                    VALUES (?,?,?,?,?,?,?)""",
                    (
                        character.id,
                        character.project_id,
                        character.name,
                        character.role,
                        dump_json(character.immutable_facts),
                        dump_json(character.current_state),
                        character.version,
                    ),
                )
            for fact in world_facts:
                conn.execute(
                    """INSERT INTO world_facts
                    (id,project_id,category,statement,evidence_chapter,version,locked)
                    VALUES (?,?,?,?,?,?,?)""",
                    (
                        fact.id,
                        fact.project_id,
                        fact.category,
                        fact.statement,
                        fact.evidence_chapter,
                        fact.version,
                        int(fact.locked),
                    ),
                )
        return project

    def save_draft_brief_with_seed_sync(
        self,
        project_id: str,
        brief: CreativeBrief,
        *,
        source: str,
        feedback: str = "",
    ) -> ProjectRecord:
        now = utc_now()
        with self._database.transaction() as conn:
            project = conn.execute(
                "SELECT status,confirmed,request_json FROM projects WHERE id=?",
                (project_id,),
            ).fetchone()
            if project is None:
                raise ProjectNotFoundError(f"找不到小说项目：{project_id}")
            if project["status"] != ProjectStatus.DRAFT.value or bool(project["confirmed"]):
                raise ProjectStateError(
                    "创作方案确认后不能直接修改，请创建正式设定变更流程"
                )
            count_row = self._required_row(
                conn.execute(
                    "SELECT COUNT(*) AS count FROM chapters WHERE project_id=?",
                    (project_id,),
                ).fetchone(),
                "统计项目章节",
            )
            chapter_count = int(count_row["count"])
            if chapter_count:
                raise ProjectStateError("项目已有章节，不能按草稿方案修改")
            request = NovelCreateRequest.model_validate_json(project["request_json"])
            next_version = self._briefs.next_version(conn, project_id)
            self._projects.update_title_and_brief(
                conn,
                project_id,
                title=brief.selected_title,
                brief=brief,
                updated_at=now,
            )
            self._briefs.insert_brief_version(
                conn,
                project_id=project_id,
                version=next_version,
                brief=brief,
                source=source,
                feedback=feedback[:2000] or None,
                created_at=now,
            )
            self._sync_characters_and_world(conn, project_id, request, brief)
        return self._projects.get_project(project_id)

    def update_project_metadata(self, project_id: str, title: str) -> ProjectSummary:
        """Rename project without changing status, confirmation, or chapters."""
        now = utc_now()
        with self._database.transaction() as conn:
            row = self._projects.fetch_project_row(conn, project_id)
            if row is None:
                raise ProjectNotFoundError(f"找不到小说项目：{project_id}")
            project = self._projects.project_from_row(row)
            candidates = [
                title,
                *[
                    candidate
                    for candidate in project.brief.title_candidates
                    if candidate != title
                ],
            ][:6]
            brief = project.brief.model_copy(
                update={
                    "selected_title": title,
                    "title_candidates": candidates,
                }
            )
            next_version = self._briefs.next_version(conn, project_id)
            self._projects.update_title_and_brief(
                conn,
                project_id,
                title=title,
                brief=brief,
                updated_at=now,
            )
            self._briefs.insert_brief_version(
                conn,
                project_id=project_id,
                version=next_version,
                brief=brief,
                source="metadata_edit",
                feedback=None,
                created_at=now,
            )
            count_row = self._required_row(
                conn.execute(
                    "SELECT COUNT(*) AS count FROM chapters WHERE project_id=?",
                    (project_id,),
                ).fetchone(),
                "统计项目章节",
            )
            chapter_count = int(count_row["count"])
            content_rows = conn.execute(
                "SELECT content FROM chapters WHERE project_id=?",
                (project_id,),
            ).fetchall()
            content_chars = sum(
                count_content_chars(item["content"])
                for item in content_rows
                if item["content"]
            )
        return ProjectSummary(
            id=project.id,
            title=title,
            status=project.status,
            confirmed=project.confirmed,
            audience_channel=project.request.audience_channel,
            genre=project.request.genre,
            chapter_count=chapter_count,
            content_chars=content_chars,
            current_chapter=project.current_chapter,
            created_at=project.created_at,
            updated_at=now,
        )

    def _sync_characters_and_world(
        self,
        conn: sqlite3.Connection,
        project_id: str,
        request: NovelCreateRequest,
        brief: CreativeBrief,
    ) -> None:
        seeds = seed_payloads_from_brief(request, brief)
        protagonist_row = conn.execute(
            """SELECT id,version FROM characters
            WHERE project_id=? AND role='protagonist' ORDER BY id LIMIT 1""",
            (project_id,),
        ).fetchone()
        if protagonist_row is None:
            raise ProjectStateError("找不到主角人物记录")
        conn.execute("DELETE FROM characters WHERE project_id=?", (project_id,))
        for profile, facts, state in seeds:
            is_protagonist = profile.name == brief.protagonist_name
            character_id = (
                protagonist_row["id"]
                if is_protagonist
                else new_id("character")
            )
            version = int(protagonist_row["version"]) + 1 if is_protagonist else 1
            role = "protagonist" if is_protagonist else (
                "supporting" if profile.role == "protagonist" else profile.role
            )
            conn.execute(
                """INSERT INTO characters
                (id,project_id,name,role,immutable_facts_json,current_state_json,version)
                VALUES (?,?,?,?,?,?,?)""",
                (
                    character_id,
                    project_id,
                    profile.name,
                    role,
                    dump_json(facts),
                    dump_json(state),
                    version,
                ),
            )
        conn.execute("DELETE FROM world_facts WHERE project_id=?", (project_id,))
        for statement in brief.world_rules:
            conn.execute(
                """INSERT INTO world_facts
                (id,project_id,category,statement,evidence_chapter,version,locked)
                VALUES (?,?,?,?,NULL,1,1)""",
                (new_id("fact"), project_id, "hard_rule", statement),
            )

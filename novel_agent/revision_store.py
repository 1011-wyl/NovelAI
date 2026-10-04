from __future__ import annotations

import json
import sqlite3
from typing import Any, Literal

from novel_agent.diffutil import build_text_diff
from novel_agent.models import (
    AssistantChangeSet,
    AssistantChangeStatus,
    AssistantMessage,
    AssistantMode,
    AssistantSession,
    ChapterDraftUpdate,
    ChapterEditDraft,
    ChapterRevisionAnalysis,
    ChapterRevisionResult,
    ChapterSelection,
    ChapterStatus,
    CharacterMemoryUpdate,
    CharacterRecord,
    ProjectStatus,
    ReviewReport,
    new_id,
    utc_now,
)
from novel_agent.revision_errors import (
    AssistantChangeStaleError,
    AssistantChangeStateError,
    ChapterNotEditableError,
    EditConflictError,
)
from novel_agent.text_metrics import count_content_chars
from novel_agent.text_normalize import (
    draft_content_hash,
    normalize_draft_content,
    normalize_draft_title,
)

DraftSource = Literal["manual", "ai", "mixed", "rollback"]
ChangeOperation = Literal["edit_chapter", "rewrite_chapter"]

_KIND_BY_SOURCE: dict[str, str] = {
    "manual": "MANUAL_EDIT",
    "ai": "AI_EDIT",
    "mixed": "MIXED_EDIT",
    "rollback": "ROLLBACK",
}


class RevisionStoreMixin:
    """Reading/revision workspace persistence mixed into SQLiteRepository."""

    # --- row converters -------------------------------------------------

    def _edit_draft_from_row(self, row: sqlite3.Row) -> ChapterEditDraft:
        return ChapterEditDraft(
            chapter_id=row["chapter_id"],
            project_id=row["project_id"],
            base_version=int(row["base_version"]),
            title=row["title"],
            content=row["content"],
            source=row["source"],
            applied_change_ids=json.loads(row["applied_change_ids_json"] or "[]"),
            content_hash=row["content_hash"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _assistant_session_from_row(self, row: sqlite3.Row) -> AssistantSession:
        return AssistantSession(
            id=row["id"],
            project_id=row["project_id"],
            chapter_id=row["chapter_id"],
            title=row["title"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            deleted_at=row["deleted_at"],
        )

    def _assistant_message_from_row(self, row: sqlite3.Row) -> AssistantMessage:
        selection = None
        if row["selection_json"]:
            selection = ChapterSelection.model_validate_json(row["selection_json"])
        return AssistantMessage(
            id=row["id"],
            session_id=row["session_id"],
            sequence=int(row["sequence"]),
            role=row["role"],
            mode=AssistantMode(row["mode"]),
            content=row["content"],
            selection=selection,
            metadata=json.loads(row["metadata_json"] or "{}"),
            created_at=row["created_at"],
        )

    def _assistant_change_from_row(self, row: sqlite3.Row) -> AssistantChangeSet:
        return AssistantChangeSet(
            id=row["id"],
            session_id=row["session_id"],
            message_id=row["message_id"],
            chapter_id=row["chapter_id"],
            operation=row["operation"],
            base_version=int(row["base_version"]),
            base_draft_hash=row["base_draft_hash"],
            before_title=row["before_title"],
            before_content=row["before_content"],
            after_title=row["after_title"],
            after_content=row["after_content"],
            diff_json=json.loads(row["diff_json"] or "{}"),
            explanation=row["explanation"] or "",
            status=AssistantChangeStatus(row["status"]),
            created_at=row["created_at"],
            decided_at=row["decided_at"],
            reverted_at=row["reverted_at"],
        )

    @staticmethod
    def _merge_draft_source(existing: str | None, incoming: DraftSource) -> DraftSource:
        if existing is None:
            return incoming
        if incoming == "manual" and existing in {"ai", "mixed"}:
            return "mixed"
        if incoming == "ai" and existing in {"manual", "mixed", "rollback"}:
            return "mixed"
        if incoming == "rollback":
            return "rollback"
        return incoming

    def _require_editable_chapter(
        self,
        conn: sqlite3.Connection,
        project_id: str,
        chapter_number: int,
        action: str | None = None,
    ) -> tuple[sqlite3.Row, sqlite3.Row]:
        from novel_agent.features.chapter_planning.workspace_capabilities import (
            WorkspaceAction,
            capability_denied_reason,
            workspace_capabilities,
        )
        from novel_agent.features.opening_repair.errors import ChapterActionNotAllowedError
        from novel_agent.repository import RepositoryError

        project = conn.execute(
            "SELECT * FROM projects WHERE id=?", (project_id,)
        ).fetchone()
        if project is None:
            raise RepositoryError(f"找不到小说项目：{project_id}")
        if project["status"] == ProjectStatus.ARCHIVED.value:
            raise ChapterNotEditableError("已归档项目不可编辑")
        chapter = conn.execute(
            "SELECT * FROM chapters WHERE project_id=? AND number=?",
            (project_id, chapter_number),
        ).fetchone()
        if chapter is None:
            raise RepositoryError(f"找不到第{chapter_number}章")
        resolved = WorkspaceAction(action) if action else WorkspaceAction.COMMIT_REVISION
        caps = workspace_capabilities(str(chapter["status"]), str(project["status"]))
        reason = capability_denied_reason(resolved, caps, str(chapter["status"]))
        if reason:
            if resolved == WorkspaceAction.COMMIT_REVISION and chapter["status"] == ChapterStatus.FAILED.value:
                error = ChapterActionNotAllowedError(reason)
                error.code = "FAILED_DRAFT_REVIEW_REQUIRED"
                raise error
            if resolved in {WorkspaceAction.EDIT_DRAFT, WorkspaceAction.ASSISTANT}:
                raise ChapterNotEditableError(reason)
            raise ChapterActionNotAllowedError(reason)
        return project, chapter

    def _working_copy_on_conn(
        self,
        conn: sqlite3.Connection,
        project_id: str,
        chapter_number: int,
    ) -> tuple[str, str, ChapterEditDraft | None, str]:
        from novel_agent.repository import RepositoryError

        chapter = conn.execute(
            "SELECT * FROM chapters WHERE project_id=? AND number=?",
            (project_id, chapter_number),
        ).fetchone()
        if chapter is None:
            raise RepositoryError(f"找不到第{chapter_number}章")
        draft_row = conn.execute(
            "SELECT * FROM chapter_edit_drafts WHERE chapter_id=?",
            (chapter["id"],),
        ).fetchone()
        if draft_row:
            draft = self._edit_draft_from_row(draft_row)
            return draft.title, draft.content, draft, draft.content_hash
        title = normalize_draft_title(chapter["title"] or "")
        content = normalize_draft_content(chapter["content"] or "")
        return title, content, None, draft_content_hash(title, content)

    def get_or_create_working_copy(
        self, project_id: str, chapter_number: int
    ) -> tuple[str, str, ChapterEditDraft | None, str]:
        with self.connection() as conn:  # type: ignore[attr-defined]
            return self._working_copy_on_conn(conn, project_id, chapter_number)

    # --- working drafts -------------------------------------------------

    def get_chapter_edit_draft(
        self, project_id: str, chapter_number: int
    ) -> ChapterEditDraft | None:
        with self.connection() as conn:  # type: ignore[attr-defined]
            row = conn.execute(
                """SELECT d.* FROM chapter_edit_drafts d
                JOIN chapters c ON c.id=d.chapter_id
                WHERE d.project_id=? AND c.number=?""",
                (project_id, chapter_number),
            ).fetchone()
        return self._edit_draft_from_row(row) if row else None

    def upsert_chapter_edit_draft(
        self,
        project_id: str,
        chapter_number: int,
        update: ChapterDraftUpdate,
        *,
        source: DraftSource = "manual",
    ) -> ChapterEditDraft:
        title = normalize_draft_title(update.title)
        content = normalize_draft_content(update.content)
        content_hash = draft_content_hash(title, content)
        now = utc_now()
        with self.transaction() as conn:  # type: ignore[attr-defined]
            _, chapter = self._require_editable_chapter(
                conn, project_id, chapter_number, action="edit_draft"
            )
            if int(chapter["version"]) != int(update.base_version):
                raise EditConflictError(
                    f"正式版本已变更：期望 v{update.base_version}，当前 v{chapter['version']}"
                )
            existing = conn.execute(
                "SELECT * FROM chapter_edit_drafts WHERE chapter_id=?",
                (chapter["id"],),
            ).fetchone()
            if update.expected_draft_hash is not None:
                current_hash = (
                    existing["content_hash"]
                    if existing
                    else draft_content_hash(
                        normalize_draft_title(chapter["title"] or ""),
                        normalize_draft_content(chapter["content"] or ""),
                    )
                )
                if current_hash != update.expected_draft_hash:
                    raise EditConflictError("工作草稿已被其他操作更新")
            merged_source = self._merge_draft_source(
                existing["source"] if existing else None, source
            )
            applied_ids = (
                existing["applied_change_ids_json"] if existing else "[]"
            )
            created_at = existing["created_at"] if existing else now
            conn.execute(
                """INSERT INTO chapter_edit_drafts
                (chapter_id,project_id,base_version,title,content,source,
                 applied_change_ids_json,content_hash,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(chapter_id) DO UPDATE SET
                base_version=excluded.base_version,
                title=excluded.title,
                content=excluded.content,
                source=excluded.source,
                content_hash=excluded.content_hash,
                updated_at=excluded.updated_at""",
                (
                    chapter["id"],
                    project_id,
                    int(chapter["version"]),
                    title,
                    content,
                    merged_source,
                    applied_ids,
                    content_hash,
                    created_at,
                    now,
                ),
            )
            row = self._required_row(  # type: ignore[attr-defined]
                conn.execute(
                    "SELECT * FROM chapter_edit_drafts WHERE chapter_id=?",
                    (chapter["id"],),
                ).fetchone(),
                "读取工作草稿",
            )
        return self._edit_draft_from_row(row)

    def delete_chapter_edit_draft(self, project_id: str, chapter_number: int) -> None:
        from novel_agent.repository import RepositoryError

        with self.transaction() as conn:  # type: ignore[attr-defined]
            chapter = conn.execute(
                "SELECT id FROM chapters WHERE project_id=? AND number=?",
                (project_id, chapter_number),
            ).fetchone()
            if chapter is None:
                raise RepositoryError(f"找不到第{chapter_number}章")
            conn.execute(
                "DELETE FROM chapter_edit_drafts WHERE chapter_id=?",
                (chapter["id"],),
            )

    # --- assistant sessions / messages / changes ------------------------

    def create_assistant_session(
        self,
        project_id: str,
        chapter_number: int,
        title: str | None = None,
    ) -> AssistantSession:
        now = utc_now()
        session_id = new_id("asession")
        with self.transaction() as conn:  # type: ignore[attr-defined]
            _, chapter = self._require_editable_chapter(
                conn, project_id, chapter_number, action="use_assistant"
            )
            session_title = (title or "").strip() or f"第{chapter_number}章修订会话"
            conn.execute(
                """INSERT INTO assistant_sessions
                (id,project_id,chapter_id,title,created_at,updated_at,deleted_at)
                VALUES (?,?,?,?,?,?,NULL)""",
                (
                    session_id,
                    project_id,
                    chapter["id"],
                    session_title,
                    now,
                    now,
                ),
            )
            row = self._required_row(  # type: ignore[attr-defined]
                conn.execute(
                    "SELECT * FROM assistant_sessions WHERE id=?", (session_id,)
                ).fetchone(),
                "创建 AI 会话",
            )
        return self._assistant_session_from_row(row)

    def list_assistant_sessions(
        self, project_id: str, chapter_number: int
    ) -> list[AssistantSession]:
        with self.connection() as conn:  # type: ignore[attr-defined]
            rows = conn.execute(
                """SELECT s.* FROM assistant_sessions s
                JOIN chapters c ON c.id=s.chapter_id
                WHERE s.project_id=? AND c.number=? AND s.deleted_at IS NULL
                ORDER BY s.updated_at DESC""",
                (project_id, chapter_number),
            ).fetchall()
        return [self._assistant_session_from_row(row) for row in rows]

    def get_assistant_session(self, session_id: str) -> AssistantSession:
        from novel_agent.repository import RepositoryError

        with self.connection() as conn:  # type: ignore[attr-defined]
            row = conn.execute(
                "SELECT * FROM assistant_sessions WHERE id=?", (session_id,)
            ).fetchone()
        if row is None:
            raise RepositoryError(f"找不到 AI 会话：{session_id}")
        return self._assistant_session_from_row(row)

    def delete_assistant_session(self, session_id: str) -> None:
        from novel_agent.repository import RepositoryError

        now = utc_now()
        with self.transaction() as conn:  # type: ignore[attr-defined]
            updated = conn.execute(
                """UPDATE assistant_sessions
                SET deleted_at=?, updated_at=?
                WHERE id=? AND deleted_at IS NULL""",
                (now, now, session_id),
            ).rowcount
            if not updated:
                exists = conn.execute(
                    "SELECT id FROM assistant_sessions WHERE id=?", (session_id,)
                ).fetchone()
                if exists is None:
                    raise RepositoryError(f"找不到 AI 会话：{session_id}")

    def list_assistant_messages(self, session_id: str) -> list[AssistantMessage]:
        with self.connection() as conn:  # type: ignore[attr-defined]
            rows = conn.execute(
                """SELECT * FROM assistant_messages
                WHERE session_id=? ORDER BY sequence""",
                (session_id,),
            ).fetchall()
        return [self._assistant_message_from_row(row) for row in rows]

    def append_assistant_message(
        self,
        session_id: str,
        *,
        role: Literal["user", "assistant"],
        mode: AssistantMode | str,
        content: str,
        selection: ChapterSelection | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AssistantMessage:
        from novel_agent.repository import RepositoryError

        now = utc_now()
        message_id = new_id("amsg")
        mode_value = mode.value if isinstance(mode, AssistantMode) else str(mode)
        with self.transaction() as conn:  # type: ignore[attr-defined]
            session = conn.execute(
                "SELECT * FROM assistant_sessions WHERE id=? AND deleted_at IS NULL",
                (session_id,),
            ).fetchone()
            if session is None:
                raise RepositoryError(f"找不到 AI 会话：{session_id}")
            seq_row = self._required_row(  # type: ignore[attr-defined]
                conn.execute(
                    """SELECT COALESCE(MAX(sequence),0)+1 AS next_seq
                    FROM assistant_messages WHERE session_id=?""",
                    (session_id,),
                ).fetchone(),
                "计算会话消息序号",
            )
            sequence = int(seq_row["next_seq"])
            conn.execute(
                """INSERT INTO assistant_messages
                (id,session_id,sequence,role,mode,content,selection_json,metadata_json,created_at)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    message_id,
                    session_id,
                    sequence,
                    role,
                    mode_value,
                    content,
                    self._dump(selection) if selection else None,  # type: ignore[attr-defined]
                    self._dump(metadata or {}),  # type: ignore[attr-defined]
                    now,
                ),
            )
            conn.execute(
                "UPDATE assistant_sessions SET updated_at=? WHERE id=?",
                (now, session_id),
            )
            row = self._required_row(  # type: ignore[attr-defined]
                conn.execute(
                    "SELECT * FROM assistant_messages WHERE id=?", (message_id,)
                ).fetchone(),
                "写入会话消息",
            )
        return self._assistant_message_from_row(row)

    def create_assistant_change_set(
        self,
        session_id: str,
        message_id: str,
        *,
        operation: ChangeOperation,
        base_version: int,
        base_draft_hash: str,
        before_title: str,
        before_content: str,
        after_title: str,
        after_content: str,
        explanation: str = "",
        diff_json: dict[str, Any] | None = None,
    ) -> AssistantChangeSet:
        from novel_agent.repository import RepositoryError

        now = utc_now()
        change_id = new_id("achange")
        before_title_n = normalize_draft_title(before_title)
        before_content_n = normalize_draft_content(before_content)
        after_title_n = normalize_draft_title(after_title)
        after_content_n = normalize_draft_content(after_content)
        diff = diff_json or build_text_diff(
            before_title=before_title_n,
            before_content=before_content_n,
            after_title=after_title_n,
            after_content=after_content_n,
        )
        with self.transaction() as conn:  # type: ignore[attr-defined]
            session = conn.execute(
                "SELECT * FROM assistant_sessions WHERE id=? AND deleted_at IS NULL",
                (session_id,),
            ).fetchone()
            if session is None:
                raise RepositoryError(f"找不到 AI 会话：{session_id}")
            message = conn.execute(
                "SELECT id FROM assistant_messages WHERE id=? AND session_id=?",
                (message_id, session_id),
            ).fetchone()
            if message is None:
                raise RepositoryError(f"找不到会话消息：{message_id}")
            conn.execute(
                """INSERT INTO assistant_change_sets
                (id,session_id,message_id,chapter_id,operation,base_version,base_draft_hash,
                 before_title,before_content,after_title,after_content,diff_json,explanation,
                 status,created_at,decided_at,reverted_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,NULL,NULL)""",
                (
                    change_id,
                    session_id,
                    message_id,
                    session["chapter_id"],
                    operation,
                    base_version,
                    base_draft_hash,
                    before_title_n,
                    before_content_n,
                    after_title_n,
                    after_content_n,
                    self._dump(diff),  # type: ignore[attr-defined]
                    explanation or "",
                    AssistantChangeStatus.PENDING.value,
                    now,
                ),
            )
            conn.execute(
                "UPDATE assistant_sessions SET updated_at=? WHERE id=?",
                (now, session_id),
            )
            row = self._required_row(  # type: ignore[attr-defined]
                conn.execute(
                    "SELECT * FROM assistant_change_sets WHERE id=?", (change_id,)
                ).fetchone(),
                "创建修改集",
            )
        return self._assistant_change_from_row(row)

    def get_assistant_change_set(self, change_id: str) -> AssistantChangeSet:
        from novel_agent.repository import RepositoryError

        with self.connection() as conn:  # type: ignore[attr-defined]
            row = conn.execute(
                "SELECT * FROM assistant_change_sets WHERE id=?", (change_id,)
            ).fetchone()
        if row is None:
            raise RepositoryError(f"找不到修改集：{change_id}")
        return self._assistant_change_from_row(row)

    def list_assistant_changes(self, session_id: str) -> list[AssistantChangeSet]:
        with self.connection() as conn:  # type: ignore[attr-defined]
            rows = conn.execute(
                """SELECT * FROM assistant_change_sets
                WHERE session_id=? ORDER BY created_at""",
                (session_id,),
            ).fetchall()
        return [self._assistant_change_from_row(row) for row in rows]

    def approve_assistant_change(
        self, change_id: str
    ) -> tuple[AssistantChangeSet, ChapterEditDraft]:
        from novel_agent.repository import RepositoryError

        now = utc_now()
        with self.transaction() as conn:  # type: ignore[attr-defined]
            change = conn.execute(
                "SELECT * FROM assistant_change_sets WHERE id=?", (change_id,)
            ).fetchone()
            if change is None:
                raise RepositoryError(f"找不到修改集：{change_id}")
            if change["status"] != AssistantChangeStatus.PENDING.value:
                raise AssistantChangeStateError(
                    f"修改集状态为 {change['status']}，无法批准"
                )
            chapter = conn.execute(
                "SELECT * FROM chapters WHERE id=?", (change["chapter_id"],)
            ).fetchone()
            if chapter is None:
                raise RepositoryError(f"找不到章节：{change['chapter_id']}")
            if chapter["status"] != ChapterStatus.READY.value:
                raise ChapterNotEditableError(
                    f"仅 READY 章节可编辑，当前状态为 {chapter['status']}"
                )
            if int(chapter["version"]) != int(change["base_version"]):
                raise AssistantChangeStaleError("正式章节版本已变更，修改集已过期")
            title, content, draft, current_hash = self._working_copy_on_conn(
                conn, chapter["project_id"], int(chapter["number"])
            )
            if current_hash != change["base_draft_hash"]:
                raise AssistantChangeStaleError("工作副本已变化，修改集已过期")
            after_title = normalize_draft_title(change["after_title"])
            after_content = normalize_draft_content(change["after_content"])
            content_hash = draft_content_hash(after_title, after_content)
            applied_ids: list[str] = list(draft.applied_change_ids) if draft else []
            if change_id not in applied_ids:
                applied_ids.append(change_id)
            merged_source = self._merge_draft_source(
                draft.source if draft else None, "ai"
            )
            created_at = draft.created_at if draft else now
            conn.execute(
                """INSERT INTO chapter_edit_drafts
                (chapter_id,project_id,base_version,title,content,source,
                 applied_change_ids_json,content_hash,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(chapter_id) DO UPDATE SET
                base_version=excluded.base_version,
                title=excluded.title,
                content=excluded.content,
                source=excluded.source,
                applied_change_ids_json=excluded.applied_change_ids_json,
                content_hash=excluded.content_hash,
                updated_at=excluded.updated_at""",
                (
                    chapter["id"],
                    chapter["project_id"],
                    int(chapter["version"]),
                    after_title,
                    after_content,
                    merged_source,
                    self._dump(applied_ids),  # type: ignore[attr-defined]
                    content_hash,
                    created_at,
                    now,
                ),
            )
            conn.execute(
                """UPDATE assistant_change_sets
                SET status=?, decided_at=? WHERE id=?""",
                (AssistantChangeStatus.APPROVED.value, now, change_id),
            )
            conn.execute(
                "UPDATE assistant_sessions SET updated_at=? WHERE id=?",
                (now, change["session_id"]),
            )
            change_row = self._required_row(  # type: ignore[attr-defined]
                conn.execute(
                    "SELECT * FROM assistant_change_sets WHERE id=?", (change_id,)
                ).fetchone(),
                "批准修改集",
            )
            draft_row = self._required_row(  # type: ignore[attr-defined]
                conn.execute(
                    "SELECT * FROM chapter_edit_drafts WHERE chapter_id=?",
                    (chapter["id"],),
                ).fetchone(),
                "批准后工作草稿",
            )
        return (
            self._assistant_change_from_row(change_row),
            self._edit_draft_from_row(draft_row),
        )

    def reject_assistant_change(self, change_id: str) -> AssistantChangeSet:
        from novel_agent.repository import RepositoryError

        now = utc_now()
        with self.transaction() as conn:  # type: ignore[attr-defined]
            change = conn.execute(
                "SELECT * FROM assistant_change_sets WHERE id=?", (change_id,)
            ).fetchone()
            if change is None:
                raise RepositoryError(f"找不到修改集：{change_id}")
            if change["status"] != AssistantChangeStatus.PENDING.value:
                raise AssistantChangeStateError(
                    f"修改集状态为 {change['status']}，无法拒绝"
                )
            conn.execute(
                """UPDATE assistant_change_sets
                SET status=?, decided_at=? WHERE id=?""",
                (AssistantChangeStatus.REJECTED.value, now, change_id),
            )
            conn.execute(
                "UPDATE assistant_sessions SET updated_at=? WHERE id=?",
                (now, change["session_id"]),
            )
            row = self._required_row(  # type: ignore[attr-defined]
                conn.execute(
                    "SELECT * FROM assistant_change_sets WHERE id=?", (change_id,)
                ).fetchone(),
                "拒绝修改集",
            )
        return self._assistant_change_from_row(row)

    def rollback_assistant_session(
        self,
        session_id: str,
        to_message_id: str,
        *,
        expected_draft_hash: str,
    ) -> ChapterEditDraft:
        from novel_agent.repository import RepositoryError

        now = utc_now()
        with self.transaction() as conn:  # type: ignore[attr-defined]
            session = conn.execute(
                "SELECT * FROM assistant_sessions WHERE id=? AND deleted_at IS NULL",
                (session_id,),
            ).fetchone()
            if session is None:
                raise RepositoryError(f"找不到 AI 会话：{session_id}")
            target = conn.execute(
                """SELECT * FROM assistant_messages
                WHERE id=? AND session_id=?""",
                (to_message_id, session_id),
            ).fetchone()
            if target is None:
                raise RepositoryError(f"找不到会话消息：{to_message_id}")
            if target["role"] != "user":
                raise AssistantChangeStateError("回滚目标必须是用户消息")
            chapter = conn.execute(
                "SELECT * FROM chapters WHERE id=?", (session["chapter_id"],)
            ).fetchone()
            if chapter is None:
                raise RepositoryError(f"找不到章节：{session['chapter_id']}")
            if chapter["status"] != ChapterStatus.READY.value:
                raise ChapterNotEditableError(
                    f"仅 READY 章节可编辑，当前状态为 {chapter['status']}"
                )
            _, _, draft, current_hash = self._working_copy_on_conn(
                conn, chapter["project_id"], int(chapter["number"])
            )
            if current_hash != expected_draft_hash:
                raise EditConflictError("工作副本已变化，无法回滚")
            approved = conn.execute(
                """SELECT acs.* FROM assistant_change_sets acs
                JOIN assistant_messages m ON m.id=acs.message_id
                WHERE acs.session_id=? AND acs.status=? AND m.sequence>?
                ORDER BY m.sequence ASC, acs.created_at ASC""",
                (
                    session_id,
                    AssistantChangeStatus.APPROVED.value,
                    int(target["sequence"]),
                ),
            ).fetchall()
            if not approved:
                if draft is None:
                    raise AssistantChangeStateError("没有可回滚的已批准修改")
                return draft
            latest = approved[-1]
            expected_after_hash = draft_content_hash(
                latest["after_title"], latest["after_content"]
            )
            if current_hash != expected_after_hash:
                raise EditConflictError("会话修改后又有手工编辑，禁止覆盖")
            earliest = approved[0]
            restore_title = normalize_draft_title(earliest["before_title"])
            restore_content = normalize_draft_content(earliest["before_content"])
            restore_hash = draft_content_hash(restore_title, restore_content)
            reverted_ids = {row["id"] for row in approved}
            applied_ids = [
                item
                for item in (draft.applied_change_ids if draft else [])
                if item not in reverted_ids
            ]
            created_at = draft.created_at if draft else now
            conn.execute(
                """INSERT INTO chapter_edit_drafts
                (chapter_id,project_id,base_version,title,content,source,
                 applied_change_ids_json,content_hash,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(chapter_id) DO UPDATE SET
                base_version=excluded.base_version,
                title=excluded.title,
                content=excluded.content,
                source=excluded.source,
                applied_change_ids_json=excluded.applied_change_ids_json,
                content_hash=excluded.content_hash,
                updated_at=excluded.updated_at""",
                (
                    chapter["id"],
                    chapter["project_id"],
                    int(chapter["version"]),
                    restore_title,
                    restore_content,
                    "rollback",
                    self._dump(applied_ids),  # type: ignore[attr-defined]
                    restore_hash,
                    created_at,
                    now,
                ),
            )
            for row in approved:
                conn.execute(
                    """UPDATE assistant_change_sets
                    SET status=?, reverted_at=? WHERE id=?""",
                    (AssistantChangeStatus.REVERTED.value, now, row["id"]),
                )
            conn.execute(
                "UPDATE assistant_sessions SET updated_at=? WHERE id=?",
                (now, session_id),
            )
            draft_row = self._required_row(  # type: ignore[attr-defined]
                conn.execute(
                    "SELECT * FROM chapter_edit_drafts WHERE chapter_id=?",
                    (chapter["id"],),
                ).fetchone(),
                "回滚后工作草稿",
            )
        return self._edit_draft_from_row(draft_row)

    # --- version restore / formal commit --------------------------------

    def restore_chapter_version_to_draft(
        self, project_id: str, chapter_number: int, version: int
    ) -> ChapterEditDraft:
        from novel_agent.repository import RepositoryError

        now = utc_now()
        with self.transaction() as conn:  # type: ignore[attr-defined]
            _, chapter = self._require_editable_chapter(
                conn, project_id, chapter_number, action="edit_draft"
            )
            snap = conn.execute(
                """SELECT * FROM chapter_versions
                WHERE chapter_id=? AND version=?""",
                (chapter["id"], version),
            ).fetchone()
            if snap is None:
                raise RepositoryError(f"找不到版本 v{version}")
            title = normalize_draft_title(snap["title"] or chapter["title"] or "")
            content = normalize_draft_content(snap["content"] or "")
            content_hash = draft_content_hash(title, content)
            existing = conn.execute(
                "SELECT * FROM chapter_edit_drafts WHERE chapter_id=?",
                (chapter["id"],),
            ).fetchone()
            created_at = existing["created_at"] if existing else now
            conn.execute(
                """INSERT INTO chapter_edit_drafts
                (chapter_id,project_id,base_version,title,content,source,
                 applied_change_ids_json,content_hash,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(chapter_id) DO UPDATE SET
                base_version=excluded.base_version,
                title=excluded.title,
                content=excluded.content,
                source=excluded.source,
                applied_change_ids_json=excluded.applied_change_ids_json,
                content_hash=excluded.content_hash,
                updated_at=excluded.updated_at""",
                (
                    chapter["id"],
                    project_id,
                    int(chapter["version"]),
                    title,
                    content,
                    "rollback",
                    "[]",
                    content_hash,
                    created_at,
                    now,
                ),
            )
            row = self._required_row(  # type: ignore[attr-defined]
                conn.execute(
                    "SELECT * FROM chapter_edit_drafts WHERE chapter_id=?",
                    (chapter["id"],),
                ).fetchone(),
                "恢复版本为工作草稿",
            )
        return self._edit_draft_from_row(row)

    def commit_chapter_revision(
        self,
        project_id: str,
        chapter_number: int,
        *,
        expected_base_version: int,
        expected_draft_hash: str,
        analysis: ChapterRevisionAnalysis,
        review: ReviewReport | None,
        base_characters: list[CharacterRecord],
        action: str = "commit_revision",
    ) -> ChapterRevisionResult:
        from novel_agent.repository import RepositoryError

        now = utc_now()
        with self.transaction() as conn:  # type: ignore[attr-defined]
            project, chapter = self._require_editable_chapter(
                conn, project_id, chapter_number, action=action
            )
            if int(chapter["version"]) != int(expected_base_version):
                raise EditConflictError(
                    f"正式版本已变更：期望 v{expected_base_version}，当前 v{chapter['version']}"
                )
            draft_row = conn.execute(
                "SELECT * FROM chapter_edit_drafts WHERE chapter_id=?",
                (chapter["id"],),
            ).fetchone()
            if draft_row is None:
                raise EditConflictError("没有可提交的工作草稿")
            draft = self._edit_draft_from_row(draft_row)
            if draft.content_hash != expected_draft_hash:
                raise EditConflictError("工作草稿已被其他操作更新")
            if int(draft.base_version) != int(chapter["version"]):
                raise EditConflictError("工作草稿基于的正式版本已过期")

            title = normalize_draft_title(draft.title)
            content = normalize_draft_content(draft.content)
            kind = _KIND_BY_SOURCE.get(draft.source, "MIXED_EDIT")
            old_words = count_content_chars(chapter["content"])
            new_words = count_content_chars(content)
            next_row = self._required_row(  # type: ignore[attr-defined]
                conn.execute(
                    """SELECT COALESCE(MAX(version),0)+1 AS next_version
                    FROM chapter_versions WHERE chapter_id=?""",
                    (chapter["id"],),
                ).fetchone(),
                "计算修订版本号",
            )
            version = int(next_row["next_version"])
            metadata = {
                "official": True,
                "source": draft.source,
                "review": review,
                "timeline_event": analysis.timeline_event,
                "character_updates": analysis.character_updates,
                "world_facts": analysis.world_facts,
                "introduced_foreshadows": analysis.introduced_foreshadows,
                "resolved_foreshadows": analysis.resolved_foreshadows,
                "assistant_change_ids": draft.applied_change_ids,
            }
            conn.execute(
                """INSERT INTO chapter_versions
                (chapter_id,version,kind,content,metadata_json,created_at,title,source,is_official)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    chapter["id"],
                    version,
                    kind,
                    content,
                    self._dump(metadata),  # type: ignore[attr-defined]
                    now,
                    title,
                    draft.source,
                    1,
                ),
            )
            conn.execute(
                """UPDATE chapters
                SET title=?, content=?, summary=?, version=?, status=?, updated_at=?
                WHERE id=?""",
                (
                    title,
                    content,
                    analysis.summary,
                    version,
                    ChapterStatus.READY.value,
                    now,
                    chapter["id"],
                ),
            )

            activity_source = "agent" if draft.source == "ai" else "user"
            activity_meta_note = {
                "revision_source": draft.source,
                "had_ai": draft.source in {"ai", "mixed"},
                "assistant_change_ids": draft.applied_change_ids,
            }
            self.record_writing_activity(  # type: ignore[attr-defined]
                project_id=project_id,
                chapter_id=chapter["id"],
                chapter_title=title,
                source=activity_source,
                operation="update",
                old_word_count=old_words,
                new_word_count=new_words,
                created_at=now,
                conn=conn,
            )
            # Store AI note on mixed revisions via review_reports-style metadata
            # already embedded in chapter_versions.metadata_json.
            _ = activity_meta_note

            # Clear derived memory for current + later chapters.
            conn.execute(
                "DELETE FROM timeline_events WHERE project_id=? AND chapter_number>=?",
                (project_id, chapter_number),
            )
            conn.execute(
                """DELETE FROM world_facts
                WHERE project_id=? AND evidence_chapter>=? AND locked=0""",
                (project_id, chapter_number),
            )
            conn.execute(
                "DELETE FROM foreshadows WHERE project_id=? AND introduced_chapter>=?",
                (project_id, chapter_number),
            )
            conn.execute(
                """UPDATE foreshadows SET status='OPEN', resolved_chapter=NULL
                WHERE project_id=? AND resolved_chapter>=?""",
                (project_id, chapter_number),
            )

            later = conn.execute(
                "SELECT id,number,title,status,content,summary,plan_json,version FROM chapters "
                "WHERE project_id=? AND number>?",
                (project_id, chapter_number),
            ).fetchall()
            later_ids = [row["id"] for row in later]
            reset_numbers = [int(row["number"]) for row in later]
            all_touch_ids = [chapter["id"], *later_ids]

            if all_touch_ids:
                placeholders = ",".join("?" for _ in all_touch_ids)
                conn.execute(
                    f"""DELETE FROM semantic_documents
                    WHERE project_id=? AND chapter_id IN ({placeholders})""",
                    (project_id, *all_touch_ids),
                )

            # Insert revised chapter memory.
            conn.execute(
                """INSERT OR IGNORE INTO timeline_events
                (project_id,chapter_number,event,created_at) VALUES (?,?,?,?)""",
                (project_id, chapter_number, analysis.timeline_event, now),
            )
            for fact in analysis.world_facts:
                conn.execute(
                    """INSERT INTO world_facts
                    (id,project_id,category,statement,evidence_chapter,version,locked)
                    VALUES (?,?,?,?,?,?,0)""",
                    (
                        new_id("fact"),
                        project_id,
                        fact.category,
                        fact.statement,
                        chapter_number,
                        1,
                    ),
                )
            for label in analysis.introduced_foreshadows:
                text = str(label).strip()
                if not text:
                    continue
                conn.execute(
                    """INSERT INTO foreshadows
                    (project_id,label,status,introduced_chapter,resolved_chapter)
                    VALUES (?,?,?,?,NULL)
                    ON CONFLICT(project_id,label) DO UPDATE SET
                    status='OPEN',
                    introduced_chapter=excluded.introduced_chapter,
                    resolved_chapter=NULL""",
                    (project_id, text, "OPEN", chapter_number),
                )
            for label in analysis.resolved_foreshadows:
                text = str(label).strip()
                if not text:
                    continue
                existing_fs = conn.execute(
                    "SELECT id FROM foreshadows WHERE project_id=? AND label=?",
                    (project_id, text),
                ).fetchone()
                if existing_fs:
                    conn.execute(
                        """UPDATE foreshadows
                        SET status='RESOLVED', resolved_chapter=? WHERE id=?""",
                        (chapter_number, existing_fs["id"]),
                    )
                else:
                    conn.execute(
                        """INSERT INTO foreshadows
                        (project_id,label,status,introduced_chapter,resolved_chapter)
                        VALUES (?,?,?,?,?)""",
                        (project_id, text, "RESOLVED", chapter_number, chapter_number),
                    )

            # RESET_ARCHIVE later chapters, then reset to PLANNED (keep versions).
            for row in later:
                prev_content = row["content"]
                prev_version = int(row["version"] or 0)
                if prev_content or prev_version > 0 or row["status"] != ChapterStatus.PLANNED.value:
                    archive_row = self._required_row(  # type: ignore[attr-defined]
                        conn.execute(
                            """SELECT COALESCE(MAX(version),0)+1 AS next_version
                            FROM chapter_versions WHERE chapter_id=?""",
                            (row["id"],),
                        ).fetchone(),
                        "计算 RESET_ARCHIVE 版本",
                    )
                    archive_version = int(archive_row["next_version"])
                    plan_payload = (
                        json.loads(row["plan_json"]) if row["plan_json"] else {}
                    )
                    conn.execute(
                        """INSERT INTO chapter_versions
                        (chapter_id,version,kind,content,metadata_json,created_at,
                         title,source,is_official)
                        VALUES (?,?,?,?,?,?,?,?,?)""",
                        (
                            row["id"],
                            archive_version,
                            "RESET_ARCHIVE",
                            prev_content or "",
                            self._dump(  # type: ignore[attr-defined]
                                {
                                    "official": False,
                                    "reset_by_chapter": chapter_number,
                                    "previous_status": row["status"],
                                    "previous_version": prev_version,
                                    "summary": row["summary"],
                                    "plan": plan_payload,
                                }
                            ),
                            now,
                            row["title"],
                            "workflow",
                            0,
                        ),
                    )

            if later_ids:
                placeholders = ",".join("?" for _ in later_ids)
                research_rows = conn.execute(
                    f"""SELECT id FROM research_sources
                    WHERE project_id=? AND chapter_id IN ({placeholders})""",
                    (project_id, *later_ids),
                ).fetchall()
                research_ids = [str(r["id"]) for r in research_rows]
                if research_ids:
                    research_placeholders = ",".join("?" for _ in research_ids)
                    conn.execute(
                        f"""DELETE FROM semantic_documents WHERE project_id=?
                        AND source_type='research_source'
                        AND source_id IN ({research_placeholders})""",
                        (project_id, *research_ids),
                    )
                conn.execute(
                    f"""DELETE FROM research_sources
                    WHERE project_id=? AND chapter_id IN ({placeholders})""",
                    (project_id, *later_ids),
                )
                conn.execute(
                    f"DELETE FROM review_reports WHERE chapter_id IN ({placeholders})",
                    later_ids,
                )
                conn.execute(
                    f"DELETE FROM publish_tasks WHERE chapter_id IN ({placeholders})",
                    later_ids,
                )
                conn.execute(
                    f"DELETE FROM runs WHERE project_id=? AND chapter_id IN ({placeholders})",
                    (project_id, *later_ids),
                )
                conn.execute(
                    f"DELETE FROM chapter_edit_drafts WHERE chapter_id IN ({placeholders})",
                    later_ids,
                )
                conn.execute(
                    f"""UPDATE chapters SET status=?, content=NULL, summary=NULL,
                    plan_json=NULL, version=0, locked=0, updated_at=?
                    WHERE id IN ({placeholders})""",
                    (ChapterStatus.PLANNED.value, now, *later_ids),
                )

            # Rebuild characters from brief base + official versions through current.
            retained = conn.execute(
                """SELECT c.number,c.plan_json,cv.metadata_json
                FROM chapters c
                LEFT JOIN chapter_versions cv ON cv.id=(
                    SELECT id FROM chapter_versions
                    WHERE chapter_id=c.id AND is_official=1
                    ORDER BY version DESC LIMIT 1
                )
                WHERE c.project_id=? AND c.number<=? AND c.status=?
                ORDER BY c.number""",
                (project_id, chapter_number, ChapterStatus.READY.value),
            ).fetchall()
            conn.execute("DELETE FROM characters WHERE project_id=?", (project_id,))
            for character in base_characters:
                conn.execute(
                    """INSERT INTO characters
                    (id,project_id,name,role,immutable_facts_json,current_state_json,version)
                    VALUES (?,?,?,?,?,?,?)""",
                    (
                        character.id,
                        project_id,
                        character.name,
                        character.role,
                        self._dump(character.immutable_facts),  # type: ignore[attr-defined]
                        self._dump(character.current_state),  # type: ignore[attr-defined]
                        character.version,
                    ),
                )
            for row in retained:
                raw_updates: list[Any] = []
                if row["metadata_json"]:
                    meta = json.loads(row["metadata_json"])
                    raw_updates = meta.get("character_updates") or []
                if not raw_updates and row["plan_json"]:
                    raw_updates = json.loads(row["plan_json"]).get("character_updates") or []
                updates = [
                    CharacterMemoryUpdate.model_validate(item) for item in raw_updates
                ]
                self._apply_character_updates(  # type: ignore[attr-defined]
                    conn, project_id, int(row["number"]), updates
                )

            # Keep PAUSED if paused; otherwise leave status unchanged.
            conn.execute(
                """UPDATE projects SET current_chapter=?, updated_at=? WHERE id=?""",
                (chapter_number, now, project_id),
            )
            conn.execute(
                "DELETE FROM chapter_edit_drafts WHERE chapter_id=?",
                (chapter["id"],),
            )

            chapter_row = self._required_row(  # type: ignore[attr-defined]
                conn.execute(
                    "SELECT * FROM chapters WHERE id=?", (chapter["id"],)
                ).fetchone(),
                "读取修订后章节",
            )

        memory_changes = {
            "characters": [
                {"name": item.name, "change": item.current_goal or item.last_result or "更新"}
                for item in analysis.character_updates
            ],
            "timeline": [{"event": analysis.timeline_event}],
            "world_facts": [
                {"category": item.category, "statement": item.statement}
                for item in analysis.world_facts
            ],
            "foreshadows": {
                "introduced": list(analysis.introduced_foreshadows),
                "resolved": list(analysis.resolved_foreshadows),
            },
        }
        return ChapterRevisionResult(
            chapter=self._chapter(chapter_row),  # type: ignore[attr-defined]
            reset_chapters=reset_numbers,
            memory_changes=memory_changes,
            warnings=[],
            semantic_index_status="pending",
        )

    def commit_failed_chapter_review(
        self,
        project_id: str,
        chapter_number: int,
        *,
        expected_base_version: int,
        expected_draft_hash: str,
        analysis: ChapterRevisionAnalysis,
        review: ReviewReport | None,
        base_characters: list[CharacterRecord],
    ) -> ChapterRevisionResult:
        return self.commit_chapter_revision(
            project_id,
            chapter_number,
            expected_base_version=expected_base_version,
            expected_draft_hash=expected_draft_hash,
            analysis=analysis,
            review=review,
            base_characters=base_characters,
            action="submit_for_review",
        )

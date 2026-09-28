from __future__ import annotations

from typing import Any

from novel_agent.diffutil import build_text_diff
from novel_agent.models import (
    AssistantChangeSet,
    AssistantGatewayResponse,
    AssistantMessage,
    AssistantMessageCreate,
    AssistantMode,
    AssistantSession,
    ChapterDraftUpdate,
    ChapterEditDraft,
    ChapterRevisionAnalysis,
    ChapterRevisionCommitRequest,
    ChapterRevisionResult,
    ChapterSelection,
    ChapterStatus,
    ContinuityContext,
    ProjectStatus,
    ReviewDecision,
    ReviewReport,
)
from novel_agent.repository import RepositoryError
from novel_agent.revision_errors import (
    ChapterNotEditableError,
    EditConflictError,
    RevisionAnalysisError,
)
from novel_agent.telemetry import llm_call_scope
from novel_agent.text_normalize import (
    draft_content_hash,
    normalize_draft_content,
    normalize_draft_title,
)


class ChapterWorkspaceMixin:
    """Reading/revision workspace orchestration for NovelAgentService."""

    def get_chapter_workspace(self, project_id: str, chapter_number: int) -> dict[str, Any]:
        project = self.repository.get_project(project_id)
        chapter = self.repository.get_chapter_by_number(project_id, chapter_number)
        if chapter is None:
            raise RepositoryError(f"找不到第{chapter_number}章")
        draft = self.repository.get_chapter_edit_draft(project_id, chapter_number)
        editable = chapter.status == ChapterStatus.READY
        read_only_reason = None
        if not editable:
            read_only_reason = f"仅 READY 章节可修订（当前 {chapter.status.value}）"
        elif project.status == ProjectStatus.ARCHIVED:
            editable = False
            read_only_reason = "归档项目不可修订"
        chapters = self.repository.list_chapters(project_id)
        later = [c for c in chapters if c.number > chapter_number]
        downstream = {
            "count": len(later),
            "first_number": later[0].number if later else None,
            "last_number": later[-1].number if later else None,
        }
        versions = self.repository.list_chapter_versions(project_id, chapter_number)
        sessions = self.repository.list_assistant_sessions(project_id, chapter_number)
        return {
            "project": {
                "id": project.id,
                "title": project.title,
                "status": project.status.value,
            },
            "chapter": chapter,
            "draft": draft,
            "editable": editable,
            "read_only_reason": read_only_reason,
            "downstream": downstream,
            "versions": versions,
            "sessions": sessions,
        }

    def save_chapter_edit_draft(
        self,
        project_id: str,
        chapter_number: int,
        update: ChapterDraftUpdate,
    ) -> ChapterEditDraft:
        self._assert_workspace_project(project_id)
        return self.repository.upsert_chapter_edit_draft(
            project_id, chapter_number, update, source="manual"
        )

    def discard_chapter_edit_draft(self, project_id: str, chapter_number: int) -> None:
        self._assert_workspace_project(project_id)
        self.repository.delete_chapter_edit_draft(project_id, chapter_number)

    def restore_chapter_version(
        self, project_id: str, chapter_number: int, version: int
    ) -> ChapterEditDraft:
        self._assert_workspace_project(project_id)
        return self.repository.restore_chapter_version_to_draft(
            project_id, chapter_number, version
        )

    def commit_chapter_edit_draft(
        self,
        project_id: str,
        chapter_number: int,
        request: ChapterRevisionCommitRequest,
    ) -> ChapterRevisionResult:
        project = self._assert_workspace_project(project_id)
        draft = self.repository.get_chapter_edit_draft(project_id, chapter_number)
        if draft is None:
            raise EditConflictError("没有可提交的工作草稿")
        if draft.content_hash != request.expected_draft_hash:
            raise EditConflictError("工作草稿已被其他操作更新")
        if draft.base_version != request.base_version:
            raise EditConflictError("工作草稿基于的正式版本已过期")

        chapter = self.repository.get_chapter_by_number(project_id, chapter_number)
        if chapter is None or chapter.status != ChapterStatus.READY:
            raise ChapterNotEditableError("只有 READY 章节可以提交修订")

        characters = self.repository.list_characters(project_id)
        with llm_call_scope(
            project_id=project_id,
            chapter_id=chapter.id,
            category="revision",
        ):
            try:
                analysis = self.gateway.analyze_chapter_revision(
                    project=project,
                    chapter=chapter,
                    title=draft.title,
                    content=draft.content,
                    characters=characters,
                )
            except Exception as exc:
                raise RevisionAnalysisError(f"修订分析失败：{exc}") from exc

        warnings: list[str] = []
        review: ReviewReport | None = None
        try:
            previous = [
                item
                for item in self.repository.list_chapters(project_id)
                if item.number < chapter_number and item.status == ChapterStatus.READY
            ][-6:]
            continuity = ContinuityContext(
                skill_name="revision-continuity",
                skill_source="workspace-revision",
                project_id=project_id,
                chapter_number=chapter_number,
                creative_request=project.request.model_dump(mode="json"),
                creative_brief=project.brief.model_dump(mode="json"),
                chapter_plan=(chapter.plan.model_dump(mode="json") if chapter.plan else {}),
                current_draft=draft.content,
                recent_chapters=[
                    {
                        "number": item.number,
                        "title": item.title,
                        "summary": item.summary or "",
                        "ending_excerpt": (item.content or "")[-1200:],
                    }
                    for item in previous
                ],
                characters=[item.model_dump(mode="json") for item in characters],
                world_facts=[
                    item.model_dump(mode="json")
                    for item in self.repository.list_world_facts(project_id)
                ],
                timeline=self.repository.list_timeline(project_id)[-40:],
                foreshadows=self.repository.list_foreshadows(project_id),
            )
            instructions = ""
            if hasattr(self.story_skills, "continuity_instructions"):
                try:
                    instructions = self.story_skills.continuity_instructions() or ""
                except Exception:
                    instructions = ""
            review = self.gateway.review_continuity(continuity, instructions)
            if review.decision in {ReviewDecision.REVISE, ReviewDecision.HUMAN_REQUIRED}:
                warnings.append(
                    f"连续性审校建议关注：{review.decision.value}（评分 {review.score}）"
                )
        except Exception as exc:
            warnings.append(f"连续性审校未能完成：{exc}")

        base_characters = self._character_records(
            project_id, project.request, project.brief
        )
        result = self.repository.commit_chapter_revision(
            project_id,
            chapter_number,
            expected_base_version=request.base_version,
            expected_draft_hash=request.expected_draft_hash,
            analysis=analysis,
            review=review,
            base_characters=base_characters,
        )
        result = result.model_copy(update={"warnings": [*result.warnings, *warnings]})

        semantic_status = "skipped"
        if getattr(self.embedding, "enabled", False):
            try:
                updated = self.repository.get_chapter_by_number(project_id, chapter_number)
                if updated and updated.content:
                    self._reindex_chapter_semantics(project_id, updated)
                    semantic_status = "updated"
            except Exception as exc:
                semantic_status = "failed"
                result = result.model_copy(
                    update={
                        "warnings": [
                            *result.warnings,
                            f"语义索引更新失败：{exc}",
                        ]
                    }
                )
        return result.model_copy(update={"semantic_index_status": semantic_status})

    def create_assistant_session(
        self, project_id: str, chapter_number: int
    ) -> AssistantSession:
        self._assert_workspace_project(project_id)
        chapter = self.repository.get_chapter_by_number(project_id, chapter_number)
        if chapter is None:
            raise RepositoryError(f"找不到第{chapter_number}章")
        return self.repository.create_assistant_session(
            project_id, chapter_number, title=f"第{chapter_number}章修订会话"
        )

    def list_assistant_sessions(
        self, project_id: str, chapter_number: int
    ) -> list[AssistantSession]:
        self._assert_workspace_project(project_id)
        return self.repository.list_assistant_sessions(project_id, chapter_number)

    def get_assistant_messages(self, session_id: str) -> list[AssistantMessage]:
        session = self.repository.get_assistant_session(session_id)
        self._assert_workspace_project(session.project_id)
        return self.repository.list_assistant_messages(session_id)

    def list_assistant_changes(self, session_id: str) -> list[AssistantChangeSet]:
        session = self.repository.get_assistant_session(session_id)
        self._assert_workspace_project(session.project_id)
        return self.repository.list_assistant_changes(session_id)

    def delete_assistant_session(self, session_id: str) -> None:
        session = self.repository.get_assistant_session(session_id)
        self._assert_workspace_project(session.project_id)
        self.repository.delete_assistant_session(session_id)

    def send_assistant_message(
        self, session_id: str, request: AssistantMessageCreate
    ) -> dict[str, Any]:
        session = self.repository.get_assistant_session(session_id)
        project = self._assert_workspace_project(session.project_id)
        chapter = self.repository.get_chapter(session.chapter_id)
        if chapter.status != ChapterStatus.READY:
            raise ChapterNotEditableError("只有 READY 章节可以使用修订助手")

        working = self.repository.get_or_create_working_copy(
            session.project_id, chapter.number
        )
        title, content, _draft, content_hash = working
        if request.selection is not None:
            self._validate_selection(request.selection, content, chapter.version, content_hash)

        user_message = self.repository.append_assistant_message(
            session_id,
            role="user",
            mode=request.mode,
            content=request.content,
            selection=request.selection,
            metadata={"quick_action": request.quick_action} if request.quick_action else None,
        )

        with llm_call_scope(
            project_id=session.project_id,
            chapter_id=chapter.id,
            category="assistant",
        ):
            response: AssistantGatewayResponse = self.gateway.respond_to_chapter_assistant(
                mode=request.mode,
                user_message=self._compose_user_prompt(request),
                selection=request.selection,
                project=project,
                chapter=chapter,
                working_title=title,
                working_content=content,
                recent_summaries=self._recent_summaries(session.project_id, chapter.number),
                characters=self.repository.list_characters(session.project_id),
                world_facts=self.repository.list_world_facts(session.project_id),
                timeline=self.repository.list_timeline(session.project_id),
            )

        change_set: AssistantChangeSet | None = None
        proposal_meta: dict[str, Any] = {}
        if request.mode == AssistantMode.EDITOR and response.proposal is not None:
            proposal = response.proposal
            after_title = normalize_draft_title(proposal.title)
            after_content = normalize_draft_content(proposal.content)
            if not after_title or not after_content:
                raise RevisionAnalysisError("编辑提案标题或正文无效")
            if after_title == title and after_content == content:
                response = response.model_copy(
                    update={
                        "message": response.message or "未发现需要修改的内容。",
                        "proposal": None,
                    }
                )
            else:
                operation = proposal.operation
                if request.selection is not None:
                    operation = "edit_chapter"
                diff_json = build_text_diff(
                    before_title=title,
                    before_content=content,
                    after_title=after_title,
                    after_content=after_content,
                )
                assistant_message = self.repository.append_assistant_message(
                    session_id,
                    role="assistant",
                    mode=request.mode,
                    content=response.message,
                    metadata={"has_proposal": True, "explanation": proposal.explanation},
                )
                change_set = self.repository.create_assistant_change_set(
                    session_id,
                    assistant_message.id,
                    operation=operation,
                    base_version=chapter.version,
                    base_draft_hash=content_hash,
                    before_title=title,
                    before_content=content,
                    after_title=after_title,
                    after_content=after_content,
                    diff_json=diff_json,
                    explanation=proposal.explanation,
                )
                proposal_meta = {"change_id": change_set.id}
                return {
                    "user_message": user_message,
                    "assistant_message": assistant_message,
                    "change_set": change_set,
                }

        assistant_message = self.repository.append_assistant_message(
            session_id,
            role="assistant",
            mode=request.mode,
            content=response.message,
            metadata=proposal_meta,
        )
        return {
            "user_message": user_message,
            "assistant_message": assistant_message,
            "change_set": change_set,
        }

    def approve_assistant_change(self, change_id: str) -> dict[str, Any]:
        change = self.repository.get_assistant_change_set(change_id)
        session = self.repository.get_assistant_session(change.session_id)
        self._assert_workspace_project(session.project_id)
        updated, draft = self.repository.approve_assistant_change(change_id)
        return {"change_set": updated, "draft": draft}

    def reject_assistant_change(self, change_id: str) -> AssistantChangeSet:
        change = self.repository.get_assistant_change_set(change_id)
        session = self.repository.get_assistant_session(change.session_id)
        self._assert_workspace_project(session.project_id)
        return self.repository.reject_assistant_change(change_id)

    def rollback_assistant_session(
        self, session_id: str, *, to_message_id: str, expected_draft_hash: str
    ) -> ChapterEditDraft:
        session = self.repository.get_assistant_session(session_id)
        self._assert_workspace_project(session.project_id)
        return self.repository.rollback_assistant_session(
            session_id, to_message_id, expected_draft_hash=expected_draft_hash
        )

    def _assert_workspace_project(self, project_id: str):
        project = self.repository.get_project(project_id)
        if project.status == ProjectStatus.DRAFT and not project.confirmed:
            raise ChapterNotEditableError("请先确认创作方案")
        if project.status == ProjectStatus.ARCHIVED:
            raise ChapterNotEditableError("归档项目不可修订")
        return project

    def _recent_summaries(self, project_id: str, chapter_number: int) -> list[str]:
        chapters = self.repository.list_chapters(project_id)
        summaries: list[str] = []
        for chapter in chapters:
            if chapter.number >= chapter_number:
                break
            if chapter.summary:
                summaries.append(f"第{chapter.number}章：{chapter.summary}")
        return summaries[-6:]

    @staticmethod
    def _validate_selection(
        selection: ChapterSelection,
        content: str,
        chapter_version: int,
        draft_hash: str,
    ) -> None:
        if selection.chapter_version != chapter_version:
            raise EditConflictError("选区对应的正式版本已过期")
        if selection.draft_hash != draft_hash:
            raise EditConflictError("选区对应的工作草稿已过期，请重新选择")
        chars = list(content)
        if selection.end > len(chars) or selection.start >= selection.end:
            raise EditConflictError("选区范围无效")
        slice_text = "".join(chars[selection.start : selection.end])
        if slice_text != selection.text:
            raise EditConflictError("选区文本与正文不匹配")

    @staticmethod
    def _compose_user_prompt(request: AssistantMessageCreate) -> str:
        parts = [request.content.strip()]
        if request.quick_action:
            labels = {
                "polish": "请润色选中段落，保持原意。",
                "shorten": "请精简选中段落，保留关键信息。",
                "expand": "请扩写选中段落，增加画面与细节。",
                "visualize": "请增强选中段落的画面感与感官细节。",
                "dialogue": "请调整选中对白，让语气更自然。",
            }
            parts.insert(0, labels.get(request.quick_action, ""))
        return "\n".join(p for p in parts if p)

    def _reindex_chapter_semantics(self, project_id: str, chapter) -> None:
        if not hasattr(self.repository, "delete_semantic_documents_for_chapter"):
            return
        # Best-effort: embedding reindex is optional for this MVP.
        try:
            from novel_agent.semantic import index_chapter_content  # type: ignore
        except Exception:
            return
        index_chapter_content(self.repository, self.embedding, project_id, chapter)

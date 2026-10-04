from __future__ import annotations

from enum import StrEnum

from novel_agent.models import ChapterStatus, ProjectStatus, ReviewReport


class WorkspaceAction(StrEnum):
    EDIT_DRAFT = "edit_draft"
    ASSISTANT = "use_assistant"
    COMMIT_REVISION = "commit_revision"
    SUBMIT_FAILED_REVIEW = "submit_for_review"
    REPLAN = "replan"
    ACCEPT_WITH_WARNINGS = "accept_with_warnings"


def workspace_capabilities(
    chapter_status: str,
    project_status: str,
    *,
    can_accept_with_warnings: bool = False,
) -> dict[str, bool]:
    archived = project_status == ProjectStatus.ARCHIVED.value
    ready = chapter_status == ChapterStatus.READY.value
    failed = chapter_status == ChapterStatus.FAILED.value
    if archived:
        return {
            "edit_draft": False,
            "use_assistant": False,
            "commit_revision": False,
            "submit_for_review": False,
            "replan": False,
            "accept_with_warnings": False,
        }
    if ready:
        return {
            "edit_draft": True,
            "use_assistant": True,
            "commit_revision": True,
            "submit_for_review": False,
            "replan": False,
            "accept_with_warnings": False,
        }
    if failed:
        return {
            "edit_draft": True,
            "use_assistant": True,
            "commit_revision": False,
            "submit_for_review": True,
            "replan": True,
            "accept_with_warnings": bool(can_accept_with_warnings),
        }
    return {
        "edit_draft": False,
        "use_assistant": False,
        "commit_revision": False,
        "submit_for_review": False,
        "replan": False,
        "accept_with_warnings": False,
    }


def capability_denied_reason(
    action: WorkspaceAction,
    capabilities: dict[str, bool],
    status: str,
) -> str | None:
    mapping = {
        WorkspaceAction.EDIT_DRAFT: "edit_draft",
        WorkspaceAction.ASSISTANT: "use_assistant",
        WorkspaceAction.COMMIT_REVISION: "commit_revision",
        WorkspaceAction.SUBMIT_FAILED_REVIEW: "submit_for_review",
        WorkspaceAction.REPLAN: "replan",
        WorkspaceAction.ACCEPT_WITH_WARNINGS: "accept_with_warnings",
    }
    key = mapping[action]
    if capabilities.get(key):
        return None
    if action == WorkspaceAction.COMMIT_REVISION and status == ChapterStatus.FAILED.value:
        return "未通过审核的章节不能通过普通应用修订成为正式正文，请重新送审"
    if action == WorkspaceAction.ACCEPT_WITH_WARNINGS:
        return "当前章节仍有硬阻断或结构性问题，不能接受当前版本并继续"
    return f"当前章节状态为 {status}，不能执行该操作"


def compute_accept_with_warnings(report: ReviewReport | None, content: str) -> bool:
    from novel_agent.features.chapter_review.issue_policy import can_accept_with_warnings

    return can_accept_with_warnings(report, content)

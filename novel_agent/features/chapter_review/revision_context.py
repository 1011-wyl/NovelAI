from __future__ import annotations

from typing import Any

from novel_agent.models import (
    ReviewIssue,
    ReviewReport,
    StrictModel,
)


class ChapterRevisionContext(StrictModel):
    project_id: str
    chapter_number: int
    target_chars: int
    creative_request: dict[str, Any]
    creative_brief: dict[str, Any]
    chapter_plan: dict[str, Any]
    quality_contract: dict[str, Any]
    current_draft: str
    previous_chapter_excerpt: str = ""
    opening_anchor: dict[str, Any] | None = None
    character_archives: list[dict[str, Any] | str]
    world_rules: list[str]
    review: ReviewReport
    revision_number: int


def prioritized_issues(report: ReviewReport) -> list[ReviewIssue]:
    order = {"BLOCKER": 0, "MAJOR": 1, "MINOR": 2}
    return sorted(
        report.issues,
        key=lambda issue: (order.get(issue.severity.value, 9), issue.category, issue.message),
    )


def revision_instruction_payload(report: ReviewReport) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for issue in prioritized_issues(report):
        payload.append(
            {
                "category": issue.category,
                "severity": issue.severity.value,
                "message": issue.message,
                "evidence": list(issue.evidence),
                "suggestion": issue.suggestion,
            }
        )
    return payload

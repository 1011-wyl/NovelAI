from __future__ import annotations

import hashlib
import re
from enum import StrEnum

from novel_agent.features.chapter_planning.rework_policy import classify_rework_mode
from novel_agent.features.chapter_planning.models import ReworkMode
from novel_agent.models import ChapterPlan, IssueSeverity, ReviewDecision, ReviewIssue, ReviewReport

_WHITESPACE = re.compile(r"\s+")

SOFT_CATEGORIES = {
    "length",
    "text",
    "repetition",
    "prose",
    "prose_ai_style",
    "dialogue",
    "readability",
}
SOFT_PREFIXES = ("readability", "prose", "length")
HARD_CATEGORIES = {
    "constraint",
    "opening",
    "anchor",
    "continuity",
    "world",
    "plot",
    "character_state",
}
HARD_PREFIXES = ("continuity", "opening", "anchor", "world", "structural")
UNKNOWN_CATEGORY = "unknown_category"


class RecoveryAction(StrEnum):
    REVISE = "revise"
    REPLAN = "replan"
    STOP = "stop"


def issue_fingerprint(report: ReviewReport) -> str:
    parts: list[str] = []
    for issue in report.issues:
        if issue.severity not in {IssueSeverity.MAJOR, IssueSeverity.BLOCKER}:
            continue
        message = _WHITESPACE.sub(" ", issue.message).strip().casefold()
        parts.append(f"{issue.category}|{issue.severity.value}|{message}")
    return "\n".join(sorted(parts))


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _is_soft_issue(issue: ReviewIssue) -> bool:
    category = issue.category or UNKNOWN_CATEGORY
    if category == UNKNOWN_CATEGORY or category.startswith("unknown"):
        return False
    if category in SOFT_CATEGORIES:
        return True
    if any(category.startswith(prefix) for prefix in SOFT_PREFIXES):
        return True
    return False


def _is_hard_major(issue: ReviewIssue) -> bool:
    if issue.severity == IssueSeverity.BLOCKER:
        return True
    if issue.severity != IssueSeverity.MAJOR:
        return False
    category = issue.category or UNKNOWN_CATEGORY
    if category == UNKNOWN_CATEGORY or category.startswith("unknown"):
        return True
    if category in HARD_CATEGORIES:
        return True
    if any(category.startswith(prefix) for prefix in HARD_PREFIXES):
        return True
    if category in {"character"} and "缺失" in issue.message:
        return False
    if category == "character" and any(
        token in issue.message for token in ("关系", "初态", "知识", "死亡", "世界")
    ):
        return True
    return False


def has_hard_blockers(report: ReviewReport) -> bool:
    return any(
        issue.severity == IssueSeverity.BLOCKER or _is_hard_major(issue)
        for issue in report.issues
    )


def can_accept_with_warnings(report: ReviewReport | None, content: str) -> bool:
    """Quality pass is only score > 60; this override cannot bypass that rule."""
    if report is None:
        return False
    stripped = (content or "").strip()
    if not stripped or any(marker in stripped for marker in ("[截断]", "因长度上限而被截断")):
        return False
    if (report.quality_status or "") in {"GENERATION_FAILED", "LENGTH_REPAIRING", "LENGTH_NEEDS_ATTENTION"}:
        return False
    from novel_agent.features.chapter_review.decision import decide_quality

    if decide_quality(report.score) != ReviewDecision.PASS:
        return False
    if any(issue.severity == IssueSeverity.BLOCKER for issue in report.issues):
        return False
    return True


def resolve_recovery_action(
    report: ReviewReport,
    *,
    plan: ChapterPlan | None,
    chapter_number: int,
    replanned: bool,
    same_content: bool,
    stagnant: bool,
) -> RecoveryAction:
    if same_content:
        return RecoveryAction.STOP
    classified = classify_rework_mode(report, chapter_number, plan)
    structural = classified == ReworkMode.REPLAN and has_hard_blockers(report)
    if stagnant and not replanned:
        return RecoveryAction.REPLAN
    if stagnant and replanned:
        return RecoveryAction.STOP
    if structural and not replanned:
        return RecoveryAction.REPLAN
    if structural and replanned:
        return RecoveryAction.STOP
    return RecoveryAction.REVISE

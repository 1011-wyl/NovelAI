from __future__ import annotations

from novel_agent.features.chapter_planning.errors import ReworkModeNotAllowedError
from novel_agent.features.chapter_planning.models import ReworkMode
from novel_agent.models import ChapterPlan, IssueSeverity, ReviewReport

_SOFT_CATEGORY_PREFIXES = (
    "readability",
    "length",
    "text",
    "prose",
    "repetition",
    "dialogue",
    "template",
)

_HARD_CATEGORY_PREFIXES = (
    "opening",
    "anchor",
    "continuity",
    "world",
    "constraint",
    "story",
)

_REPLAN_TEXT_MARKERS = (
    "opening_anchor",
    "开篇锚点",
    "上一章",
    "承接上一章",
    "承接前文",
    "character knowledge",
    "character state",
    "人物初态",
    "人物关系",
    "plot consistency",
    "连续性",
    "世界规则",
    "能力起点",
    "must_establish",
    "建立项",
    "forbidden_assumptions",
)

_REUSE_TEXT_MARKERS = (
    "长度",
    "字数",
    "模板",
    "套话",
    "对话",
    "句式",
    "节奏",
    "冗余",
    "可读性",
    "length",
    "prose",
    "dialogue",
    "template",
    "opening_hook",
    "scene_causality",
    "conflict_escalation",
    "character_agency",
    "showing_specificity",
    "reader_payoff",
    "ending_hook",
)


def _is_soft_category(category: str) -> bool:
    lowered = (category or "").lower()
    return any(
        lowered == prefix or lowered.startswith(f"{prefix}.") or lowered.startswith(f"{prefix}_")
        for prefix in _SOFT_CATEGORY_PREFIXES
    )


def _is_hard_category(category: str) -> bool:
    lowered = (category or "").lower()
    if _is_soft_category(lowered):
        return False
    return any(
        lowered == prefix or lowered.startswith(f"{prefix}.") or lowered.startswith(f"{prefix}_")
        for prefix in _HARD_CATEGORY_PREFIXES
    )


def classify_rework_mode(
    report: ReviewReport | None,
    chapter_number: int,
    plan: ChapterPlan | None,
) -> ReworkMode:
    if report is None:
        return ReworkMode.REPLAN
    serious = [
        issue
        for issue in report.issues
        if issue.severity in {IssueSeverity.MAJOR, IssueSeverity.BLOCKER}
    ]
    if any(_is_hard_category(issue.category) for issue in serious):
        return ReworkMode.REPLAN
    blob_parts = [report.decision.value, str(report.score)]
    for issue in report.issues:
        blob_parts.extend([issue.category, issue.message, issue.suggestion])
    blob = "\n".join(blob_parts).lower()
    if any(marker.lower() in blob for marker in _REPLAN_TEXT_MARKERS):
        return ReworkMode.REPLAN
    if any(_is_soft_category(issue.category) for issue in serious) or any(
        marker.lower() in blob for marker in _REUSE_TEXT_MARKERS
    ):
        return ReworkMode.REUSE_PLAN
    if plan is not None and serious and all(_is_soft_category(issue.category) for issue in serious):
        return ReworkMode.REUSE_PLAN
    return ReworkMode.REPLAN


def resolve_requested_mode(
    requested: str | ReworkMode | None,
    *,
    report: ReviewReport | None,
    chapter_number: int,
    plan: ChapterPlan | None,
) -> ReworkMode:
    classified = classify_rework_mode(report, chapter_number, plan)
    raw = requested.value if isinstance(requested, ReworkMode) else str(requested or "auto").strip().lower()
    if raw in {"", "auto"}:
        return classified
    if raw == ReworkMode.REPLAN.value:
        return ReworkMode.REPLAN
    if raw == ReworkMode.REUSE_PLAN.value:
        if classified == ReworkMode.REPLAN:
            raise ReworkModeNotAllowedError(
                "当前失败涉及开篇、人物状态、连续性或世界规则，必须重新规划"
            )
        return ReworkMode.REUSE_PLAN
    return classified

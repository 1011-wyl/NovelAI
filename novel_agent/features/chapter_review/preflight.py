from __future__ import annotations

import re
from dataclasses import dataclass, field

from novel_agent.features.chapter_planning.validation import CHAPTER1_FORBIDDEN_PHRASES
from novel_agent.features.chapter_review.decision import QualityStatus
from novel_agent.features.chapter_review.quality_spec import (
    DEFAULT_QUALITY_CONTRACT,
    ChapterQualityContract,
    classify_length,
    count_quality_chars,
    length_bounds,
)
from novel_agent.features.story_design.models import OpeningChapterAnchor
from novel_agent.models import (
    ChapterPlan,
    IssueSeverity,
    ProjectRecord,
    ReviewDecision,
    ReviewIssue,
    ReviewReport,
)

_TRUNCATION_MARKERS = ("[截断]", "因长度上限而被截断", "...(truncated)")


@dataclass(slots=True)
class PreflightResult:
    report: ReviewReport
    can_skip_expensive_review: bool
    passed: bool
    technical_failed: bool = False
    length_class: str = "ok"
    actual_length: int = 0
    quality_status: str = ""
    issues: list[ReviewIssue] = field(default_factory=list)

    def as_review_report(self) -> ReviewReport:
        return self.report


def run_preflight(
    project: ProjectRecord,
    plan: ChapterPlan,
    protagonist_name: str,
    content: str,
    has_research: bool,
    *,
    opening_anchor: OpeningChapterAnchor | None = None,
    spec: ChapterQualityContract | None = None,
    contract: ChapterQualityContract | None = None,
) -> PreflightResult:
    active = contract or spec or DEFAULT_QUALITY_CONTRACT
    issues: list[ReviewIssue] = []
    checks: dict[str, float] = {}
    target = max(1, project.request.chapter_target_chars)
    bounds = length_bounds(target, active)
    body_chars = count_quality_chars(content)
    length_class = classify_length(body_chars, target, active)
    length_ratio = body_chars / target
    checks["structural.length"] = min(100.0, round(length_ratio * 100, 1))
    stripped = (content or "").strip()
    truncated = any(marker in (content or "") for marker in _TRUNCATION_MARKERS)
    technical_failed = False

    if not stripped:
        technical_failed = True
        issues.append(
            ReviewIssue(
                category="constraint",
                severity=IssueSeverity.BLOCKER,
                message="正文为空",
                suggestion="重新生成完整章节，不得提交空稿",
                evidence=["current_draft 为空"],
            )
        )
    if truncated:
        technical_failed = True
        issues.append(
            ReviewIssue(
                category="constraint",
                severity=IssueSeverity.BLOCKER,
                message="正文被供应商标记为截断",
                suggestion="缩短输出或提高输出预算后重写完整章节",
                evidence=[marker for marker in _TRUNCATION_MARKERS if marker in content],
            )
        )

    # Length findings are informational for the length-repair loop; they must not
    # become a second quality veto via MAJOR severity.
    if stripped and not truncated and length_class in {"short", "severe_short"}:
        issues.append(
            ReviewIssue(
                category="length",
                severity=IssueSeverity.MINOR,
                message=(
                    f"章节长度 {body_chars} 字，目标范围 "
                    f"{bounds['accepted_length_min']}～{bounds['accepted_length_max']}"
                ),
                suggestion="保持已有剧情定向补写，不得整章无约束重写或灌水",
                evidence=[
                    f"body_chars={body_chars}",
                    f"target={target}",
                    f"length_class={length_class}",
                ],
            )
        )
    elif stripped and not truncated and length_class == "over":
        issues.append(
            ReviewIssue(
                category="length",
                severity=IssueSeverity.MINOR,
                message=(
                    f"章节长度 {body_chars} 字，超出建议上限 {bounds['accepted_length_max']}"
                ),
                suggestion="仅在明显影响阅读时压缩冗余，不得因此判定质量失败",
                evidence=[f"body_chars={body_chars}", f"target={target}"],
            )
        )

    forbidden_terms: list[str] = []
    for item in project.request.exclude:
        term = re.sub(r"^(不要|避免|禁止|无)", "", item).strip()
        if term and term in (content or ""):
            forbidden_terms.append(term)
            technical_failed = True
            issues.append(
                ReviewIssue(
                    category="constraint",
                    severity=IssueSeverity.BLOCKER,
                    message=f"正文出现明确排除项：{term}",
                    suggestion=f"删除禁止项：{term}",
                    evidence=[term],
                )
            )
    checks["structural.constraints"] = (
        100.0 if not forbidden_terms and stripped and not truncated else 0.0
    )
    if protagonist_name and protagonist_name in (content or ""):
        checks["structural.character"] = 100.0
    else:
        checks["structural.character"] = 70.0
        if protagonist_name:
            issues.append(
                ReviewIssue(
                    category="character",
                    severity=IssueSeverity.MINOR,
                    message="正文未出现主角姓名，请确认第一人称或代称叙事是否足够清楚",
                    suggestion=f"如非第一人称，应让读者能识别{protagonist_name}正在推动情节",
                    evidence=[f"protagonist_name={protagonist_name}"],
                )
            )
    paragraphs = [p.strip() for p in (content or "").split("\n\n") if p.strip()]
    unique_ratio = len(set(paragraphs)) / max(1, len(paragraphs))
    checks["structural.repetition"] = round(unique_ratio * 100, 1)
    if paragraphs and unique_ratio < 0.8:
        issues.append(
            ReviewIssue(
                category="repetition",
                severity=IssueSeverity.MINOR,
                message="段落重复率偏高，建议修订时压缩重复信息",
                suggestion="重写重复段落并增加推进信息",
                evidence=[paragraphs[0][:80]],
            )
        )
    checks["structural.plot"] = (
        100.0 if plan.hook[:8] in (content or "") or "下一" in (content or "") else 75.0
    )
    checks["structural.factuality"] = (
        100.0 if not plan.research_questions or has_research else 78.0
    )
    if plan.number == 1:
        for phrase in CHAPTER1_FORBIDDEN_PHRASES:
            if phrase in (content or ""):
                technical_failed = True
                issues.append(
                    ReviewIssue(
                        category="opening",
                        severity=IssueSeverity.BLOCKER,
                        message=f"第一章正文包含禁用前情表达：{phrase}",
                        suggestion="删除对不存在上一章的承接，从当前现场起笔",
                        evidence=[phrase],
                    )
                )
        if opening_anchor is not None:
            for item in opening_anchor.forbidden_assumptions:
                if item and item in (content or ""):
                    issues.append(
                        ReviewIssue(
                            category="opening",
                            severity=IssueSeverity.MAJOR,
                            message=f"正文把禁止提前成立的事实写成当前事实：{item}",
                            suggestion="删除或改写尚未发生的设定，只保留第一章可成立的现场",
                            evidence=[item],
                        )
                    )

    # Preflight score is diagnostic only; final quality uses readability dimensions.
    diagnostic_score = round(sum(checks.values()) / max(1, len(checks)), 1)
    needs_length_repair = length_class in {"short", "severe_short"} and not technical_failed
    if technical_failed:
        decision = ReviewDecision.REVISE
        quality_status = QualityStatus.GENERATION_FAILED.value
        can_skip = True
    elif needs_length_repair:
        decision = ReviewDecision.REVISE
        quality_status = QualityStatus.LENGTH_REPAIRING.value
        # Skip expensive quality scoring until length is in range / exhausted.
        can_skip = True
    else:
        decision = ReviewDecision.REVISE  # pending quality gate
        quality_status = QualityStatus.QUALITY_REVIEWING.value
        can_skip = False

    report = ReviewReport(
        decision=decision,
        score=diagnostic_score,
        issues=issues,
        checks=checks,
        quality_status=quality_status,
        actual_length=body_chars,
        target_length=bounds["target_length"],
        accepted_length_min=bounds["accepted_length_min"],
        accepted_length_max=bounds["accepted_length_max"],
        pass_score_exclusive=active.pass_score_exclusive,
    )
    return PreflightResult(
        report=report,
        can_skip_expensive_review=can_skip,
        passed=False,
        technical_failed=technical_failed,
        length_class=length_class,
        actual_length=body_chars,
        quality_status=quality_status,
        issues=issues,
    )

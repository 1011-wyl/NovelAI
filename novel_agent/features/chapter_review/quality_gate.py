from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from novel_agent.features.chapter_planning.continuity_guard import relationship_guard_issues
from novel_agent.features.chapter_review.decision import QualityStatus, decide_quality
from novel_agent.features.chapter_review.issue_policy import UNKNOWN_CATEGORY
from novel_agent.features.chapter_review.preflight import run_preflight
from novel_agent.features.chapter_review.quality_spec import (
    DEFAULT_QUALITY_CONTRACT,
    READABILITY_DIMENSION_SUGGESTIONS,
    READABILITY_DIMENSIONS,
    ChapterQualityContract,
    compute_quality_score,
    length_bounds,
)
from novel_agent.features.story_design.models import OpeningChapterAnchor
from novel_agent.models import (
    ChapterPlan,
    CharacterRecord,
    IssueSeverity,
    ProjectRecord,
    ReadabilityContext,
    ReviewDecision,
    ReviewIssue,
    ReviewReport,
)
from novel_agent.ports import LLMGateway
from novel_agent.story_skills import StorySkillsRuntime
from novel_agent.writing_skills import OhStoryWritingRuntime

CHECK_ALIASES = {
    "length": "structural.length",
    "constraints": "structural.constraints",
    "character": "structural.character",
    "originality": "structural.repetition",
    "plot": "structural.plot",
    "factuality": "structural.factuality",
    "prose_naturalness": "prose.template_density",
    "semantic": "continuity.semantic",
    "timeline": "continuity.timeline",
}


def extract_dimension_scores(checks: dict[str, float]) -> dict[str, float]:
    scores: dict[str, float] = {}
    for name in READABILITY_DIMENSIONS:
        if name in checks:
            scores[name] = float(checks[name])
        elif f"readability.{name}" in checks:
            scores[name] = float(checks[f"readability.{name}"])
        elif f"readability_{name}" in checks:
            scores[name] = float(checks[f"readability_{name}"])
    return scores


def merge_review_reports(
    base: ReviewReport,
    extra: ReviewReport,
    *,
    contract: ChapterQualityContract = DEFAULT_QUALITY_CONTRACT,
) -> ReviewReport:
    """Merge issues/checks; quality_score comes only from readability dimensions when present."""
    issues: list[ReviewIssue] = []
    seen: set[tuple[str, str]] = set()
    for issue in [*base.issues, *extra.issues]:
        key = (issue.category, issue.message)
        if key in seen:
            continue
        seen.add(key)
        issues.append(issue)
    checks = {**base.checks, **extra.checks}
    dim_scores = extract_dimension_scores(checks)
    if len(dim_scores) == len(READABILITY_DIMENSIONS):
        score = compute_quality_score(dim_scores, contract)
    else:
        base_dims = extract_dimension_scores(base.checks)
        if len(base_dims) == len(READABILITY_DIMENSIONS):
            score = compute_quality_score(base_dims, contract)
        else:
            score = float(base.score)
    decision = decide_quality(score, contract)
    return ReviewReport(
        decision=decision,
        score=score,
        issues=issues,
        checks=checks,
        quality_status=base.quality_status or extra.quality_status,
        pass_score_exclusive=contract.pass_score_exclusive,
        actual_length=base.actual_length or extra.actual_length,
        target_length=base.target_length or extra.target_length,
        accepted_length_min=base.accepted_length_min or extra.accepted_length_min,
        accepted_length_max=base.accepted_length_max or extra.accepted_length_max,
    )


def namespace_checks(checks: dict[str, float]) -> dict[str, float]:
    namespaced: dict[str, float] = {}
    for key, value in checks.items():
        if key in CHECK_ALIASES:
            namespaced[CHECK_ALIASES[key]] = value
        elif key in READABILITY_DIMENSIONS:
            namespaced[f"readability.{key}"] = value
        elif key.startswith("readability_"):
            namespaced[f"readability.{key.removeprefix('readability_')}"] = value
        else:
            namespaced[key] = value
    return namespaced


def lowest_component(checks: dict[str, float]) -> str | None:
    if not checks:
        return None
    return min(checks.items(), key=lambda item: (item[1], item[0]))[0]


def sanitize_review_issues(issues: list[ReviewIssue]) -> list[ReviewIssue]:
    cleaned: list[ReviewIssue] = []
    known_prefixes = (
        "length",
        "text",
        "repetition",
        "constraint",
        "character",
        "opening",
        "anchor",
        "continuity",
        "world",
        "plot",
        "prose",
        "readability",
        "story",
        "dialogue",
        "structural",
    )
    for issue in issues:
        category = issue.category or UNKNOWN_CATEGORY
        if not any(category == prefix or category.startswith(prefix) for prefix in known_prefixes):
            category = UNKNOWN_CATEGORY
        evidence = list(issue.evidence)
        severity = issue.severity
        if severity in {IssueSeverity.MAJOR, IssueSeverity.BLOCKER} and not evidence:
            dim = category.removeprefix("readability_").removeprefix("readability.")
            if dim in READABILITY_DIMENSIONS and "分" in issue.message:
                evidence = [f"维度 {dim} 得分偏低，建议优先修订"]
            else:
                severity = IssueSeverity.MINOR
        cleaned.append(
            issue.model_copy(
                update={
                    "category": category,
                    "severity": severity,
                    "evidence": evidence,
                }
            )
        )
    return cleaned


def annotate_report(
    report: ReviewReport,
    *,
    review_attempt: int = 0,
    max_review_attempts: int = 0,
    revision_count: int = 0,
    length_repair_count: int = 0,
    next_action: str = "",
    score_trace: list[float] | None = None,
    preflight_only: bool = False,
    quality_status: str = "",
    selected_score: float | None = None,
    best_attempt_index: int = 0,
    contract: ChapterQualityContract = DEFAULT_QUALITY_CONTRACT,
    force_decision: ReviewDecision | None = None,
) -> ReviewReport:
    checks = namespace_checks(report.checks)
    issues = sanitize_review_issues(report.issues)
    blocking = sum(1 for issue in issues if issue.severity == IssueSeverity.BLOCKER)
    major = sum(1 for issue in issues if issue.severity == IssueSeverity.MAJOR)
    minor = sum(1 for issue in issues if issue.severity == IssueSeverity.MINOR)
    dim_scores = extract_dimension_scores(checks)
    if len(dim_scores) == len(READABILITY_DIMENSIONS):
        score = compute_quality_score(dim_scores, contract)
    else:
        score = report.score
    if force_decision is not None:
        decision = force_decision
    elif quality_status in {
        QualityStatus.GENERATION_FAILED.value,
        QualityStatus.LENGTH_REPAIRING.value,
        QualityStatus.LENGTH_NEEDS_ATTENTION.value,
    }:
        decision = ReviewDecision.REVISE
    else:
        decision = decide_quality(score, contract)
    status = quality_status or report.quality_status
    if not status:
        if decision == ReviewDecision.PASS:
            status = QualityStatus.PASSED.value
        else:
            status = QualityStatus.QUALITY_REVISING.value
    resolved_selected_score = selected_score
    if resolved_selected_score is None and not preflight_only:
        resolved_selected_score = score
    return report.model_copy(
        update={
            "decision": decision,
            "score": score,
            "issues": issues,
            "checks": checks,
            "blocking_issue_count": blocking,
            "major_issue_count": major,
            "minor_issue_count": minor,
            "lowest_component": lowest_component(checks),
            "review_attempt": review_attempt,
            "max_review_attempts": max_review_attempts,
            "revision_count": revision_count,
            "length_repair_count": length_repair_count,
            "next_action": next_action,
            "score_trace": list(score_trace or []),
            "preflight_only": preflight_only,
            "issue_fingerprint": "",
            "quality_status": status,
            "pass_score_exclusive": contract.pass_score_exclusive,
            # A preflight/length failure has not produced a quality score.  Keep
            # this nullable instead of turning the technical placeholder score
            # (0.0) into a user-visible review result.
            "selected_score": resolved_selected_score,
            "best_attempt_index": best_attempt_index,
            "actual_length": report.actual_length,
            "target_length": report.target_length,
            "accepted_length_min": report.accepted_length_min,
            "accepted_length_max": report.accepted_length_max,
        }
    )


def readability_context(
    project: ProjectRecord,
    plan: ChapterPlan,
    content: str,
    previous_chapter_excerpt: str,
    quality_contract: dict[str, Any] | None = None,
) -> ReadabilityContext:
    request = project.request
    brief = project.brief
    # Chapter 1 must not receive previous-chapter continuity payload.
    excerpt = "" if plan.number == 1 else previous_chapter_excerpt[-800:]
    return ReadabilityContext(
        project_id=project.id,
        chapter_number=plan.number,
        creative_request={
            "audience_channel": request.audience_channel,
            "genre": request.genre,
            "experiences": request.experiences,
            "elements": request.elements,
            "protagonist_tags": request.protagonist_tags,
            "romance": request.romance,
            "idea": request.idea,
            "must_have": request.must_have,
            "nice_to_have": request.nice_to_have,
            "exclude": request.exclude,
            "chapter_target_chars": request.chapter_target_chars,
        },
        creative_brief={
            "synopsis": brief.synopsis,
            "target_readers": brief.target_readers,
            "selling_points": brief.selling_points,
            "protagonist_name": brief.protagonist_name,
            "protagonist_profile": brief.protagonist_profile,
            "character_profiles": [
                {
                    "name": item.name,
                    "role": item.role,
                    "personality": item.personality,
                    "core_goal": item.core_goal,
                    "relationships": item.relationships,
                }
                for item in brief.character_profiles
            ],
            "main_conflict": brief.main_conflict,
            "world_rules": brief.world_rules,
            "style_guide": brief.style_guide,
            "reader_contract": brief.reader_contract,
            "core_expectation": brief.core_expectation,
        },
        chapter_plan={
            "number": plan.number,
            "title": plan.title,
            "objective": plan.objective,
            "conflict": plan.conflict,
            "turning_point": plan.turning_point,
            "hook": plan.hook,
            "scenes": plan.scenes,
            "story_stage": plan.story_stage,
            "plot_unit": plan.plot_unit,
            "chapter_position": plan.chapter_position,
            "target_emotion": plan.target_emotion,
            "reader_payoff": plan.reader_payoff,
            "new_expectation": plan.new_expectation,
            "protagonist_goal": plan.protagonist_goal,
            "critical_choice": plan.critical_choice,
            "opening_hook": plan.opening_hook,
            "forbidden_releases": plan.forbidden_releases,
            "relationship_changes": plan.relationship_changes,
            "information_gap": plan.information_gap,
            "scene_beats": [item.model_dump(mode="json") for item in plan.scene_beats],
        },
        current_draft=content,
        previous_chapter_excerpt=excerpt,
        quality_contract=quality_contract or {},
    )


def review_structural(
    project: ProjectRecord,
    plan: ChapterPlan,
    protagonist_name: str,
    content: str,
    has_research: bool,
    opening_anchor: OpeningChapterAnchor | None = None,
) -> ReviewReport:
    return run_preflight(
        project,
        plan,
        protagonist_name,
        content,
        has_research,
        opening_anchor=opening_anchor,
    ).as_review_report()


def ensure_dimension_guidance(report: ReviewReport) -> ReviewReport:
    """Attach revision guidance for weak dimensions; never inject quality vetoes."""
    checks = dict(report.checks)
    issues = list(report.issues)
    represented = {
        issue.category.removeprefix("readability_").removeprefix("readability.")
        for issue in issues
    }
    desired = DEFAULT_QUALITY_CONTRACT.desired_generation_score
    for name in READABILITY_DIMENSIONS:
        value = float(checks.get(name, checks.get(f"readability.{name}", 100.0)))
        if value >= desired or name in represented:
            continue
        issues.append(
            ReviewIssue(
                category=f"readability.{name}",
                severity=IssueSeverity.MAJOR if value <= 60 else IssueSeverity.MINOR,
                message=f"可读性维度 {name} 仅得 {value:.1f} 分",
                suggestion=READABILITY_DIMENSION_SUGGESTIONS[name],
                evidence=[f"维度 {name} 得分 {value:.1f}，写作目标 {desired:.0f}"],
            )
        )
    return report.model_copy(update={"issues": issues})


@dataclass(slots=True)
class ChapterQualityGate:
    gateway: LLMGateway
    story_skills: StorySkillsRuntime
    writing_skills: OhStoryWritingRuntime
    spec: ChapterQualityContract = DEFAULT_QUALITY_CONTRACT

    def review(
        self,
        *,
        repository: Any,
        project: ProjectRecord,
        plan: ChapterPlan,
        content: str,
        protagonist_name: str,
        previous_chapter_excerpt: str,
        has_research: bool,
        characters: list[CharacterRecord],
        opening_anchor: OpeningChapterAnchor | None = None,
        quality_contract: dict[str, Any] | None = None,
        review_attempt: int = 0,
        max_review_attempts: int = 0,
        revision_count: int = 0,
        length_repair_count: int = 0,
        score_trace: list[float] | None = None,
        selected_score: float | None = None,
        best_attempt_index: int = 0,
    ) -> ReviewReport:
        preflight = run_preflight(
            project,
            plan,
            protagonist_name,
            content,
            has_research,
            opening_anchor=opening_anchor,
            contract=self.spec,
        )
        report = preflight.report
        bounds = length_bounds(project.request.chapter_target_chars, self.spec)
        report = report.model_copy(
            update={
                "actual_length": preflight.actual_length,
                "target_length": bounds["target_length"],
                "accepted_length_min": bounds["accepted_length_min"],
                "accepted_length_max": bounds["accepted_length_max"],
            }
        )
        preflight_only = False
        force_decision: ReviewDecision | None = None
        quality_status = preflight.quality_status

        if preflight.technical_failed:
            preflight_only = True
            force_decision = ReviewDecision.REVISE
            quality_status = QualityStatus.GENERATION_FAILED.value
        elif preflight.length_class in {"short", "severe_short"}:
            preflight_only = True
            force_decision = ReviewDecision.REVISE
            quality_status = QualityStatus.LENGTH_REPAIRING.value
        else:
            if self.writing_skills.enabled:
                prose_audit = self.writing_skills.audit_prose(content)
                report = merge_review_reports(
                    report,
                    self.writing_skills.as_review_report(prose_audit),
                    contract=self.spec,
                )
            readability_report = ensure_dimension_guidance(
                self.gateway.review_readability(
                    readability_context(
                        project,
                        plan,
                        content,
                        previous_chapter_excerpt if plan.number > 1 else "",
                        quality_contract,
                    )
                )
            )
            report = merge_review_reports(report, readability_report, contract=self.spec)
            if self.story_skills.enabled:
                skill_report = self.story_skills.audit(
                    repository,
                    self.gateway,
                    project,
                    plan,
                    content,
                )
                report = report.model_copy(
                    update={
                        "issues": sanitize_review_issues(
                            [*report.issues, *skill_report.issues]
                        ),
                        "checks": {**report.checks, **namespace_checks(skill_report.checks)},
                    }
                )
            if plan.number > 1:
                guard_issues = relationship_guard_issues(
                    content,
                    brief=project.brief,
                    characters=characters,
                    chapter_number=plan.number,
                )
                if guard_issues:
                    report = report.model_copy(
                        update={"issues": sanitize_review_issues([*report.issues, *guard_issues])}
                    )
            quality_status = QualityStatus.QUALITY_REVIEWING.value

        return annotate_report(
            report,
            review_attempt=review_attempt,
            max_review_attempts=max_review_attempts,
            revision_count=revision_count,
            length_repair_count=length_repair_count,
            score_trace=score_trace,
            preflight_only=preflight_only,
            quality_status=quality_status,
            selected_score=selected_score,
            best_attempt_index=best_attempt_index,
            contract=self.spec,
            force_decision=force_decision,
        )

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from novel_agent.features.chapter_review.candidates import ChapterCandidate, choose_best
from novel_agent.features.chapter_review.decision import QualityStatus, decide_quality
from novel_agent.features.chapter_review.issue_policy import (
    RecoveryAction,
    content_hash,
    issue_fingerprint,
    resolve_recovery_action,
)
from novel_agent.features.chapter_review.quality_gate import (
    ChapterQualityGate,
    annotate_report,
    extract_dimension_scores,
)
from novel_agent.features.chapter_review.quality_spec import (
    DEFAULT_QUALITY_CONTRACT,
    ChapterQualityContract,
    classify_length,
    count_quality_chars,
    length_bounds,
)
from novel_agent.features.chapter_review.revision_context import ChapterRevisionContext
from novel_agent.features.story_design.models import OpeningChapterAnchor
from novel_agent.models import (
    ChapterPlan,
    CharacterRecord,
    ProjectRecord,
    ReviewDecision,
    ReviewReport,
)


class QualityLoopHost(Protocol):
    def persist_attempt(
        self,
        content: str,
        report: ReviewReport,
        *,
        review_attempt: int,
        revision_count: int,
        recovery_action: str,
        preflight_only: bool,
    ) -> None: ...

    def emit_quality(
        self,
        message: str,
        *,
        review_attempt: int,
        revision_count: int,
        report: ReviewReport,
        next_action: str,
    ) -> None: ...

    def write_chapter(self, plan: ChapterPlan) -> str: ...

    def revise_chapter(self, context: ChapterRevisionContext) -> str: ...

    def replan_chapter(self) -> ChapterPlan: ...

    def build_revision_context(
        self,
        plan: ChapterPlan,
        content: str,
        report: ReviewReport,
        revision_number: int,
        quality_contract: dict[str, Any],
    ) -> ChapterRevisionContext: ...


def merge_length_repair(original: str, response: str) -> str:
    """Merge an append-only length repair without allowing the draft to shrink.

    New gateways return only the added scene fragment.  The compatibility
    branches accept older gateways that still return the complete chapter.
    """
    base = (original or "").strip()
    candidate = (response or "").strip()
    if not candidate or content_hash(candidate) == content_hash(base):
        return base
    if candidate.startswith(base):
        return candidate

    # An older/full-chapter response normally contains the original opening.
    # Accept it only when it actually grows; never replace a draft by a shorter
    # rewrite during the length-repair phase.
    compact_base = "".join(base.split())
    signature = compact_base[: min(40, len(compact_base))]
    compact_candidate = "".join(candidate.split())
    if signature and compact_candidate.startswith(signature):
        return candidate if count_quality_chars(candidate) > count_quality_chars(base) else base

    # Keep the existing ending hook last by inserting the new fragment before
    # the final paragraph.  A one-paragraph draft falls back to appending.
    paragraphs = [part.strip() for part in base.split("\n\n") if part.strip()]
    if len(paragraphs) >= 2:
        return "\n\n".join([*paragraphs[:-1], candidate, paragraphs[-1]])
    return f"{base}\n\n{candidate}".strip()


@dataclass(slots=True)
class QualityLoopResult:
    content: str
    plan: ChapterPlan
    report: ReviewReport
    passed: bool
    revision_count: int
    review_attempts: int
    replanned: bool
    length_repair_count: int = 0
    score_trace: list[float] = field(default_factory=list)
    best_attempt_index: int = 1
    selected_score: float | None = None


@dataclass(slots=True)
class ChapterQualityRecovery:
    host: QualityLoopHost
    gate: ChapterQualityGate
    max_revision_attempts: int
    spec: ChapterQualityContract = DEFAULT_QUALITY_CONTRACT

    def run(
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
        opening_anchor: OpeningChapterAnchor | None,
        quality_contract: dict[str, Any],
        initial_action: str = "initial",
    ) -> QualityLoopResult:
        revision_count = 0
        length_repair_count = 0
        review_attempt = 0
        replanned = False
        score_trace: list[float] = []
        previous_hash = ""
        previous_fingerprint = ""
        previous_attempt_score = -1.0
        current_plan = plan
        current = content
        last_action = initial_action
        max_reviews = self.max_revision_attempts + 1
        target = project.request.chapter_target_chars
        bounds = length_bounds(target, self.spec)
        attempt_index = 0
        best: ChapterCandidate | None = None

        while True:
            # --- Length gate (does not consume quality revision budget) ---
            length_class = classify_length(count_quality_chars(current), target, self.spec)
            if length_class in {"short", "severe_short"}:
                if length_repair_count >= self.spec.max_length_repairs:
                    report = ReviewReport(
                        decision=ReviewDecision.REVISE,
                        score=0.0,
                        issues=[],
                        quality_status=QualityStatus.LENGTH_NEEDS_ATTENTION.value,
                        pass_score_exclusive=self.spec.pass_score_exclusive,
                        actual_length=count_quality_chars(current),
                        target_length=bounds["target_length"],
                        accepted_length_min=bounds["accepted_length_min"],
                        accepted_length_max=bounds["accepted_length_max"],
                        length_repair_count=length_repair_count,
                        revision_count=revision_count,
                        score_trace=score_trace,
                        selected_score=best.quality_score if best else None,
                        best_attempt_index=best.attempt_index if best else 0,
                    )
                    report = annotate_report(
                        report,
                        revision_count=revision_count,
                        length_repair_count=length_repair_count,
                        score_trace=score_trace,
                        preflight_only=True,
                        quality_status=QualityStatus.LENGTH_NEEDS_ATTENTION.value,
                        selected_score=best.quality_score if best else None,
                        best_attempt_index=best.attempt_index if best else 0,
                        contract=self.spec,
                        force_decision=ReviewDecision.REVISE,
                    )
                    self.host.persist_attempt(
                        current,
                        report,
                        review_attempt=review_attempt,
                        revision_count=revision_count,
                        recovery_action="length_exhausted",
                        preflight_only=True,
                    )
                    self.host.emit_quality(
                        (
                            f"字数补写已用尽：当前 {report.actual_length} 字，"
                            f"目标范围 {bounds['accepted_length_min']}～{bounds['accepted_length_max']}"
                        ),
                        review_attempt=review_attempt,
                        revision_count=revision_count,
                        report=report,
                        next_action="length_needs_attention",
                    )
                    return QualityLoopResult(
                        content=current,
                        plan=current_plan,
                        report=report,
                        passed=False,
                        revision_count=revision_count,
                        review_attempts=review_attempt,
                        replanned=replanned,
                        length_repair_count=length_repair_count,
                        score_trace=score_trace,
                        best_attempt_index=best.attempt_index if best else 0,
                        selected_score=best.quality_score if best else None,
                    )

                current_length = count_quality_chars(current)
                gap_min = max(0, bounds["accepted_length_min"] - current_length)
                gap_max = max(gap_min, bounds["accepted_length_max"] - current_length)
                # Ask for a safety margin because model estimates include
                # punctuation/whitespace that the quality counter excludes.
                addition_min = min(gap_max, max(gap_min + 120, (gap_min * 3 + 1) // 2))
                addition_max = min(gap_max, addition_min + 120)
                length_repair_count += 1
                last_action = "length_repair"
                self.host.emit_quality(
                    f"字数不足，正在定向补写约 {addition_min}～{addition_max} 字"
                    f"（第 {length_repair_count} 次）",
                    review_attempt=review_attempt,
                    revision_count=revision_count,
                    report=ReviewReport(
                        decision=ReviewDecision.REVISE,
                        score=0,
                        quality_status=QualityStatus.LENGTH_REPAIRING.value,
                        actual_length=count_quality_chars(current),
                        target_length=bounds["target_length"],
                        accepted_length_min=bounds["accepted_length_min"],
                        accepted_length_max=bounds["accepted_length_max"],
                    ),
                    next_action="length_repair",
                )
                stub_report = ReviewReport(
                    decision=ReviewDecision.REVISE,
                    score=0,
                    issues=[],
                    quality_status=QualityStatus.LENGTH_REPAIRING.value,
                )
                # Encode length-repair intent into revision number metadata via contract copy.
                length_contract = {
                    **quality_contract,
                    "length_repair": True,
                    "length_gap_chars": gap_min,
                    "length_addition_min": addition_min,
                    "length_addition_max": addition_max,
                    "length_repair_returns_fragment": True,
                    "keep_plot": True,
                }
                context = self.host.build_revision_context(
                    current_plan,
                    current,
                    stub_report,
                    length_repair_count,
                    length_contract,
                )
                expanded = self.host.revise_chapter(context)
                current = merge_length_repair(current, expanded)
                continue

            review_attempt += 1
            report = self.gate.review(
                repository=repository,
                project=project,
                plan=current_plan,
                content=current,
                protagonist_name=protagonist_name,
                previous_chapter_excerpt=previous_chapter_excerpt,
                has_research=has_research,
                characters=characters,
                opening_anchor=opening_anchor,
                quality_contract=quality_contract,
                review_attempt=review_attempt,
                max_review_attempts=max_reviews,
                revision_count=revision_count,
                length_repair_count=length_repair_count,
                score_trace=score_trace,
                selected_score=best.quality_score if best else None,
                best_attempt_index=best.attempt_index if best else 0,
            )

            if report.quality_status == QualityStatus.GENERATION_FAILED.value:
                self.host.persist_attempt(
                    current,
                    report,
                    review_attempt=review_attempt,
                    revision_count=revision_count,
                    recovery_action=last_action,
                    preflight_only=True,
                )
                self.host.emit_quality(
                    "生成未完成或技术失败，不进入质量评分",
                    review_attempt=review_attempt,
                    revision_count=revision_count,
                    report=report,
                    next_action="generation_failed",
                )
                return QualityLoopResult(
                    content=current,
                    plan=current_plan,
                    report=report,
                    passed=False,
                    revision_count=revision_count,
                    review_attempts=review_attempt,
                    replanned=replanned,
                    length_repair_count=length_repair_count,
                    score_trace=score_trace,
                )

            attempt_index += 1
            fingerprint = issue_fingerprint(report)
            score_trace.append(report.score)
            candidate = ChapterCandidate(
                content=current,
                quality_score=report.score,
                report=report,
                dimension_scores=extract_dimension_scores(report.checks),
                issues=list(report.issues),
                length=count_quality_chars(current),
                source=last_action if last_action != "initial" else "initial",
                attempt_index=attempt_index,
            )
            if best is None:
                best = candidate
            else:
                best = choose_best(best, candidate, target_chars=target, contract=self.spec)

            # Always evaluate pass against the best retained candidate.
            best_decision = decide_quality(best.quality_score, self.spec)
            selected_report = best.report or report
            report = annotate_report(
                selected_report,
                review_attempt=review_attempt,
                max_review_attempts=max_reviews,
                revision_count=revision_count,
                length_repair_count=length_repair_count,
                score_trace=score_trace,
                preflight_only=report.preflight_only,
                quality_status=(
                    QualityStatus.PASSED.value
                    if best_decision == ReviewDecision.PASS
                    else report.quality_status or QualityStatus.QUALITY_REVISING.value
                ),
                selected_score=best.quality_score,
                best_attempt_index=best.attempt_index,
                contract=self.spec,
                force_decision=best_decision,
            )
            report = report.model_copy(
                update={"issue_fingerprint": issue_fingerprint(selected_report)}
            )
            self.host.persist_attempt(
                best.content,
                report,
                review_attempt=review_attempt,
                revision_count=revision_count,
                recovery_action=last_action,
                preflight_only=report.preflight_only,
            )

            if best_decision == ReviewDecision.PASS:
                report = report.model_copy(
                    update={
                        "next_action": "commit_ready",
                        "decision": ReviewDecision.PASS,
                        "score": best.quality_score,
                        "quality_status": QualityStatus.PASSED.value,
                        "selected_score": best.quality_score,
                        "best_attempt_index": best.attempt_index,
                    }
                )
                self.host.emit_quality(
                    (
                        f"质量检查通过：最终采用 {best.quality_score:.1f} 分"
                        f"（第 {best.attempt_index} 版），通过条件 > {self.spec.pass_score_exclusive}"
                    ),
                    review_attempt=review_attempt,
                    revision_count=revision_count,
                    report=report,
                    next_action="commit_ready",
                )
                return QualityLoopResult(
                    content=best.content,
                    plan=current_plan,
                    report=report,
                    passed=True,
                    revision_count=revision_count,
                    review_attempts=review_attempt,
                    replanned=replanned,
                    length_repair_count=length_repair_count,
                    score_trace=score_trace,
                    best_attempt_index=best.attempt_index,
                    selected_score=best.quality_score,
                )

            if revision_count >= self.max_revision_attempts:
                final_decision = decide_quality(best.quality_score, self.spec)
                if final_decision == ReviewDecision.PASS:
                    report = report.model_copy(
                        update={
                            "decision": ReviewDecision.PASS,
                            "score": best.quality_score,
                            "quality_status": QualityStatus.PASSED.value,
                            "selected_score": best.quality_score,
                            "best_attempt_index": best.attempt_index,
                            "next_action": "commit_ready",
                        }
                    )
                    self.host.emit_quality(
                        f"修订轮次结束，历史最佳 {best.quality_score:.1f} 分已通过",
                        review_attempt=review_attempt,
                        revision_count=revision_count,
                        report=report,
                        next_action="commit_ready",
                    )
                    return QualityLoopResult(
                        content=best.content,
                        plan=current_plan,
                        report=report,
                        passed=True,
                        revision_count=revision_count,
                        review_attempts=review_attempt,
                        replanned=replanned,
                        length_repair_count=length_repair_count,
                        score_trace=score_trace,
                        best_attempt_index=best.attempt_index,
                        selected_score=best.quality_score,
                    )
                report = report.model_copy(
                    update={
                        "next_action": "failed",
                        "decision": ReviewDecision.REVISE,
                        "score": best.quality_score,
                        "quality_status": QualityStatus.QUALITY_NEEDS_ATTENTION.value,
                        "selected_score": best.quality_score,
                        "best_attempt_index": best.attempt_index,
                    }
                )
                self.host.emit_quality(
                    (
                        f"已自动修订 {revision_count} 次仍未超过 {self.spec.pass_score_exclusive}，"
                        f"保留最佳 {best.quality_score:.1f} 分（第 {best.attempt_index} 版）"
                    ),
                    review_attempt=review_attempt,
                    revision_count=revision_count,
                    report=report,
                    next_action="failed",
                )
                return QualityLoopResult(
                    content=best.content,
                    plan=current_plan,
                    report=report,
                    passed=False,
                    revision_count=revision_count,
                    review_attempts=review_attempt,
                    replanned=replanned,
                    length_repair_count=length_repair_count,
                    score_trace=score_trace,
                    best_attempt_index=best.attempt_index,
                    selected_score=best.quality_score,
                )

            current_hash = content_hash(current)
            same_content = bool(previous_hash) and current_hash == previous_hash
            stagnant = (
                bool(previous_fingerprint)
                and fingerprint == previous_fingerprint
                and (candidate.quality_score - previous_attempt_score) < 1
            )
            action = resolve_recovery_action(
                report,
                plan=current_plan,
                chapter_number=current_plan.number,
                replanned=replanned,
                same_content=same_content,
                stagnant=stagnant,
            )
            if action == RecoveryAction.STOP:
                final_decision = decide_quality(best.quality_score, self.spec)
                passed = final_decision == ReviewDecision.PASS
                report = report.model_copy(
                    update={
                        "next_action": "commit_ready" if passed else "failed",
                        "decision": final_decision,
                        "score": best.quality_score,
                        "quality_status": (
                            QualityStatus.PASSED.value
                            if passed
                            else QualityStatus.QUALITY_NEEDS_ATTENTION.value
                        ),
                        "selected_score": best.quality_score,
                        "best_attempt_index": best.attempt_index,
                    }
                )
                self.host.emit_quality(
                    "未检测到有效进展，停止自动修订并保留历史最佳稿",
                    review_attempt=review_attempt,
                    revision_count=revision_count,
                    report=report,
                    next_action=report.next_action,
                )
                return QualityLoopResult(
                    content=best.content,
                    plan=current_plan,
                    report=report,
                    passed=passed,
                    revision_count=revision_count,
                    review_attempts=review_attempt,
                    replanned=replanned,
                    length_repair_count=length_repair_count,
                    score_trace=score_trace,
                    best_attempt_index=best.attempt_index,
                    selected_score=best.quality_score,
                )

            previous_hash = current_hash
            previous_fingerprint = fingerprint
            previous_attempt_score = candidate.quality_score
            blocking = report.blocking_issue_count + report.major_issue_count
            lowest = report.lowest_component or "未知"
            # Always revise from the current best content.
            revise_base = best.content
            if action == RecoveryAction.REPLAN:
                last_action = "replan"
                report = report.model_copy(update={"next_action": "replan"})
                self.host.emit_quality(
                    f"第 {review_attempt}/{max_reviews} 次质量检查未通过，最低项 {lowest}，"
                    f"正在根据 {blocking} 个优先问题重新规划",
                    review_attempt=review_attempt,
                    revision_count=revision_count,
                    report=report,
                    next_action="replan",
                )
                current_plan = self.host.replan_chapter()
                replanned = True
                current = self.host.write_chapter(current_plan)
            else:
                last_action = "revise"
                report = report.model_copy(update={"next_action": "revise"})
                self.host.emit_quality(
                    f"第 {review_attempt}/{max_reviews} 次质量检查未通过，当前最佳 "
                    f"{best.quality_score:.1f}，正在定向修订以超越该分",
                    review_attempt=review_attempt,
                    revision_count=revision_count,
                    report=report,
                    next_action="revise",
                )
                beat_contract = {
                    **quality_contract,
                    "beat_best_score": best.quality_score,
                    "keep_high_scoring_parts": True,
                }
                context = self.host.build_revision_context(
                    current_plan,
                    revise_base,
                    report,
                    revision_count + 1,
                    beat_contract,
                )
                current = self.host.revise_chapter(context)
            revision_count += 1
            if content_hash(current) == previous_hash:
                final_decision = decide_quality(best.quality_score, self.spec)
                passed = final_decision == ReviewDecision.PASS
                report = report.model_copy(
                    update={
                        "next_action": "commit_ready" if passed else "failed",
                        "decision": final_decision,
                        "score": best.quality_score,
                        "quality_status": (
                            QualityStatus.PASSED.value
                            if passed
                            else QualityStatus.QUALITY_NEEDS_ATTENTION.value
                        ),
                        "selected_score": best.quality_score,
                        "best_attempt_index": best.attempt_index,
                    }
                )
                self.host.emit_quality(
                    "修订后正文没有变化，停止无效循环并保留历史最佳稿",
                    review_attempt=review_attempt,
                    revision_count=revision_count,
                    report=report,
                    next_action=report.next_action,
                )
                return QualityLoopResult(
                    content=best.content,
                    plan=current_plan,
                    report=report,
                    passed=passed,
                    revision_count=revision_count,
                    review_attempts=review_attempt,
                    replanned=replanned,
                    length_repair_count=length_repair_count,
                    score_trace=score_trace,
                    best_attempt_index=best.attempt_index,
                    selected_score=best.quality_score,
                )

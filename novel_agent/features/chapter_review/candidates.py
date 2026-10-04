from __future__ import annotations

from dataclasses import dataclass, field

from novel_agent.features.chapter_review.quality_spec import (
    DEFAULT_QUALITY_CONTRACT,
    ChapterQualityContract,
    classify_length,
    count_quality_chars,
)
from novel_agent.models import IssueSeverity, ReviewIssue, ReviewReport


@dataclass(slots=True)
class ChapterCandidate:
    content: str
    quality_score: float
    report: ReviewReport | None = None
    dimension_scores: dict[str, float] = field(default_factory=dict)
    issues: list[ReviewIssue] = field(default_factory=list)
    length: int = 0
    source: str = "initial"
    attempt_index: int = 1
    plan_fingerprint: str = ""

    def __post_init__(self) -> None:
        if not self.length:
            self.length = count_quality_chars(self.content)


def _priority_issue_count(issues: list[ReviewIssue]) -> int:
    return sum(
        1
        for issue in issues
        if issue.severity in {IssueSeverity.MAJOR, IssueSeverity.BLOCKER}
    )


def _lowest_dimension(scores: dict[str, float]) -> float:
    if not scores:
        return 0.0
    return min(scores.values())


def choose_best(
    current_best: ChapterCandidate,
    new_candidate: ChapterCandidate,
    *,
    target_chars: int,
    contract: ChapterQualityContract = DEFAULT_QUALITY_CONTRACT,
) -> ChapterCandidate:
    """best_quality_score 只能不变或上升；同分用次级指标，仍相同则保留旧稿。"""
    if new_candidate.quality_score > current_best.quality_score:
        return new_candidate
    if new_candidate.quality_score < current_best.quality_score:
        return current_best

    best_len = classify_length(current_best.length, target_chars, contract)
    new_len = classify_length(new_candidate.length, target_chars, contract)
    if best_len != "ok" and new_len == "ok":
        return new_candidate
    if best_len == "ok" and new_len != "ok":
        return current_best

    best_pri = _priority_issue_count(current_best.issues)
    new_pri = _priority_issue_count(new_candidate.issues)
    if new_pri < best_pri:
        return new_candidate
    if new_pri > best_pri:
        return current_best

    if _lowest_dimension(new_candidate.dimension_scores) > _lowest_dimension(
        current_best.dimension_scores
    ):
        return new_candidate

    # Prefer smaller edit distance proxy: closer length to best when both ok.
    return current_best

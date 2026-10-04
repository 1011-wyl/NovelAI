from __future__ import annotations

from enum import StrEnum

from novel_agent.features.chapter_review.quality_spec import (
    DEFAULT_QUALITY_CONTRACT,
    ChapterQualityContract,
)
from novel_agent.models import ReviewDecision


class QualityStatus(StrEnum):
    GENERATION_FAILED = "GENERATION_FAILED"
    LENGTH_REPAIRING = "LENGTH_REPAIRING"
    LENGTH_NEEDS_ATTENTION = "LENGTH_NEEDS_ATTENTION"
    QUALITY_REVIEWING = "QUALITY_REVIEWING"
    QUALITY_REVISING = "QUALITY_REVISING"
    PASSED = "PASSED"
    QUALITY_NEEDS_ATTENTION = "QUALITY_NEEDS_ATTENTION"


def decide_quality(
    score: float,
    contract: ChapterQualityContract = DEFAULT_QUALITY_CONTRACT,
) -> ReviewDecision:
    """唯一质量判定：仅比较原始 quality_score 与严格大于通过线。"""
    if score > contract.pass_score_exclusive:
        return ReviewDecision.PASS
    return ReviewDecision.REVISE



"""Shared chapter quality-gate, quality contract, and bounded auto-revision."""

from novel_agent.features.chapter_review.decision import decide_quality
from novel_agent.features.chapter_review.quality_gate import (
    ChapterQualityGate,
    merge_review_reports,
)
from novel_agent.features.chapter_review.quality_spec import (
    DEFAULT_QUALITY_CONTRACT,
    READABILITY_DIMENSIONS,
    WRITE_TEMPERATURE,
    ChapterQualityContract,
    build_reviewer_quality_contract,
    build_writer_quality_contract,
)
from novel_agent.features.chapter_review.recovery import ChapterQualityRecovery
from novel_agent.features.chapter_review.revision_context import ChapterRevisionContext

__all__ = [
    "DEFAULT_QUALITY_CONTRACT",
    "READABILITY_DIMENSIONS",
    "WRITE_TEMPERATURE",
    "ChapterQualityContract",
    "ChapterQualityGate",
    "ChapterQualityRecovery",
    "ChapterRevisionContext",
    "build_reviewer_quality_contract",
    "build_writer_quality_contract",
    "decide_quality",
    "merge_review_reports",
]

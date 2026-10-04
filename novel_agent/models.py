from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


class ChapterStatus(StrEnum):
    PLANNED = "PLANNED"
    RESEARCHING = "RESEARCHING"
    WRITING = "WRITING"
    REVIEWING = "REVIEWING"
    REVISING = "REVISING"
    READY = "READY"
    SCHEDULED = "SCHEDULED"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"


class RunStatus(StrEnum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    HUMAN_REQUIRED = "HUMAN_REQUIRED"


class IssueSeverity(StrEnum):
    MINOR = "MINOR"
    MAJOR = "MAJOR"
    BLOCKER = "BLOCKER"


class ReviewDecision(StrEnum):
    PASS = "PASS"
    REVISE = "REVISE"
    HUMAN_REQUIRED = "HUMAN_REQUIRED"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


# Compatibility re-exports — migration-period Facade.
# Canonical definitions live under features/projects and features/story_design.
# Do not add new project/story-design fields here; extend the feature modules.
from novel_agent.features.projects.models import ProjectRecord, ProjectStatus
from novel_agent.features.story_design.models import (
    BriefRegenerateRequest,
    CharacterProfile,
    CreativeBrief,
    NovelCreateRequest,
    OpeningChapterAnchor,
)

#角色记忆更新
class CharacterMemoryUpdate(StrictModel):
    name: str = Field(min_length=1, max_length=20)
    role: str = Field(default="supporting", max_length=30)
    importance: Literal["core", "major"] = "major"
    profile: str = Field(default="", max_length=1000)
    immutable_facts: list[str] = Field(default_factory=list, max_length=12)
    current_goal: str = Field(default="", max_length=500)
    last_result: str = Field(default="", max_length=500)
    location: str = Field(default="", max_length=200)
    knowledge_gained: list[str] = Field(default_factory=list, max_length=12)
    relationship_changes: dict[str, str] = Field(default_factory=dict)

    @field_validator("name", "role", "profile", "current_goal", "last_result", "location", mode="before")
    @classmethod
    def strip_memory_text(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value


class CharacterMemoryBatch(StrictModel):
    characters: list[CharacterMemoryUpdate] = Field(default_factory=list, max_length=30)


class SceneBeat(StrictModel):
    sequence: int = Field(ge=1)
    scene: str = Field(min_length=1, max_length=1000)
    purpose: str = Field(min_length=1, max_length=300)
    emotional_shift: str = Field(min_length=1, max_length=300)
    intensity: Literal["dense", "normal", "sparse"] = "normal"
    target_chars: int = Field(ge=40, le=3000)

#章节规划
class ChapterPlan(StrictModel):
    number: int
    title: str
    objective: str
    conflict: str
    turning_point: str
    hook: str
    scenes: list[str]
    research_questions: list[str] = Field(default_factory=list)
    character_updates: list[CharacterMemoryUpdate] = Field(default_factory=list, max_length=20)
    story_stage: str = ""
    plot_unit: str = ""
    chapter_position: str = "推进"
    target_emotion: str = ""
    reader_payoff: str = ""
    new_expectation: str = ""
    protagonist_goal: str = ""
    critical_choice: str = ""
    opening_hook: str = ""
    forbidden_releases: list[str] = Field(default_factory=list, max_length=12)
    plotline_progress: dict[str, str] = Field(default_factory=dict)
    relationship_changes: dict[str, str] = Field(default_factory=dict)
    information_gap: list[str] = Field(default_factory=list, max_length=12)
    scene_beats: list[SceneBeat] = Field(default_factory=list, max_length=20)


class ChapterPlanBatch(StrictModel):
    """Exactly three materially different plans for the same chapter."""

    candidates: list[ChapterPlan] = Field(min_length=3, max_length=3)


class PlanCandidateEvaluation(StrictModel):
    index: int = Field(ge=0, le=2)
    causality: float = Field(ge=0, le=100)
    conflict_pressure: float = Field(ge=0, le=100)
    character_choice: float = Field(ge=0, le=100)
    novelty: float = Field(ge=0, le=100)
    continuity: float = Field(ge=0, le=100)
    payoff: float = Field(ge=0, le=100)
    weaknesses: list[str] = Field(default_factory=list, max_length=6)


class ChapterPlanSelection(StrictModel):
    selected_index: int = Field(ge=0, le=2)
    rationale: str = Field(min_length=1, max_length=1200)
    evaluations: list[PlanCandidateEvaluation] = Field(min_length=3, max_length=3)


class ProseFinding(StrictModel):
    code: str
    severity: IssueSeverity
    message: str
    suggestion: str
    evidence: str = ""


class ProseAuditReport(StrictModel):
    level: Literal["clean", "light", "medium", "heavy"] = "clean"
    score: float = Field(default=100, ge=0, le=100)
    findings: list[ProseFinding] = Field(default_factory=list, max_length=100)
    metrics: dict[str, float] = Field(default_factory=dict)


class ReviewIssue(StrictModel):
    category: str
    severity: IssueSeverity
    message: str
    suggestion: str
    evidence: list[str] = Field(default_factory=list, max_length=12)

#审核报告
class ReviewReport(StrictModel):
    decision: ReviewDecision
    score: float = Field(ge=0, le=100)
    issues: list[ReviewIssue] = Field(default_factory=list)
    checks: dict[str, float] = Field(default_factory=dict)
    blocking_issue_count: int = 0
    major_issue_count: int = 0
    minor_issue_count: int = 0
    lowest_component: str | None = None
    review_attempt: int = 0
    max_review_attempts: int = 0
    revision_count: int = 0
    length_repair_count: int = 0
    next_action: str = ""
    accepted_with_warnings: bool = False
    score_trace: list[float] = Field(default_factory=list)
    issue_fingerprint: str = ""
    preflight_only: bool = False
    quality_status: str = ""
    pass_score_exclusive: float = 60.0
    selected_score: float | None = None
    best_attempt_index: int = 0
    actual_length: int = 0
    target_length: int = 0
    accepted_length_min: int = 0
    accepted_length_max: int = 0


class ReadabilityContext(StrictModel):
    project_id: str
    chapter_number: int
    creative_request: dict[str, Any]
    creative_brief: dict[str, Any]
    chapter_plan: dict[str, Any]
    current_draft: str
    previous_chapter_excerpt: str = ""
    quality_contract: dict[str, Any] = Field(default_factory=dict)

#连续上下文
class ContinuityContext(StrictModel):
    """Structured runtime input for the vendored Story Skills audit."""

    skill_name: str
    skill_source: str
    project_id: str
    chapter_number: int
    creative_request: dict[str, Any]
    creative_brief: dict[str, Any]
    chapter_plan: dict[str, Any]
    current_draft: str
    recent_chapters: list[dict[str, Any]] = Field(default_factory=list, max_length=8)
    characters: list[dict[str, Any]] = Field(default_factory=list, max_length=40)
    world_facts: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
    timeline: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
    foreshadows: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
    deterministic_findings: list[ReviewIssue] = Field(default_factory=list, max_length=100)


class CharacterRecord(StrictModel):
    id: str
    project_id: str
    name: str
    role: str
    immutable_facts: list[str]
    current_state: dict[str, Any]
    version: int = 1


class WorldFactRecord(StrictModel):
    id: str
    project_id: str
    category: str
    statement: str
    evidence_chapter: int | None = None
    version: int = 1
    locked: bool = False


class ChapterRecord(StrictModel):
    id: str
    project_id: str
    number: int
    title: str
    status: ChapterStatus
    plan: ChapterPlan | None = None
    content: str | None = None
    summary: str | None = None
    version: int = 0
    locked: bool = False
    created_at: str
    updated_at: str


class RunEvent(StrictModel):
    id: int | None = None
    run_id: str
    project_id: str
    chapter_id: str | None = None
    node: str
    message: str
    progress: int = Field(ge=0, le=100)
    level: str = "INFO"
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=utc_now)


class WorkflowResult(StrictModel):
    run_id: str
    chapter: ChapterRecord
    review: ReviewReport
    events: list[RunEvent]


# --- Reading / revision workspace (SCHEMA 5) ---


class AssistantMode(StrEnum):
    ADVISOR = "advisor"
    COAUTHOR = "coauthor"
    EDITOR = "editor"


class AssistantChangeStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REVERTED = "REVERTED"


class ChapterEditDraft(StrictModel):
    chapter_id: str
    project_id: str
    base_version: int
    title: str
    content: str
    source: Literal["manual", "ai", "mixed", "rollback"]
    applied_change_ids: list[str] = Field(default_factory=list)
    content_hash: str
    created_at: str
    updated_at: str


class ChapterDraftUpdate(StrictModel):
    base_version: int
    title: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=100_000)
    expected_draft_hash: str | None = None


class ChapterSelection(StrictModel):
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    text: str = Field(min_length=1, max_length=8_000)
    chapter_version: int = Field(ge=1)
    draft_hash: str

    @model_validator(mode="after")
    def end_after_start(self) -> ChapterSelection:
        if self.end <= self.start:
            raise ValueError("selection.end must be greater than selection.start")
        return self


class AssistantMessageCreate(StrictModel):
    content: str = Field(min_length=1, max_length=8_000)
    mode: AssistantMode
    selection: ChapterSelection | None = None
    quick_action: Literal["polish", "shorten", "expand", "visualize", "dialogue"] | None = None


class AssistantEditProposal(StrictModel):
    operation: Literal["edit_chapter", "rewrite_chapter"]
    title: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=100_000)
    explanation: str = Field(default="", max_length=2_000)


class AssistantGatewayResponse(StrictModel):
    message: str
    proposal: AssistantEditProposal | None = None


class WorldFactUpdate(StrictModel):
    category: str = Field(min_length=1, max_length=80)
    statement: str = Field(min_length=1, max_length=1_000)


class ChapterRevisionAnalysis(StrictModel):
    summary: str = Field(min_length=1, max_length=2_000)
    timeline_event: str = Field(min_length=1, max_length=1_000)
    character_updates: list[CharacterMemoryUpdate] = Field(default_factory=list)
    world_facts: list[WorldFactUpdate] = Field(default_factory=list)
    introduced_foreshadows: list[str] = Field(default_factory=list)
    resolved_foreshadows: list[str] = Field(default_factory=list)


class AssistantSession(StrictModel):
    id: str
    project_id: str
    chapter_id: str
    title: str
    created_at: str
    updated_at: str
    deleted_at: str | None = None


class AssistantMessage(StrictModel):
    id: str
    session_id: str
    sequence: int
    role: Literal["user", "assistant"]
    mode: AssistantMode
    content: str
    selection: ChapterSelection | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class AssistantChangeSet(StrictModel):
    id: str
    session_id: str
    message_id: str
    chapter_id: str
    operation: Literal["edit_chapter", "rewrite_chapter"]
    base_version: int
    base_draft_hash: str
    before_title: str
    before_content: str
    after_title: str
    after_content: str
    diff_json: dict[str, Any] = Field(default_factory=dict)
    explanation: str = ""
    status: AssistantChangeStatus
    created_at: str
    decided_at: str | None = None
    reverted_at: str | None = None


class ChapterRevisionCommitRequest(StrictModel):
    base_version: int
    expected_draft_hash: str = Field(min_length=1)


class ChapterAcceptWithWarningsRequest(StrictModel):
    confirm: bool
    base_version: int
    expected_draft_hash: str = Field(min_length=1)


class AssistantRollbackRequest(StrictModel):
    to_message_id: str = Field(min_length=1)
    expected_draft_hash: str = Field(min_length=1)


class ChapterRevisionResult(StrictModel):
    chapter: ChapterRecord
    reset_chapters: list[int] = Field(default_factory=list)
    memory_changes: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    semantic_index_status: str = "unchanged"

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from novel_agent.features.chapter_planning.context import (
    build_planning_context,
    filter_semantic_matches,
)
from novel_agent.features.chapter_planning.continuity_guard import (
    strip_future_fields_from_brief,
)
from novel_agent.features.chapter_planning.errors import ReworkModeNotAllowedError
from novel_agent.features.chapter_planning.models import ReworkMode
from novel_agent.features.chapter_planning.rework_policy import resolve_requested_mode
from novel_agent.features.chapter_planning.validation import (
    assert_write_gate,
    validate_plan_against_anchor,
)
from novel_agent.features.chapter_review.quality_gate import (
    ChapterQualityGate,
    merge_review_reports,
)
from novel_agent.features.chapter_review.quality_spec import (
    MAX_REVISION_ATTEMPTS_MAX,
    MAX_REVISION_ATTEMPTS_MIN,
    build_reviewer_quality_contract,
    build_writer_quality_contract,
    count_quality_chars,
    length_bounds,
)
from novel_agent.features.chapter_review.recovery import ChapterQualityRecovery
from novel_agent.features.chapter_review.revision_context import ChapterRevisionContext
from novel_agent.integrations.embedding.disabled import DisabledEmbeddingGateway
from novel_agent.ports import EmbeddingGateway, LLMGateway, SearchAdapter
from novel_agent.memory_manager import MemoryManager
from novel_agent.models import (
    ChapterPlan,
    ChapterRecord,
    ChapterStatus,
    CharacterMemoryUpdate,
    IssueSeverity,
    ProjectRecord,
    ProjectStatus,
    ReadabilityContext,
    ReviewDecision,
    ReviewIssue,
    ReviewReport,
    RunEvent,
    RunStatus,
    WorkflowResult,
    new_id,
    utc_now,
)
from novel_agent.repository import SQLiteRepository
from novel_agent.story_skills import StorySkillsRuntime
from novel_agent.telemetry import llm_call_scope
from novel_agent.text_metrics import count_content_chars
from novel_agent.writing_skills import OhStoryWritingRuntime


class WorkflowBlocked(RuntimeError):
    def __init__(self, message: str, *, code: str = "WORKFLOW_BLOCKED", details: Any = None):
        super().__init__(message)
        self.code = code
        self.details = details


@dataclass(slots=True)
class ChapterWorkflow:
    repository: SQLiteRepository
    gateway: LLMGateway
    search: SearchAdapter
    max_revision_attempts: int = 2
    embedding: EmbeddingGateway = field(default_factory=DisabledEmbeddingGateway)
    semantic_retrieval_limit: int = 6
    story_skills: StorySkillsRuntime = field(default_factory=StorySkillsRuntime.disabled)
    writing_skills: OhStoryWritingRuntime = field(default_factory=OhStoryWritingRuntime.disabled)
    memory_manager: MemoryManager = field(default_factory=MemoryManager)
    _events: list[RunEvent] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        if not MAX_REVISION_ATTEMPTS_MIN <= self.max_revision_attempts <= MAX_REVISION_ATTEMPTS_MAX:
            raise ValueError(
                "MAX_REVISION_ATTEMPTS 必须是 0 到 5 的整数，0 表示审核首稿后不自动修订"
            )

    def run(self, project_id: str) -> WorkflowResult:
        self._events = []
        project = self.repository.get_project(project_id)
        self._assert_runnable(project)
        number = project.current_chapter + 1
        existing = self.repository.get_chapter_by_number(project_id, number)
        if existing and existing.status == ChapterStatus.READY:
            report = ReviewReport(decision=ReviewDecision.PASS, score=100, checks={"idempotent": 100})
            return WorkflowResult(run_id="already_ready", chapter=existing, review=report, events=[])

        chapter = existing or ChapterRecord(
            id=new_id("chapter"),
            project_id=project_id,
            number=number,
            title=f"第{number}章 待规划",
            status=ChapterStatus.PLANNED,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        if existing is None:
            chapter = self.repository.create_chapter(chapter)
        run_id = new_id("run")
        self.repository.create_run(run_id, project_id, chapter.id)

        with llm_call_scope(
            project_id=project_id,
            chapter_id=chapter.id,
            run_id=run_id,
            category="agent",
        ):
            return self._run_scoped(
                project, project_id, chapter, run_id, number, existing
            )

    def _run_scoped(
        self,
        project: ProjectRecord,
        project_id: str,
        chapter: ChapterRecord,
        run_id: str,
        number: int,
        existing: ChapterRecord | None,
    ) -> WorkflowResult:
        try:
            self._emit(run_id, project_id, chapter.id, "LoadContext", "加载最近章节与正式记忆", 5)
            chapters = self.repository.list_chapters(project_id)
            planning = build_planning_context(
                project_id=project_id,
                chapter_number=number,
                brief=project.brief,
                chapters=chapters,
                timeline_source=self.repository,
            )
            summaries = list(planning.recent_summaries)
            previous_chapter_excerpt = planning.previous_chapter_excerpt
            timeline = planning.timeline
            character_roster = self.repository.list_characters(project_id)
            open_threads = list(planning.open_threads)
            semantic_research_notes: list[str] = []
            if self.embedding.enabled:
                self._index_pending(run_id, project_id, chapter.id, progress=8)
                try:
                    query = "；".join(
                        [project.brief.main_conflict, *summaries[-2:], *open_threads[-3:]]
                    )
                    vector = self.embedding.embed([query])[0]
                    matches = filter_semantic_matches(
                        self.repository.semantic_search(
                            project_id, vector, self.semantic_retrieval_limit
                        ),
                        chapter_number=number,
                        chapters=chapters,
                    )
                    for match in matches:
                        recalled = str(match["content"])[:1200]
                        if match["source_type"] == "chapter_summary":
                            if number == 1:
                                continue
                            if recalled not in summaries:
                                summaries.append(recalled)
                        else:
                            metadata = match.get("metadata", {})
                            semantic_research_notes.append(
                                self._research_note(
                                    str(metadata.get("title") or "历史研究资料"),
                                    str(metadata.get("url") or ""),
                                    recalled,
                                    float(match["score"]),
                                    True,
                                )
                            )
                    self._emit(
                        run_id,
                        project_id,
                        chapter.id,
                        "SemanticRecall",
                        f"从章节摘要与研究资料中召回 {len(matches)} 条相关记忆",
                        10,
                        payload={"matches": len(matches)},
                    )
                except Exception as exc:
                    self._emit(
                        run_id,
                        project_id,
                        chapter.id,
                        "SemanticRecall",
                        f"语义检索暂不可用，已降级为最近章节上下文：{type(exc).__name__}",
                        10,
                        level="WARN",
                    )

            writing_guidance = self.writing_skills.chapter_guidance(
                project.request.genre,
                project.request.audience_channel,
            )
            if writing_guidance:
                self._emit(
                    run_id,
                    project_id,
                    chapter.id,
                    "GenreProseCard",
                    f"加载题材正文提示卡：{writing_guidance['genre_card_name']}",
                    13,
                    payload={
                        "skill": writing_guidance["skill"],
                        "source": writing_guidance["source"],
                        "genre_card": writing_guidance["genre_card_name"],
                        "confidence": writing_guidance["genre_card_confidence"],
                    },
                )
            rework_feedback_raw = self.repository.get_setting(
                f"rework_feedback:{chapter.id}"
            )
            rework_feedback = (
                str(rework_feedback_raw).strip()
                if rework_feedback_raw
                else ""
            )
            rework_mode_raw = self.repository.get_setting(f"rework_mode:{chapter.id}")
            latest_report: ReviewReport | None = None
            with self.repository.connection() as conn:
                report_row = conn.execute(
                    """SELECT report_json FROM review_reports
                    WHERE chapter_id=? ORDER BY created_at DESC LIMIT 1""",
                    (chapter.id,),
                ).fetchone()
            if report_row and report_row["report_json"]:
                latest_report = ReviewReport.model_validate_json(report_row["report_json"])
            try:
                rework_mode = resolve_requested_mode(
                    str(rework_mode_raw or "auto"),
                    report=latest_report,
                    chapter_number=number,
                    plan=existing.plan if existing else None,
                )
            except ReworkModeNotAllowedError as exc:
                raise WorkflowBlocked(str(exc), code=exc.code) from exc
            if rework_feedback:
                writing_guidance = writing_guidance or {}
                writing_guidance["rework_feedback"] = rework_feedback
                self._emit(
                    run_id, project_id, chapter.id,
                    "ReworkFeedback",
                    f"本章打回重做，修改意见：{rework_feedback[:80]}",
                    14,
                )
            research_sources = self.repository.list_research_sources(project_id)
            chapter_id_to_number = {ch.id: ch.number for ch in chapters}
            for rs in research_sources:
                ch_id = rs.get("chapter_id")
                rs["_chapter_number"] = chapter_id_to_number.get(ch_id)
            compact_ctx = self.memory_manager.build_context(
                characters=character_roster,
                world_facts=self.repository.list_world_facts(project_id),
                timeline=timeline,
                research_sources=research_sources,
                current_chapter=number,
            )
            if (
                existing
                and existing.plan is not None
                and rework_mode == ReworkMode.REUSE_PLAN
            ):
                plan = existing.plan
                self._emit(
                    run_id,
                    project_id,
                    chapter.id,
                    "PlanReuse",
                    f"沿用上次细纲（{rework_mode.value}），按审稿意见重新写作",
                    20,
                    payload={"mode": rework_mode.value},
                )
            else:
                self._emit(
                    run_id,
                    project_id,
                    chapter.id,
                    "PlanRegenerate" if rework_feedback or existing else "Plan",
                    "生成一份包含冲突、选择、代价与情节点预算的章节细纲",
                    15,
                    payload={"mode": rework_mode.value},
                )
                plan = self.gateway.plan_chapter(
                    project.request,
                    project.brief,
                    number,
                    summaries,
                    open_threads,
                    character_roster,
                    writing_guidance,
                    compact_characters=compact_ctx.get("compact_characters"),
                    compact_world_facts=compact_ctx.get("compact_world_facts"),
                    compact_timeline=compact_ctx.get("compact_timeline"),
                    previous_chapter_excerpt=previous_chapter_excerpt,
                    opening_anchor=planning.opening_anchor,
                )
                plan = self.writing_skills.normalize_plan(
                    plan,
                    total_chapters=project.brief.total_chapters,
                    target_chars=project.request.chapter_target_chars,
                )
            plan = self._enforce_opening_anchor(
                plan,
                project=project,
                chapter=chapter,
                run_id=run_id,
                number=number,
                planning=planning,
                character_roster=character_roster,
            )
            chapter = self.repository.persist_chapter_plan_and_consume_rework(
                chapter.id,
                status=ChapterStatus.PLANNED,
                plan=plan,
                title=plan.title,
            )
            assert_write_gate(
                plan,
                chapter_number=number,
                context=planning,
                character_archives=character_roster,
            )

            research_notes: list[str] = [
                *compact_ctx.get("compact_research", []),
                *semantic_research_notes,
            ]
            if plan.research_questions:
                chapter = self.repository.update_chapter(
                    chapter.id, status=ChapterStatus.RESEARCHING
                )
                if self.search.enabled:
                    self._emit(run_id, project_id, chapter.id, "Research", "执行外部知识调研", 28)
                    try:
                        sources = self.search.research(plan.research_questions)
                        saved_sources = self.repository.save_research_sources(
                            project_id, chapter.id, sources
                        )
                        research_notes.extend(
                            self._research_note(
                                str(source.get("title") or "网页来源"),
                                str(source.get("url") or ""),
                                str(source.get("excerpt") or source.get("fact") or ""),
                                float(source.get("reliability", 0.0)),
                                bool(source.get("verified")),
                            )
                            for source in saved_sources
                            if source.get("excerpt") or source.get("fact")
                        )
                        self._emit(
                            run_id,
                            project_id,
                            chapter.id,
                            "SourceVerification",
                            f"保存 {len(saved_sources)} 条网页来源并完成可信度与交叉来源标记",
                            34,
                            payload={"sources": len(saved_sources)},
                        )
                        if self.embedding.enabled:
                            self._index_pending(run_id, project_id, chapter.id, progress=36)
                    except Exception as exc:
                        self._emit(
                            run_id,
                            project_id,
                            chapter.id,
                            "ResearchFallback",
                            f"联网调研失败，改用保守写法：{type(exc).__name__}",
                            34,
                            level="WARN",
                        )
                else:
                    self._emit(
                        run_id,
                        project_id,
                        chapter.id,
                        "ResearchDecision",
                        "检测到研究需求，但搜索 API 未启用；使用保守写法并标记边界",
                        28,
                        level="WARN",
                        payload={"questions": plan.research_questions},
                    )
            else:
                self._emit(run_id, project_id, chapter.id, "ResearchDecision", "本章无需外部调研", 28)

            chapter = self.repository.update_chapter(chapter.id, status=ChapterStatus.WRITING)
            self._emit(run_id, project_id, chapter.id, "Writer", "按情绪细纲与题材提示卡生成章节草稿", 42)
            if not character_roster:
                raise WorkflowBlocked("项目缺少人物档案，请先确认创作方案或重建人物数据")
            protagonist = next(
                (item for item in character_roster if item.role == "protagonist"),
                character_roster[0],
            )
            assert_write_gate(
                plan,
                chapter_number=number,
                context=planning,
                character_archives=character_roster,
            )
            if rework_feedback:
                research_notes = [
                    f"[打回重做修改意见] {rework_feedback}",
                    *research_notes,
                ]
            quality_contract = build_writer_quality_contract(
                chapter_number=number,
                target_chars=project.request.chapter_target_chars,
                opening_anchor=planning.opening_anchor,
                previous_chapter_excerpt=previous_chapter_excerpt,
                exclude=list(project.request.exclude),
            )
            content = self.gateway.write_chapter(
                project.request,
                project.brief,
                plan,
                protagonist.name,
                research_notes,
                character_roster,
                writing_guidance.get("genre_prose_card", ""),
                compact_characters=compact_ctx.get("compact_characters"),
                previous_chapter_excerpt=previous_chapter_excerpt,
                opening_anchor=planning.opening_anchor,
                quality_contract=quality_contract,
            )
            self.repository.save_draft_version(
                chapter.id,
                content,
                {"gateway": self.gateway.name, "plan": plan.model_dump(mode="json")},
            )

            if self.writing_skills.enabled:
                before_audit = self.writing_skills.audit_prose(content)
                polished = self.gateway.deslop_chapter(
                    content,
                    plan,
                    writing_guidance.get("genre_prose_card", ""),
                    self.writing_skills.deslop_guidance(),
                )
                after_audit = (
                    self.writing_skills.audit_prose(polished)
                    if polished.strip()
                    else before_audit
                )
                before_serious = sum(
                    item.severity in {IssueSeverity.BLOCKER, IssueSeverity.MAJOR}
                    for item in before_audit.findings
                )
                after_serious = sum(
                    item.severity in {IssueSeverity.BLOCKER, IssueSeverity.MAJOR}
                    for item in after_audit.findings
                )
                accepted_polish = bool(
                    polished.strip()
                    and after_audit.score >= before_audit.score
                    and after_serious <= before_serious
                    and (
                        length_bounds(project.request.chapter_target_chars)["accepted_length_min"]
                        <= count_quality_chars(polished)
                        <= length_bounds(project.request.chapter_target_chars)["accepted_length_max"]
                    )
                )
                if accepted_polish:
                    content = polished
                    self.repository.save_draft_version(
                        chapter.id,
                        content,
                        {
                            "stage": "story-deslop",
                            "skill_source": self.writing_skills.source_commit,
                            "before": before_audit.model_dump(mode="json"),
                            "after": after_audit.model_dump(mode="json"),
                        },
                    )
                effective_audit = after_audit if accepted_polish else before_audit
                self._emit(
                    run_id,
                    project_id,
                    chapter.id,
                    "ProsePolish",
                    (
                        ("story-deslop 润色已采用：" if accepted_polish else "story-deslop 未改善，保留原稿：")
                        + f"{before_audit.level} → {after_audit.level}，"
                        f"当前剩余 {len(effective_audit.findings)} 项"
                    ),
                    52,
                    level="WARN" if any(
                        item.severity in {IssueSeverity.BLOCKER, IssueSeverity.MAJOR}
                        for item in effective_audit.findings
                    ) else "INFO",
                    payload={
                        "skill": "story-deslop",
                        "source": self.writing_skills.source_commit,
                        "before_score": before_audit.score,
                        "after_score": after_audit.score,
                        "accepted": accepted_polish,
                        "remaining_findings": len(effective_audit.findings),
                    },
                )

            chapter = self.repository.update_chapter(chapter.id, status=ChapterStatus.REVIEWING)
            reviewer_contract = build_reviewer_quality_contract(
                chapter_number=number,
                target_chars=project.request.chapter_target_chars,
                opening_anchor=planning.opening_anchor,
                previous_chapter_excerpt=previous_chapter_excerpt,
                exclude=list(project.request.exclude),
            )
            quality_contract = {**quality_contract, **reviewer_contract}

            class _RecoveryHost:
                def __init__(host_self) -> None:
                    host_self._plan = plan
                    host_self._research_notes = research_notes

                def persist_attempt(
                    host_self,
                    draft: str,
                    attempt_report: ReviewReport,
                    *,
                    review_attempt: int,
                    revision_count: int,
                    recovery_action: str,
                    preflight_only: bool,
                ) -> None:
                    self.repository.save_draft_version(
                        chapter.id,
                        draft,
                        {
                            "review_attempt": review_attempt,
                            "revision_count": revision_count,
                            "recovery_action": recovery_action,
                            "preflight_only": preflight_only,
                            "score": attempt_report.score,
                            "issue_fingerprint": attempt_report.issue_fingerprint,
                            "score_trace": attempt_report.score_trace,
                            "report": attempt_report.model_dump(mode="json"),
                        },
                    )
                    self.repository.save_review_report(chapter.id, run_id, attempt_report)

                def emit_quality(
                    host_self,
                    message: str,
                    *,
                    review_attempt: int,
                    revision_count: int,
                    report: ReviewReport,
                    next_action: str,
                ) -> None:
                    progress = min(84, 58 + max(0, review_attempt - 1) * 8)
                    if self.story_skills.enabled:
                        skill_issues = [
                            issue
                            for issue in report.issues
                            if issue.category.startswith("story")
                            or "continuity" in issue.category
                        ]
                        self._emit(
                            run_id,
                            project_id,
                            chapter.id,
                            "StorySkillsAudit",
                            (
                                "Story Skills 一致性审校完成："
                                f"{len(skill_issues)} 个问题，得分 {report.score:.0f}"
                            ),
                            progress,
                            level="WARN" if report.decision != ReviewDecision.PASS else "INFO",
                            payload={
                                "skill": "revision-continuity",
                                "source": self.story_skills.source_commit,
                                "decision": report.decision.value,
                                "score": report.score,
                            },
                        )
                    self._emit(
                        run_id,
                        project_id,
                        chapter.id,
                        "ParallelReview",
                        message,
                        progress,
                        level=(
                            "INFO"
                            if report.decision == ReviewDecision.PASS
                            else "WARN"
                        ),
                        payload={
                            "decision": report.decision.value,
                            "score": report.score,
                            "checks": report.checks,
                            "lowest_component": report.lowest_component,
                            "review_attempt": review_attempt,
                            "max_review_attempts": report.max_review_attempts,
                            "revision_count": revision_count,
                            "next_action": next_action,
                            "score_trace": report.score_trace,
                            "blocking_issue_count": report.blocking_issue_count,
                            "major_issue_count": report.major_issue_count,
                        },
                    )

                def write_chapter(host_self, next_plan: ChapterPlan) -> str:
                    self.repository.update_chapter(
                        chapter.id, status=ChapterStatus.WRITING, plan=next_plan, title=next_plan.title
                    )
                    self._emit(
                        run_id,
                        project_id,
                        chapter.id,
                        "Writer",
                        "按重新规划的细纲重写章节草稿",
                        70,
                    )
                    return self.gateway.write_chapter(
                        project.request,
                        project.brief,
                        next_plan,
                        protagonist.name,
                        host_self._research_notes,
                        character_roster,
                        writing_guidance.get("genre_prose_card", ""),
                        compact_characters=compact_ctx.get("compact_characters"),
                        previous_chapter_excerpt=previous_chapter_excerpt,
                        opening_anchor=planning.opening_anchor,
                        quality_contract=quality_contract,
                    )

                def revise_chapter(host_self, context: ChapterRevisionContext) -> str:
                    self.repository.update_chapter(chapter.id, status=ChapterStatus.REVISING)
                    self._emit(
                        run_id,
                        project_id,
                        chapter.id,
                        "Revision",
                        f"按审核问题自动修订（第 {context.revision_number} 次）",
                        72,
                        payload={
                            "revision_number": context.revision_number,
                            "issue_count": len(context.review.issues),
                        },
                    )
                    return self.gateway.revise_chapter(context)

                def replan_chapter(host_self) -> ChapterPlan:
                    self._emit(
                        run_id,
                        project_id,
                        chapter.id,
                        "PlanRegenerate",
                        "结构性问题触发同轮自动重新规划",
                        66,
                        level="WARN",
                    )
                    next_plan = self.gateway.plan_chapter(
                        project.request,
                        project.brief,
                        number,
                        summaries,
                        open_threads,
                        character_roster,
                        writing_guidance,
                        compact_characters=compact_ctx.get("compact_characters"),
                        compact_world_facts=compact_ctx.get("compact_world_facts"),
                        compact_timeline=compact_ctx.get("compact_timeline"),
                        previous_chapter_excerpt=previous_chapter_excerpt,
                        opening_anchor=planning.opening_anchor,
                    )
                    next_plan = self.writing_skills.normalize_plan(
                        next_plan,
                        total_chapters=project.brief.total_chapters,
                        target_chars=project.request.chapter_target_chars,
                    )
                    next_plan = self._enforce_opening_anchor(
                        next_plan,
                        project=project,
                        chapter=chapter,
                        run_id=run_id,
                        number=number,
                        planning=planning,
                        character_roster=character_roster,
                    )
                    self.repository.update_chapter(
                        chapter.id,
                        status=ChapterStatus.PLANNED,
                        plan=next_plan,
                        title=next_plan.title,
                    )
                    host_self._plan = next_plan
                    return next_plan

                def build_revision_context(
                    host_self,
                    current_plan: ChapterPlan,
                    draft: str,
                    attempt_report: ReviewReport,
                    revision_number: int,
                    contract: dict[str, Any],
                ) -> ChapterRevisionContext:
                    return ChapterRevisionContext(
                        project_id=project_id,
                        chapter_number=number,
                        target_chars=project.request.chapter_target_chars,
                        creative_request={
                            "audience_channel": project.request.audience_channel,
                            "genre": project.request.genre,
                            "experiences": project.request.experiences,
                            "elements": project.request.elements,
                            "protagonist_tags": project.request.protagonist_tags,
                            "romance": project.request.romance,
                            "idea": project.request.idea,
                            "must_have": project.request.must_have,
                            "nice_to_have": project.request.nice_to_have,
                            "exclude": project.request.exclude,
                            "chapter_target_chars": project.request.chapter_target_chars,
                        },
                        creative_brief={
                            "synopsis": project.brief.synopsis,
                            "style_guide": project.brief.style_guide,
                            "protagonist_name": project.brief.protagonist_name,
                            "main_conflict": project.brief.main_conflict,
                            "world_rules": project.brief.world_rules,
                        },
                        chapter_plan=current_plan.model_dump(mode="json"),
                        quality_contract=contract,
                        current_draft=draft,
                        previous_chapter_excerpt=previous_chapter_excerpt[-1800:],
                        opening_anchor=(
                            planning.opening_anchor.model_dump(mode="json")
                            if planning.opening_anchor
                            else None
                        ),
                        character_archives=list(
                            compact_ctx.get("compact_characters")
                            or [item.model_dump(mode="json") for item in character_roster]
                        ),
                        world_rules=list(project.brief.world_rules),
                        review=attempt_report,
                        revision_number=revision_number,
                    )

            loop = ChapterQualityRecovery(
                host=_RecoveryHost(),
                gate=ChapterQualityGate(self.gateway, self.story_skills, self.writing_skills),
                max_revision_attempts=self.max_revision_attempts,
            )
            loop_result = loop.run(
                repository=self.repository,
                project=project,
                plan=plan,
                content=content,
                protagonist_name=protagonist.name,
                previous_chapter_excerpt=previous_chapter_excerpt,
                has_research=bool(research_notes),
                characters=character_roster,
                opening_anchor=planning.opening_anchor,
                quality_contract=quality_contract,
            )
            content = loop_result.content
            plan = loop_result.plan
            report = loop_result.report

            if not loop_result.passed:
                chapter = self.repository.update_chapter(chapter.id, status=ChapterStatus.FAILED)
                feedback = "；".join(
                    issue.suggestion
                    for issue in report.issues
                    if issue.severity in {IssueSeverity.BLOCKER, IssueSeverity.MAJOR}
                )[:2000]
                if feedback:
                    self.repository.save_setting(f"rework_feedback:{chapter.id}", feedback)
                self.repository.update_run(
                    run_id,
                    RunStatus.FAILED.value,
                    {
                        "node": "QualityHold",
                        "report": report.model_dump(mode="json"),
                        "score_trace": loop_result.score_trace,
                        "revision_count": loop_result.revision_count,
                    },
                    "REVIEW_RETRY_EXHAUSTED",
                )
                if loop_result.selected_score is None:
                    hold_message = (
                        f"字数补写 {loop_result.length_repair_count} 次后仍未达标，"
                        "本轮未进入质量审核。"
                        "项目保持可用，可重新规划、沿用细纲重写或编辑后重新送审"
                    )
                else:
                    hold_message = (
                        f"已自动修订 {loop_result.revision_count} 次仍未通过；"
                        f"保留最佳 {loop_result.selected_score:.1f} 分稿。"
                        "项目保持可用，可重新规划、沿用细纲重写或编辑后重新送审"
                    )
                self._emit(
                    run_id,
                    project_id,
                    chapter.id,
                    "QualityHold",
                    hold_message,
                    85,
                    level="WARN",
                    payload={
                        "score_trace": loop_result.score_trace,
                        "revision_count": loop_result.revision_count,
                        "review_attempts": loop_result.review_attempts,
                    },
                )
                return WorkflowResult(
                    run_id=run_id,
                    chapter=chapter,
                    review=report,
                    events=self._events,
                )

            self._emit(run_id, project_id, chapter.id, "Summary", "生成章节摘要与记忆变更集", 88)
            summary = self._summary(plan, content)
            timeline_event = f"第{number}章：{plan.objective}；转折：{plan.turning_point}"
            extracted_updates: list[CharacterMemoryUpdate] = []
            try:
                memory_batch = self.gateway.extract_character_memories(
                    project.brief,
                    number,
                    content,
                    character_roster,
                )
                extracted_updates = memory_batch.characters
                self._emit(
                    run_id,
                    project_id,
                    chapter.id,
                    "CharacterArchive",
                    f"识别并更新 {len(extracted_updates)} 个人物档案",
                    92,
                    payload={"characters": [item.name for item in extracted_updates]},
                )
            except Exception as exc:
                self._emit(
                    run_id,
                    project_id,
                    chapter.id,
                    "CharacterArchive",
                    f"人物提取暂不可用，已使用章节计划中的人物变更：{type(exc).__name__}",
                    92,
                    level="WARN",
                )
            character_updates = self._merge_character_updates(
                [
                    *plan.character_updates,
                    *extracted_updates,
                    CharacterMemoryUpdate(
                        name=protagonist.name,
                        role="protagonist",
                        importance="core",
                        current_goal=plan.hook,
                        last_result=plan.objective,
                    ),
                ]
            )
            self._emit(run_id, project_id, chapter.id, "MemoryCommit", "原子提交正文与正式记忆", 94)
            chapter = self.repository.commit_ready_chapter(
                chapter.id,
                run_id,
                content,
                summary,
                report,
                timeline_event,
                character_updates,
            )
            if self.embedding.enabled:
                self._index_pending(run_id, project_id, chapter.id, progress=97)
            self.repository.update_run(
                run_id,
                RunStatus.COMPLETED.value,
                {"node": "ChapterReady", "chapter_id": chapter.id, "version": chapter.version},
            )
            self._emit(run_id, project_id, chapter.id, "ChapterReady", "章节审核通过并进入 READY 储备池", 100)
            return WorkflowResult(run_id=run_id, chapter=chapter, review=report, events=self._events)
        except WorkflowBlocked:
            raise
        except Exception as exc:
            self.repository.update_chapter(chapter.id, status=ChapterStatus.FAILED)
            self.repository.update_run(
                run_id,
                RunStatus.FAILED.value,
                {"node": self._events[-1].node if self._events else "unknown"},
                type(exc).__name__,
            )
            self._emit(
                run_id,
                project_id,
                chapter.id,
                "Failure",
                f"工作流失败：{type(exc).__name__}",
                100,
                level="ERROR",
            )
            raise

    @staticmethod
    def _readability_context(
        project: ProjectRecord,
        plan: ChapterPlan,
        content: str,
        previous_chapter_excerpt: str,
    ) -> ReadabilityContext:
        request = project.request
        brief = project.brief
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
            previous_chapter_excerpt=previous_chapter_excerpt[-800:],
        )

    def _enforce_opening_anchor(
        self,
        plan: ChapterPlan,
        *,
        project: ProjectRecord,
        chapter: ChapterRecord,
        run_id: str,
        number: int,
        planning: Any,
        character_roster: list[Any],
    ) -> ChapterPlan:
        if plan.number != number:
            plan = plan.model_copy(update={"number": number})
        issues = validate_plan_against_anchor(
            plan,
            chapter_number=number,
            context=planning,
            brief=project.brief,
            character_archives=character_roster,
        )
        if not issues:
            return plan
        self._emit(
            run_id,
            project.id,
            chapter.id,
            "PlanAnchorRepair",
            "细纲未通过开篇锚点校验，尝试一次受限修复",
            18,
            level="WARN",
            payload={"issues": issues},
        )
        repaired = self.gateway.repair_chapter_plan(
            plan,
            issues,
            planning.opening_anchor,
            number,
            project.brief,
        )
        if repaired.number != number:
            repaired = repaired.model_copy(update={"number": number})
        issues = validate_plan_against_anchor(
            repaired,
            chapter_number=number,
            context=planning,
            brief=project.brief,
            character_archives=character_roster,
        )
        if issues:
            self.repository.update_chapter(chapter.id, status=ChapterStatus.FAILED, plan=plan)
            self.repository.update_run(
                run_id,
                RunStatus.FAILED.value,
                {"node": "PlanAnchor", "issues": issues, "plan": plan.model_dump(mode="json")},
                "CHAPTER_PLAN_ANCHOR_MISMATCH",
            )
            raise WorkflowBlocked(
                "章节细纲未能绑定开篇锚点，已停止正文写作",
                code="CHAPTER_PLAN_ANCHOR_MISMATCH",
                details=issues,
            )
        return repaired

    @staticmethod
    def _merge_review_reports(
        base: ReviewReport,
        story_skills: ReviewReport,
    ) -> ReviewReport:
        return merge_review_reports(base, story_skills)

    @staticmethod
    def _merge_character_updates(
        updates: list[CharacterMemoryUpdate],
    ) -> list[CharacterMemoryUpdate]:
        merged: dict[str, CharacterMemoryUpdate] = {}
        for update in updates:
            current = merged.get(update.name)
            if current is None:
                merged[update.name] = update
                continue
            merged[update.name] = current.model_copy(
                update={
                    "role": (
                        "protagonist"
                        if "protagonist" in {current.role, update.role}
                        else update.role or current.role
                    ),
                    "importance": (
                        "core"
                        if "core" in {current.importance, update.importance}
                        else "major"
                    ),
                    "profile": update.profile or current.profile,
                    "immutable_facts": list(
                        dict.fromkeys([*current.immutable_facts, *update.immutable_facts])
                    ),
                    "current_goal": update.current_goal or current.current_goal,
                    "last_result": update.last_result or current.last_result,
                    "location": update.location or current.location,
                    "knowledge_gained": list(
                        dict.fromkeys([*current.knowledge_gained, *update.knowledge_gained])
                    ),
                    "relationship_changes": {
                        **current.relationship_changes,
                        **update.relationship_changes,
                    },
                }
            )
        return list(merged.values())

    @staticmethod
    def _assert_runnable(project: ProjectRecord) -> None:
        if not project.confirmed:
            raise WorkflowBlocked("创作方案尚未确认")
        if project.status == ProjectStatus.PAUSED:
            raise WorkflowBlocked("项目已暂停")
        if project.status in {ProjectStatus.ARCHIVED, ProjectStatus.HUMAN_REQUIRED}:
            raise WorkflowBlocked(f"项目当前状态不可自动写作：{project.status.value}")

    def _review(
        self,
        project: ProjectRecord,
        plan: ChapterPlan,
        protagonist_name: str,
        content: str,
        has_research: bool,
    ) -> ReviewReport:
        from novel_agent.features.chapter_review.quality_gate import review_structural

        return review_structural(project, plan, protagonist_name, content, has_research)

    @staticmethod
    def _summary(plan: ChapterPlan, content: str) -> str:
        tail = content.split("\n\n")[-1]
        return f"{plan.objective}。{plan.turning_point}。章末：{tail[:120]}"

    @staticmethod
    def _research_note(
        title: str,
        url: str,
        excerpt: str,
        score: float,
        verified: bool,
    ) -> str:
        status = "可交叉核验" if verified else "单一来源，保守使用"
        return (
            f"来源：{title}；URL：{url or '未提供'}；"
            f"可信度：{score:.2f}；核验：{status}；摘录：{excerpt[:1200]}"
        )

    def _index_pending(
        self,
        run_id: str,
        project_id: str,
        chapter_id: str,
        *,
        progress: int,
    ) -> None:
        try:
            pending = self.repository.list_pending_semantic_inputs(project_id)
            if not pending:
                return
            texts = [str(item["content"])[:8000] for item in pending]
            vectors = self.embedding.embed(texts)
            self.repository.upsert_semantic_documents(
                project_id, pending, vectors, self.embedding.model
            )
            self._emit(
                run_id,
                project_id,
                chapter_id,
                "SemanticIndex",
                f"已向量化 {len(pending)} 条章节摘要或研究资料",
                progress,
                payload={"documents": len(pending), "model": self.embedding.model},
            )
        except Exception as exc:
            self._emit(
                run_id,
                project_id,
                chapter_id,
                "SemanticIndex",
                f"向量索引失败但不阻断写作：{type(exc).__name__}",
                progress,
                level="WARN",
            )

    def _emit(
        self,
        run_id: str,
        project_id: str,
        chapter_id: str | None,
        node: str,
        message: str,
        progress: int,
        *,
        level: str = "INFO",
        payload: dict[str, Any] | None = None,
    ) -> None:
        event = RunEvent(
            run_id=run_id,
            project_id=project_id,
            chapter_id=chapter_id,
            node=node,
            message=message,
            progress=progress,
            level=level,
            payload=payload or {},
        )
        self.repository.add_event(event)
        self._events.append(event)

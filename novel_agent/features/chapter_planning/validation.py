from __future__ import annotations

import re

from novel_agent.features.chapter_planning.models import PlanningContext
from novel_agent.features.story_design.models import CreativeBrief, OpeningChapterAnchor
from novel_agent.models import ChapterPlan, CharacterRecord

CHAPTER1_FORBIDDEN_PHRASES = (
    "上一章",
    "承接前文",
    "承接上一章",
    "此前已经",
    "继续上章",
    "上章结尾",
    "承接上章",
)

_TOKEN_SPLIT = re.compile(r"[，。！？、；：:（）()【】\[\]“”\"'·\s]+")
_STOP_PHRASES = ("然后", "接着", "于是", "开始", "进行")
CORE_EVENT_NGRAM_THRESHOLD = 0.22
MUST_ESTABLISH_NGRAM_THRESHOLD = 0.28
MUST_ESTABLISH_MIN_CHARS = 8
FORBIDDEN_ASSUMPTION_NGRAM_THRESHOLD = 0.45


def plan_text_blob(plan: ChapterPlan) -> str:
    parts = [
        plan.title,
        plan.objective,
        plan.conflict,
        plan.turning_point,
        plan.hook,
        plan.opening_hook,
        plan.protagonist_goal,
        " ".join(plan.scenes),
    ]
    return "\n".join(parts)


def _normalize_anchor_text(text: str) -> str:
    compact = re.sub(r"^第\d+章\s*", "", text or "")
    compact = _TOKEN_SPLIT.sub("", compact)
    for phrase in _STOP_PHRASES:
        compact = compact.replace(phrase, "")
    return compact.casefold()


def _ngrams(text: str, size: int) -> set[str]:
    compact = _normalize_anchor_text(text)
    if not compact:
        return set()
    if len(compact) < size:
        return {compact}
    return {compact[index : index + size] for index in range(len(compact) - size + 1)}


def _overlap_score(left: str, right: str) -> float:
    scores: list[float] = []
    for size in (2, 3):
        left_grams = _ngrams(left, size)
        right_grams = _ngrams(right, size)
        if left_grams and right_grams:
            scores.append(len(left_grams & right_grams) / max(1, len(left_grams)))
    if scores:
        return max(scores)
    compact_left = _normalize_anchor_text(left)
    compact_right = _normalize_anchor_text(right)
    if not compact_left or not compact_right:
        return 0.0
    if compact_left in compact_right or compact_right in compact_left:
        return 1.0
    return 0.0


def validate_plan_against_anchor(
    plan: ChapterPlan,
    *,
    chapter_number: int,
    context: PlanningContext,
    brief: CreativeBrief,
    character_archives: list[CharacterRecord] | None = None,
) -> list[str]:
    issues: list[str] = []
    if plan.number != chapter_number:
        issues.append(f"plan.number={plan.number} 与当前章 {chapter_number} 不一致")
    blob = plan_text_blob(plan)
    if chapter_number == 1:
        for phrase in CHAPTER1_FORBIDDEN_PHRASES:
            if phrase in blob:
                issues.append(f"第一章细纲包含禁用前情表达：{phrase}")
        if (plan.model_dump().get("previous_chapter_excerpt") or "").strip():
            issues.append("第一章细纲不得携带上一章摘录")
        if context.recent_summaries or context.timeline or context.open_threads or context.previous_chapter_excerpt:
            issues.append("第一章规划上下文必须全空")
        if any(item.strip() for item in context.open_threads):
            issues.append("第一章不得注入开放线索")
    anchor = context.opening_anchor
    if anchor is not None:
        issues.extend(_anchor_alignment_issues(plan, anchor, brief, chapter_number))
    issues.extend(
        _relationship_origin_issues(plan, brief, character_archives or [], chapter_number)
    )
    issues.extend(_future_as_present_issues(plan, brief))
    return issues


def _anchor_alignment_issues(
    plan: ChapterPlan,
    anchor: OpeningChapterAnchor,
    brief: CreativeBrief,
    chapter_number: int,
) -> list[str]:
    issues: list[str] = []
    blob = plan_text_blob(plan)
    title_bound = False
    if anchor.title.strip():
        title_core = re.sub(r"^第\d+章\s*", "", plan.title).strip()
        title_bound = anchor.title in plan.title or anchor.title in title_core
        if not title_bound:
            issues.append(f"标题未绑定开篇锚点「{anchor.title}」")
    score = _overlap_score(anchor.core_event, blob)
    established = 0
    for item in anchor.must_establish:
        compact = _normalize_anchor_text(item)
        if len(compact) < MUST_ESTABLISH_MIN_CHARS:
            continue
        if _overlap_score(item, blob) >= MUST_ESTABLISH_NGRAM_THRESHOLD or item in blob:
            established += 1
        else:
            issues.append(f"细纲未落实开篇必须建立项：{item}")
    if score < CORE_EVENT_NGRAM_THRESHOLD and not (title_bound and established):
        issues.append("核心事件与锁定开篇锚点不一致")
    for item in anchor.forbidden_assumptions:
        if item and (
            item in blob or _overlap_score(item, blob) >= FORBIDDEN_ASSUMPTION_NGRAM_THRESHOLD
        ):
            issues.append(f"细纲命中开篇禁止预设：{item}")
    sibling_hits: list[str] = []
    for other in brief.opening_chapter_anchors:
        if int(other.number) == int(chapter_number):
            continue
        other_score = max(
            _overlap_score(other.core_event, blob),
            _overlap_score(other.title, blob) if other.title else 0.0,
        )
        if other.title and other.title in plan.title and other.title != anchor.title:
            sibling_hits.append(other.title)
        elif other_score > score + 0.08 and other_score > 0.40:
            sibling_hits.append(other.core_event[:40])
    if sibling_hits:
        issues.append(f"细纲更接近相邻开篇锚点：{'、'.join(sibling_hits)}")
    return issues


def _relationship_origin_issues(
    plan: ChapterPlan,
    brief: CreativeBrief,
    archives: list[CharacterRecord],
    chapter_number: int,
) -> list[str]:
    if chapter_number != 1:
        return []
    allowed: dict[str, set[str]] = {}
    for profile in brief.character_profiles:
        allowed[profile.name] = set(profile.initial_relationships)
    for character in archives:
        rels = character.current_state.get("relationships") or {}
        if isinstance(rels, dict):
            allowed.setdefault(character.name, set()).update(rels)
    issues: list[str] = []
    for name, change in (plan.relationship_changes or {}).items():
        text = str(change)
        if any(marker in text for marker in ("效忠", "代理人", "掌控者")) and name not in allowed.get(
            brief.protagonist_name, set()
        ):
            if "初次" not in text and "结识" not in text:
                issues.append(f"第一章人物关系变化超出初始关系：{name}")
    return issues


def _future_as_present_issues(plan: ChapterPlan, brief: CreativeBrief) -> list[str]:
    blob = plan_text_blob(plan)
    issues: list[str] = []
    for profile in brief.character_profiles:
        future = (profile.future_arc or "").strip()
        if len(future) >= 8 and future[:12] in blob:
            issues.append(f"把尚未发生的未来弧线当作既成事实：{profile.name}")
        for other, rel in (profile.future_relationships or {}).items():
            if rel and rel in blob and "将" not in blob:
                issues.append(f"把未来关系写成已经成立：{profile.name}-{other}")
    return issues


def assert_write_gate(
    plan: ChapterPlan,
    *,
    chapter_number: int,
    context: PlanningContext,
    character_archives: list[CharacterRecord],
) -> None:
    if plan.number != chapter_number:
        raise ValueError("WRITE_GATE: plan.number 不正确")
    if chapter_number == 1 and context.previous_chapter_excerpt:
        raise ValueError("WRITE_GATE: 第一章不得带上一章摘录")
    for character in character_archives:
        blob = " ".join(character.immutable_facts) + str(character.current_state)
        if "future_arc" in blob or "未来弧线" in blob:
            raise ValueError("WRITE_GATE: 人物档案把未来弧线写入了当前状态")

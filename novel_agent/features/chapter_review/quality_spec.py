from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from novel_agent.features.story_design.models import OpeningChapterAnchor
from novel_agent.models import ChapterPlan

READABILITY_DIMENSIONS = (
    "opening_hook",
    "scene_causality",
    "conflict_escalation",
    "character_agency",
    "dialogue_voice",
    "showing_specificity",
    "reader_payoff",
    "ending_hook",
)

READABILITY_DIMENSION_LABELS = {
    "opening_hook": "开篇钩子",
    "scene_causality": "场景因果",
    "conflict_escalation": "冲突升级",
    "character_agency": "人物能动性",
    "dialogue_voice": "对话声口",
    "showing_specificity": "具体描写",
    "reader_payoff": "读者回报",
    "ending_hook": "结尾钩子",
}

READABILITY_DIMENSION_SUGGESTIONS = {
    "opening_hook": "重写开篇 300 字，用正在发生的具体问题和后果建立阅读牵引",
    "scene_causality": "重排薄弱场景，使上一场的选择直接造成下一场的阻力或机会",
    "conflict_escalation": "增加会改变选择条件的阻力，避免只重复同一种危险",
    "character_agency": "让主要人物基于自身目标作出选择，并承担可见代价",
    "dialogue_voice": "按人物立场、知识和利益重写对话，删除同声同气的说明台词",
    "showing_specificity": "把情绪判断和作者解释改成动作、物件、感官细节与具体后果",
    "reader_payoff": "补足前置铺垫和兑现过程，让本章回报由角色行动挣得",
    "ending_hook": "用已经发生的事件或新后果收尾，删除预告式和升华式套话",
}

WRITE_TEMPERATURE = 0.72
REVISE_TEMPERATURE = 0.40
REVIEW_TEMPERATURE = 0.1
MAX_REVISION_ATTEMPTS_DEFAULT = 2
MAX_REVISION_ATTEMPTS_MIN = 0
MAX_REVISION_ATTEMPTS_MAX = 5

_CHAPTER_TITLE_LINE = re.compile(
    r"^\s*#*\s*第\s*[0-9零〇一二三四五六七八九十百千万两]+\s*章(?:\s|[-—:：·.、]|$)"
)


@dataclass(frozen=True, slots=True)
class QualityDimension:
    name: str
    label: str
    weight: float
    suggestion: str = ""


def _default_dimensions() -> tuple[QualityDimension, ...]:
    weight = 1.0 / len(READABILITY_DIMENSIONS)
    return tuple(
        QualityDimension(
            name=name,
            label=READABILITY_DIMENSION_LABELS[name],
            weight=weight,
            suggestion=READABILITY_DIMENSION_SUGGESTIONS[name],
        )
        for name in READABILITY_DIMENSIONS
    )


@dataclass(frozen=True, slots=True)
class ChapterQualityContract:
    """唯一写作—审核—修订质量契约。通过线只能是 quality_score > pass_score_exclusive。"""

    pass_score_exclusive: float = 60.0
    desired_generation_score: float = 85.0
    length_tolerance_chars: int = 500
    severe_shortage_ratio: float = 0.70
    max_length_repairs: int = 2
    max_quality_revisions: int = 2
    write_temperature: float = WRITE_TEMPERATURE
    revise_temperature: float = REVISE_TEMPERATURE
    review_temperature: float = REVIEW_TEMPERATURE
    dimensions: tuple[QualityDimension, ...] = _default_dimensions()

    def __post_init__(self) -> None:
        total = sum(item.weight for item in self.dimensions)
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"dimension weights must sum to 1.0, got {total}")


DEFAULT_QUALITY_CONTRACT = ChapterQualityContract()


def count_quality_chars(content: str | None) -> int:
    """Count every non-whitespace body character, including punctuation."""
    if not content:
        return 0
    text = content.replace("\r\n", "\n").replace("\r", "\n")
    first_line, separator, rest = text.partition("\n")
    body = rest if separator and _CHAPTER_TITLE_LINE.match(first_line) else text
    return sum(1 for char in body if not char.isspace())


def length_bounds(target_chars: int, contract: ChapterQualityContract = DEFAULT_QUALITY_CONTRACT) -> dict[str, int]:
    target = max(1, int(target_chars))
    tolerance = max(0, int(contract.length_tolerance_chars))
    accepted_min = max(1, target - tolerance)
    accepted_max = target + tolerance
    severe = min(int(target * contract.severe_shortage_ratio), accepted_min)
    return {
        "target_length": target,
        "accepted_length_min": accepted_min,
        "accepted_length_max": accepted_max,
        "severe_shortage_max": severe,
    }


def classify_length(
    actual_length: int,
    target_chars: int,
    contract: ChapterQualityContract = DEFAULT_QUALITY_CONTRACT,
) -> str:
    bounds = length_bounds(target_chars, contract)
    if actual_length < bounds["severe_shortage_max"]:
        return "severe_short"
    if actual_length < bounds["accepted_length_min"]:
        return "short"
    if actual_length > bounds["accepted_length_max"]:
        return "over"
    return "ok"


def compute_quality_score(
    dimension_scores: dict[str, float],
    contract: ChapterQualityContract = DEFAULT_QUALITY_CONTRACT,
) -> float:
    missing = [dim.name for dim in contract.dimensions if dim.name not in dimension_scores]
    if missing:
        raise ValueError(f"missing dimension scores: {', '.join(missing)}")
    total = 0.0
    for dim in contract.dimensions:
        total += float(dimension_scores[dim.name]) * dim.weight
    return round(total, 4)


def _anchor_payload(opening_anchor: OpeningChapterAnchor | None) -> dict[str, Any] | None:
    if opening_anchor is None:
        return None
    return opening_anchor.model_dump(mode="json")


def _shared_contract(
    *,
    chapter_number: int,
    target_chars: int,
    opening_anchor: OpeningChapterAnchor | None,
    previous_chapter_excerpt: str,
    exclude: list[str],
    contract: ChapterQualityContract = DEFAULT_QUALITY_CONTRACT,
) -> dict[str, Any]:
    bounds = length_bounds(target_chars, contract)
    dimensions = [
        {
            "name": dim.name,
            "label": dim.label,
            "weight": dim.weight,
            "suggestion": dim.suggestion,
        }
        for dim in contract.dimensions
    ]
    hard_rules = [
        "不得出现创作排除项",
        "正文不得为空或被截断",
        "不得把尚未发生的人物关系或未来事实写成当前事实",
        "不得与世界硬规则直接冲突",
        f"综合质量分必须严格高于 {contract.pass_score_exclusive} 才算通过",
        f"写作目标尽量达到 {contract.desired_generation_score} 分以上，但这不是隐藏通过线",
        f"正文字数应落在 {bounds['accepted_length_min']}～{bounds['accepted_length_max']}（目标约 {bounds['target_length']}）",
        "字数统计包含标点符号，不包含空格、换行和明确的「第 X 章」标题行",
        "MAJOR/BLOCKER 仅表示修订优先级，不能单独否决已超过通过线的总分",
    ]
    extras: list[str] = []
    is_chapter_one = chapter_number == 1
    if is_chapter_one:
        extras.extend(
            [
                "第一章没有上一章，禁止检查或要求承接不存在的前文",
                "不得因为缺少前文章节档案而产生连续性误报",
                "自然完成：主角基本定位、当前处境、必要背景、开篇事件或冲突、后续钩子",
                "必须用场景和行动完成 opening_anchor.must_establish（若有）",
                "禁止把 opening_anchor.forbidden_assumptions 写成已经成立的事实（若有）",
            ]
        )
    else:
        extras.append("直接承接上一章未完成动作、问题和在场人物，不得复述或摘要上一章")
    return {
        "dimensions": dimensions,
        "pass_score_exclusive": contract.pass_score_exclusive,
        "desired_generation_score": contract.desired_generation_score,
        "quality_pass_score": contract.pass_score_exclusive,
        "length_tolerance_chars": contract.length_tolerance_chars,
        "severe_shortage_ratio": contract.severe_shortage_ratio,
        "max_length_repairs": contract.max_length_repairs,
        "max_quality_revisions": contract.max_quality_revisions,
        "target_chars": bounds["target_length"],
        "accepted_length_min": bounds["accepted_length_min"],
        "accepted_length_max": bounds["accepted_length_max"],
        "exclude": exclude,
        "hard_rules": [*hard_rules, *extras],
        "chapter_number": chapter_number,
        "is_chapter_one": is_chapter_one,
        "has_previous_chapter": (not is_chapter_one)
        and bool((previous_chapter_excerpt or "").strip()),
        "opening_anchor": _anchor_payload(opening_anchor),
        "must_establish": list(opening_anchor.must_establish) if opening_anchor else [],
        "forbidden_assumptions": (
            list(opening_anchor.forbidden_assumptions) if opening_anchor else []
        ),
    }


def build_writer_quality_contract(
    *,
    chapter_number: int,
    target_chars: int,
    opening_anchor: OpeningChapterAnchor | None = None,
    previous_chapter_excerpt: str = "",
    exclude: list[str] | None = None,
    spec: ChapterQualityContract | None = None,
    contract: ChapterQualityContract | None = None,
) -> dict[str, Any]:
    active = contract or spec or DEFAULT_QUALITY_CONTRACT
    payload = _shared_contract(
        chapter_number=chapter_number,
        target_chars=target_chars,
        opening_anchor=opening_anchor,
        previous_chapter_excerpt=previous_chapter_excerpt,
        exclude=list(exclude or []),
        contract=active,
    )
    payload["role"] = "writer"
    payload["internal_check"] = (
        f"落笔前按质量契约自检，写作目标约 {active.desired_generation_score} 分；"
        f"先按场景分配字数，输出前内部核对正文必须为 "
        f"{payload['accepted_length_min']}～{payload['accepted_length_max']} 字（标点计入）；"
        "不足时补因果、动作和有效对话，超出时删重复；"
        "最终只输出标题和正文，不得输出自评表。"
    )
    return payload


def build_reviewer_quality_contract(
    *,
    chapter_number: int,
    target_chars: int,
    opening_anchor: OpeningChapterAnchor | None = None,
    previous_chapter_excerpt: str = "",
    exclude: list[str] | None = None,
    spec: ChapterQualityContract | None = None,
    contract: ChapterQualityContract | None = None,
) -> dict[str, Any]:
    active = contract or spec or DEFAULT_QUALITY_CONTRACT
    payload = _shared_contract(
        chapter_number=chapter_number,
        target_chars=target_chars,
        opening_anchor=opening_anchor,
        previous_chapter_excerpt=previous_chapter_excerpt,
        exclude=list(exclude or []),
        contract=active,
    )
    payload["role"] = "reviewer"
    payload["decision_rule"] = (
        f"只根据加权综合 quality_score 是否严格大于 {active.pass_score_exclusive} 判定通过；"
        "单项分、平均分、MAJOR/BLOCKER 不得作为第二套通过条件。"
    )
    return payload


def writer_quality_prompt_fragment(contract: dict[str, Any]) -> str:
    names = "、".join(item["name"] for item in contract["dimensions"])
    return (
        "quality_contract 是唯一质量标准，与审稿器和修订器共用。"
        f"八维为 {names}；写作目标约 {contract['desired_generation_score']} 分；"
        f"最终通过条件只有综合分严格高于 {contract['pass_score_exclusive']}；"
        f"字数落在 {contract['accepted_length_min']}～{contract['accepted_length_max']}。"
        "标点符号计入字数，空格、换行和明确的章节标题行不计。"
        "先按 scene_beats 分配篇幅，输出前内部核对字数和质量契约，"
        "不足时补有效剧情，超出时删除重复，最终只输出标题和正文。"
    )


def plan_payload_for_contract(plan: ChapterPlan) -> dict[str, Any]:
    return plan.model_dump(mode="json")

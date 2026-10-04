"""Deterministic continuity checks that ignore future arcs but enforce initial facts."""

from __future__ import annotations

from novel_agent.features.story_design.models import CreativeBrief
from novel_agent.models import CharacterRecord, IssueSeverity, ReviewIssue


def strip_future_fields_from_brief(brief: CreativeBrief) -> dict:
    data = brief.model_dump(mode="json")
    for profile in data.get("character_profiles") or []:
        profile["future_arc"] = ""
        profile["future_relationships"] = {}
    return data


def relationship_guard_issues(
    content: str,
    *,
    brief: CreativeBrief,
    characters: list[CharacterRecord],
    chapter_number: int,
) -> list[ReviewIssue]:
    issues: list[ReviewIssue] = []
    if chapter_number != 1:
        return _established_relationship_issues(content, characters)
    for profile in brief.character_profiles:
        for other, rel in (profile.future_relationships or {}).items():
            marker = str(rel).strip()
            if not marker:
                continue
            if marker in content and profile.name in content and other in content:
                continue
        for other, rel in (profile.initial_relationships or {}).items():
            if not rel.strip():
                continue
            if profile.name in content and other in content:
                if _contradicts_established(rel, content):
                    issues.append(
                        ReviewIssue(
                            category="Character Knowledge & State",
                            severity=IssueSeverity.MAJOR,
                            message=f"{profile.name} 与 {other} 的正文关系违反了开篇已成立的初始关系",
                            suggestion="从 initial_relationships 出发写本章关系变化，不要提前写成未来结果",
                            evidence=[rel],
                        )
                    )
    issues.extend(_established_relationship_issues(content, characters))
    return issues


def _established_relationship_issues(
    content: str, characters: list[CharacterRecord]
) -> list[ReviewIssue]:
    issues: list[ReviewIssue] = []
    for character in characters:
        rels = character.current_state.get("relationships") or {}
        if not isinstance(rels, dict):
            continue
        for other, rel in rels.items():
            rel_text = str(rel)
            if not rel_text.strip():
                continue
            if character.name in content and str(other) in content and _contradicts_established(
                rel_text, content
            ):
                issues.append(
                    ReviewIssue(
                        category="Character Knowledge & State",
                        severity=IssueSeverity.MAJOR,
                        message=f"{character.name} 与 {other} 违反了已成立的正式关系",
                        suggestion="正文关系变化必须从正式记忆中的当前关系出发",
                        evidence=[rel_text],
                    )
                )
    return issues


def _contradicts_established(rel: str, content: str) -> bool:
    if any(token in rel for token in ("效忠", "主仆", "夫妻", "盟友", "师徒")):
        if any(token in content for token in ("初次见面", "第一次见面", "素未谋面", "还不认识")):
            return True
    if any(token in rel for token in ("互不相识", "尚未见面", "陌生人", "不认识")):
        if any(token in content for token in ("效忠多年", "一直效忠", "早已效忠", "多年主仆")):
            return True
    return False

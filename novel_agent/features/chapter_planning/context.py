from __future__ import annotations

from typing import Any, Protocol

from novel_agent.features.chapter_planning.anchors import resolve_opening_anchor
from novel_agent.features.chapter_planning.models import PlanningContext
from novel_agent.features.story_design.models import CreativeBrief
from novel_agent.models import ChapterRecord, ChapterStatus


class TimelineSource(Protocol):
    def list_timeline(self, project_id: str) -> list[dict[str, Any]]: ...


def _ready_prior_chapters(
    chapters: list[ChapterRecord], chapter_number: int
) -> list[ChapterRecord]:
    return [
        item
        for item in chapters
        if item.number < chapter_number
        and item.status == ChapterStatus.READY
        and item.content
    ]


def build_planning_context(
    *,
    project_id: str,
    chapter_number: int,
    brief: CreativeBrief,
    chapters: list[ChapterRecord],
    timeline_source: TimelineSource | None = None,
    timeline: list[dict[str, Any]] | None = None,
) -> PlanningContext:
    if chapter_number == 1:
        return PlanningContext(
            chapter_number=1,
            recent_summaries=[],
            timeline=[],
            open_threads=[],
            previous_chapter_excerpt="",
            opening_anchor=resolve_opening_anchor(brief, 1),
        )
    prior = _ready_prior_chapters(chapters, chapter_number)
    summaries = [item.summary for item in prior[-6:] if item.summary]
    excerpt = (prior[-1].content or "")[-1800:] if prior else ""
    events = list(timeline) if timeline is not None else []
    if timeline is None and timeline_source is not None:
        events = [
            item
            for item in timeline_source.list_timeline(project_id)
            if int(item.get("chapter_number") or 0) < chapter_number
        ]
    open_threads = [str(item.get("event") or "")[:40] for item in events[-3:] if item.get("event")]
    return PlanningContext(
        chapter_number=chapter_number,
        recent_summaries=summaries,
        timeline=events,
        open_threads=open_threads,
        previous_chapter_excerpt=excerpt,
        opening_anchor=resolve_opening_anchor(brief, chapter_number),
    )


def filter_semantic_matches(
    matches: list[dict[str, Any]],
    *,
    chapter_number: int,
    chapters: list[ChapterRecord],
) -> list[dict[str, Any]]:
    ready_ids = {
        item.id
        for item in chapters
        if item.number < chapter_number and item.status == ChapterStatus.READY
    }
    number_by_id = {item.id: item.number for item in chapters}
    filtered: list[dict[str, Any]] = []
    for match in matches:
        chapter_id = match.get("chapter_id")
        if not chapter_id:
            filtered.append(match)
            continue
        number = number_by_id.get(str(chapter_id))
        if number is None:
            continue
        if number >= chapter_number:
            continue
        if str(chapter_id) not in ready_ids:
            continue
        filtered.append(match)
    return filtered

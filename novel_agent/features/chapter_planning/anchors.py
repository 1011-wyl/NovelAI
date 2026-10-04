from __future__ import annotations

from novel_agent.features.story_design.models import CreativeBrief, OpeningChapterAnchor


def resolve_opening_anchor(
    brief: CreativeBrief, chapter_number: int
) -> OpeningChapterAnchor | None:
    if chapter_number not in {1, 2, 3}:
        return None
    for anchor in brief.opening_chapter_anchors:
        if int(anchor.number) == int(chapter_number):
            return anchor
    if 1 <= chapter_number <= len(brief.opening_three_chapters):
        text = str(brief.opening_three_chapters[chapter_number - 1]).strip()
        if text:
            return OpeningChapterAnchor(
                number=chapter_number,  # type: ignore[arg-type]
                title="",
                core_event=text,
            )
    return None

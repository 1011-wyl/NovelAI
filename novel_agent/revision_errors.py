from __future__ import annotations


class ChapterNotEditableError(RuntimeError):
    """Chapter is not in an editable READY state."""

    code = "CHAPTER_NOT_EDITABLE"


class EditConflictError(RuntimeError):
    """Working draft or base version conflicted with concurrent edits."""

    code = "EDIT_CONFLICT"


class AssistantChangeStaleError(RuntimeError):
    """Pending change no longer matches current working draft."""

    code = "ASSISTANT_CHANGE_STALE"


class AssistantChangeStateError(RuntimeError):
    """Change set is not in the expected lifecycle state."""

    code = "ASSISTANT_CHANGE_STATE"


class RevisionAnalysisError(RuntimeError):
    """LLM revision analysis failed or returned invalid structure."""

    code = "REVISION_ANALYSIS_FAILED"

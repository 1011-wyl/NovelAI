"""Story design feature errors.

RequirementConflict remains a ValueError subclass with the historical shape
used by HTTP mapping and existing tests; do not change its public MRO lightly.
"""

from __future__ import annotations


class StoryDesignError(RuntimeError):
    """Base error for story-design failures."""


class StoryDesignNotEditableError(StoryDesignError):
    """Draft brief is not editable in the current project state."""


class BriefVersionNotFoundError(StoryDesignError):
    """Requested brief version does not exist."""

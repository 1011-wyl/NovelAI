"""Compatibility re-export for requirement validation (migration-period Facade).

Canonical implementation: novel_agent.features.story_design.requirements
"""

from __future__ import annotations

from novel_agent.features.story_design.requirements import (
    RequirementConflict,
    validate_requirements,
)

__all__ = ["RequirementConflict", "validate_requirements"]

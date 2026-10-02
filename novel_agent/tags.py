"""Compatibility re-export for tag catalog (migration-period Facade).

Canonical implementation: novel_agent.features.story_design.tags
"""

from __future__ import annotations

from novel_agent.features.story_design.tags import TAG_CATALOG, public_tag_catalog

__all__ = ["TAG_CATALOG", "public_tag_catalog"]

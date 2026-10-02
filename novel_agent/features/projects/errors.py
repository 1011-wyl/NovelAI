"""Project feature errors.

External HTTP / isinstance mappings stay on existing RepositoryError / ValueError
until route tests freeze a finer taxonomy. Stubs exist for future refinement only.
"""

from __future__ import annotations


class ProjectError(RuntimeError):
    """Base error for project lifecycle failures."""


class ProjectNotFoundError(ProjectError):
    """Requested project does not exist."""


class ProjectStateError(ProjectError):
    """Project is not in a state that allows the requested action."""


class ProjectDeletionConfirmationError(ProjectError):
    """Force-delete confirmation title does not match the project title."""

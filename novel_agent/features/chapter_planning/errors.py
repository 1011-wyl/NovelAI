from __future__ import annotations

from typing import Any


class ReworkModeNotAllowedError(RuntimeError):
    code = "REWORK_MODE_NOT_ALLOWED"

    def __init__(self, message: str, *, details: Any = None):
        super().__init__(message)
        self.details = details

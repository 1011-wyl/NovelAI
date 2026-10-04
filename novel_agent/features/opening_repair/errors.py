from __future__ import annotations

from http import HTTPStatus
from typing import Any


class OpeningRepairError(RuntimeError):
    status = HTTPStatus.CONFLICT
    code = "OPENING_REPAIR_NOT_ELIGIBLE"

    def __init__(self, message: str, *, code: str | None = None, details: Any = None):
        super().__init__(message)
        if code:
            self.code = code
        self.details = details


class ChapterActionNotAllowedError(RuntimeError):
    code = "CHAPTER_ACTION_NOT_ALLOWED"

    def __init__(self, message: str, *, details: Any = None):
        super().__init__(message)
        self.details = details

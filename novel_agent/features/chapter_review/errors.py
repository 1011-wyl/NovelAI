from __future__ import annotations

from http import HTTPStatus
from typing import Any


class QualityOverrideNotAllowedError(RuntimeError):
    status = HTTPStatus.CONFLICT
    code = "QUALITY_OVERRIDE_NOT_ALLOWED"

    def __init__(self, message: str, *, details: Any = None):
        super().__init__(message)
        self.details = details

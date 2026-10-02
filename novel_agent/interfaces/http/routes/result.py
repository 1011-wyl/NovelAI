"""Shared HTTP route result type."""

from __future__ import annotations

from dataclasses import dataclass
from http import HTTPStatus
from typing import Any


@dataclass(frozen=True, slots=True)
class RouteResult:
    payload: Any
    status: HTTPStatus = HTTPStatus.OK

"""Opening-repair HTTP routes."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import unquote

from novel_agent.features.opening_repair.models import OpeningRepairApplyRequest
from novel_agent.features.opening_repair.service import OpeningRepairService
from novel_agent.interfaces.http.routes.result import RouteResult

_PREVIEW = re.compile(r"/api/novels/([^/]+)/opening-repair-preview")
_LATEST = re.compile(r"/api/novels/([^/]+)/opening-repair-snapshots/latest")
_APPLY = re.compile(r"/api/novels/([^/]+)/opening-repair$")
_ROLLBACK = re.compile(r"/api/novels/([^/]+)/opening-repair/([^/]+)/rollback")


def dispatch_opening_repair_get(path: str, service: OpeningRepairService) -> RouteResult | None:
    latest_match = _LATEST.fullmatch(path)
    if latest_match:
        return RouteResult(service.latest_snapshot(unquote(latest_match.group(1))))
    match = _PREVIEW.fullmatch(path)
    if not match:
        return None
    preview = service.preview(unquote(match.group(1)))
    return RouteResult(preview.model_dump(mode="json"))


def dispatch_opening_repair_post(
    path: str, payload: dict[str, Any], service: OpeningRepairService
) -> RouteResult | None:
    apply_match = _APPLY.fullmatch(path)
    if apply_match:
        request = OpeningRepairApplyRequest.model_validate(payload)
        result = service.apply(unquote(apply_match.group(1)), request)
        return RouteResult(result.model_dump(mode="json"))
    rollback_match = _ROLLBACK.fullmatch(path)
    if rollback_match:
        return RouteResult(
            service.rollback(unquote(rollback_match.group(1)), unquote(rollback_match.group(2)))
        )
    return None

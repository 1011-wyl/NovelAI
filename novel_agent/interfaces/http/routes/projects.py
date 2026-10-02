"""Projects lifecycle HTTP routes."""

from __future__ import annotations

import re
from http import HTTPStatus
from typing import Any, Mapping
from urllib.parse import unquote

from novel_agent.features.projects.service import ProjectService
from novel_agent.interfaces.http.routes.result import RouteResult

_PROJECT_ID = r"/api/novels/([^/]+)"


def dispatch_projects_get(
    path: str,
    params: Mapping[str, str],
    service: ProjectService,
) -> RouteResult | None:
    if path == "/api/novels":
        return RouteResult({"items": service.list_projects()})
    match = re.fullmatch(_PROJECT_ID, path)
    if match:
        return RouteResult(service.get_detail(unquote(match.group(1))))
    return None


def dispatch_projects_post(
    path: str,
    payload: dict[str, Any],
    service: ProjectService,
) -> RouteResult | None:
    match = re.fullmatch(r"/api/novels/([^/]+)/(confirm|pause|resume|recover)", path)
    if not match:
        return None
    project_id = unquote(match.group(1))
    action = match.group(2)
    method = {
        "confirm": service.confirm,
        "pause": service.pause,
        "resume": service.resume,
        "recover": service.recover,
    }[action]
    return RouteResult(method(project_id))


def dispatch_projects_delete(
    path: str,
    payload: dict[str, Any],
    service: ProjectService,
) -> RouteResult | None:
    match = re.fullmatch(_PROJECT_ID, path)
    if not match:
        return None
    project_id = unquote(match.group(1))
    service.delete(
        project_id,
        confirmation_title=str(payload.get("confirmation_title", "")).strip() or None,
    )
    return RouteResult({"deleted": True, "project_id": project_id})

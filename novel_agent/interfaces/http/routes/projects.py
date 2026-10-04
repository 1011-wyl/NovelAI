"""Projects lifecycle HTTP routes."""

from __future__ import annotations

import re
from typing import Any, Mapping
from urllib.parse import unquote

from novel_agent.features.projects.models import ProjectMetadataUpdate
from novel_agent.features.projects.service import ProjectService
from novel_agent.interfaces.http.routes.result import RouteResult

_PROJECT_ID = r"/api/novels/([^/]+)"


def dispatch_projects_get(
    path: str,
    params: Mapping[str, str],
    service: ProjectService,
) -> RouteResult | None:
    if path == "/api/novels":
        detail = (params.get("detail") or "").strip().lower()
        if detail == "full":
            # Temporary compatibility; Vue clients must use the default summary list.
            return RouteResult({"items": service.list_projects()})
        return RouteResult({"items": service.list_project_summaries()})
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


def dispatch_projects_put(
    path: str,
    payload: dict[str, Any],
    service: ProjectService,
) -> RouteResult | None:
    match = re.fullmatch(r"/api/novels/([^/]+)/metadata", path)
    if not match:
        return None
    update = ProjectMetadataUpdate.model_validate(payload)
    return RouteResult(service.update_metadata(unquote(match.group(1)), update))


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

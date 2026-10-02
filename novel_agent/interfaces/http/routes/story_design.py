"""Story-design HTTP routes."""

from __future__ import annotations

import re
from http import HTTPStatus
from typing import Any, Mapping
from urllib.parse import unquote

from novel_agent.features.story_design.models import (
    BriefRegenerateRequest,
    CreativeBrief,
    NovelCreateRequest,
)
from novel_agent.features.story_design.service import StoryDesignService
from novel_agent.interfaces.http.routes.result import RouteResult

_PROJECT_ID = r"/api/novels/([^/]+)"


def dispatch_story_design_get(
    path: str,
    params: Mapping[str, str],
    service: StoryDesignService,
) -> RouteResult | None:
    match = re.fullmatch(rf"{_PROJECT_ID}/brief-versions", path)
    if not match:
        return None
    return RouteResult(
        {"items": service.list_versions(unquote(match.group(1)))}
    )


def dispatch_story_design_post(
    path: str,
    payload: dict[str, Any],
    service: StoryDesignService,
) -> RouteResult | None:
    if path == "/api/novels":
        request = NovelCreateRequest.model_validate(payload)
        return RouteResult(service.create_story(request), HTTPStatus.CREATED)
    match = re.fullmatch(rf"{_PROJECT_ID}/brief-regenerate", path)
    if match:
        change = BriefRegenerateRequest.model_validate(payload)
        return RouteResult(
            service.regenerate_brief(unquote(match.group(1)), change)
        )
    match = re.fullmatch(rf"{_PROJECT_ID}/brief-restore", path)
    if match:
        return RouteResult(
            service.restore_brief(
                unquote(match.group(1)), int(payload.get("version", 0))
            )
        )
    return None


def dispatch_story_design_put(
    path: str,
    payload: dict[str, Any],
    service: StoryDesignService,
) -> RouteResult | None:
    match = re.fullmatch(rf"{_PROJECT_ID}/brief", path)
    if not match:
        return None
    brief = CreativeBrief.model_validate(payload)
    return RouteResult(service.update_brief(unquote(match.group(1)), brief))

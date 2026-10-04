from __future__ import annotations

from http import HTTPStatus
from typing import Any

from novel_agent.features.llm_settings.errors import LLMSettingsError
from novel_agent.features.llm_settings.service import LLMSettingsService
from novel_agent.interfaces.http.routes.result import RouteResult

LLM_SETTINGS_GET_PATHS = frozenset({"/api/settings/llm"})
LLM_SETTINGS_PUT_PATHS = frozenset({"/api/settings/llm"})
LLM_SETTINGS_POST_PATHS = frozenset({"/api/settings/llm/test"})
LLM_SETTINGS_DELETE_PATHS = frozenset({"/api/settings/llm"})


def dispatch_llm_settings_get(path: str, service: LLMSettingsService) -> RouteResult | None:
    if path not in LLM_SETTINGS_GET_PATHS:
        return None
    return RouteResult(service.safe_view())


def dispatch_llm_settings_put(
    path: str, payload: dict[str, Any], service: LLMSettingsService
) -> RouteResult | None:
    if path not in LLM_SETTINGS_PUT_PATHS:
        return None
    return RouteResult(service.save(payload))


def dispatch_llm_settings_post(
    path: str, payload: dict[str, Any], service: LLMSettingsService
) -> RouteResult | None:
    if path not in LLM_SETTINGS_POST_PATHS:
        return None
    return RouteResult(service.test_connection(payload))


def dispatch_llm_settings_delete(path: str, service: LLMSettingsService) -> RouteResult | None:
    if path not in LLM_SETTINGS_DELETE_PATHS:
        return None
    return RouteResult(service.delete())


def llm_settings_error_result(exc: LLMSettingsError) -> RouteResult:
    status = exc.status
    if exc.code == "CONFIG_VERSION_CONFLICT":
        status = HTTPStatus.CONFLICT
    elif exc.code == "SECRET_STORE_UNAVAILABLE":
        status = HTTPStatus.SERVICE_UNAVAILABLE
    elif exc.code in {"VALIDATION_ERROR", "INVALID_BASE_URL", "LLM_NOT_CONFIGURED"}:
        status = HTTPStatus.UNPROCESSABLE_ENTITY
    elif exc.code in {
        "INVALID_API_KEY",
        "MODEL_NOT_FOUND",
        "NETWORK_UNREACHABLE",
        "REQUEST_TIMEOUT",
        "RATE_LIMITED",
        "INSUFFICIENT_QUOTA",
        "PROVIDER_ERROR",
    }:
        status = HTTPStatus.BAD_GATEWAY
    return RouteResult(
        {"error": exc.code, "message": exc.message},
        status,
    )

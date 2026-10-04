from __future__ import annotations

import urllib.error

from novel_agent.features.llm_settings.errors import LLMSettingsError, USER_MESSAGES
from novel_agent.integrations.errors import APIConfigurationRequired
from novel_agent.integrations.llm.errors import (
    LLMAuthenticationError,
    LLMProviderError,
    LLMRateLimitError,
    LLMResponseError,
    LLMTimeoutError,
)
from novel_agent.ports import LLMGateway


def probe_connection(gateway: LLMGateway) -> None:
    probe = getattr(gateway, "probe_connection", None)
    if callable(probe):
        probe()
        return
    chat = getattr(gateway, "_chat", None)
    if callable(chat):
        chat(
            "You are a connection probe. Reply with ok.",
            "ok",
            max_tokens=8,
            temperature=0,
            operation="connection_probe",
        )
        return


def map_probe_error(exc: BaseException) -> LLMSettingsError:
    if isinstance(exc, LLMSettingsError):
        return exc
    http = _http_error(exc)
    text = str(exc).lower()
    if isinstance(exc, LLMAuthenticationError) or (http and http.code in {401, 403}):
        return LLMSettingsError("INVALID_API_KEY", USER_MESSAGES["INVALID_API_KEY"])
    if http and http.code == 404:
        return LLMSettingsError("MODEL_NOT_FOUND", USER_MESSAGES["MODEL_NOT_FOUND"])
    if isinstance(exc, LLMRateLimitError) or (http and http.code == 429):
        if "quota" in text or "insufficient" in text:
            return LLMSettingsError("INSUFFICIENT_QUOTA", USER_MESSAGES["INSUFFICIENT_QUOTA"])
        return LLMSettingsError("RATE_LIMITED", USER_MESSAGES["RATE_LIMITED"])
    if isinstance(exc, LLMTimeoutError):
        return LLMSettingsError("REQUEST_TIMEOUT", USER_MESSAGES["REQUEST_TIMEOUT"])
    if isinstance(exc, APIConfigurationRequired):
        message = str(exc)
        if "HTTPS" in message or "BASE_URL" in message or "地址" in message:
            return LLMSettingsError("INVALID_BASE_URL", USER_MESSAGES["INVALID_BASE_URL"])
        if "Key" in message or "密钥" in message:
            return LLMSettingsError("INVALID_API_KEY", USER_MESSAGES["INVALID_API_KEY"])
        if "尚未配置" in message:
            return LLMSettingsError("LLM_NOT_CONFIGURED", USER_MESSAGES["LLM_NOT_CONFIGURED"])
        return LLMSettingsError("VALIDATION_ERROR", USER_MESSAGES["VALIDATION_ERROR"])
    if isinstance(exc, LLMResponseError):
        return LLMSettingsError("PROVIDER_ERROR", USER_MESSAGES["PROVIDER_ERROR"])
    if isinstance(exc, LLMProviderError):
        if "无法连接" in str(exc):
            return LLMSettingsError("NETWORK_UNREACHABLE", USER_MESSAGES["NETWORK_UNREACHABLE"])
        return LLMSettingsError("PROVIDER_ERROR", USER_MESSAGES["PROVIDER_ERROR"])
    if "timed out" in text or "timeout" in text:
        return LLMSettingsError("REQUEST_TIMEOUT", USER_MESSAGES["REQUEST_TIMEOUT"])
    return LLMSettingsError("PROVIDER_ERROR", USER_MESSAGES["PROVIDER_ERROR"])


def _http_error(exc: BaseException) -> urllib.error.HTTPError | None:
    current: BaseException | None = exc
    seen = 0
    while current is not None and seen < 6:
        if isinstance(current, urllib.error.HTTPError):
            return current
        current = current.__cause__ or current.__context__
        seen += 1
    return None

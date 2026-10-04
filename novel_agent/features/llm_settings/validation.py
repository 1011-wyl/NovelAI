from __future__ import annotations

import re
from urllib.parse import urlparse

from novel_agent.features.llm_settings.errors import LLMSettingsError
from novel_agent.features.llm_settings.models import LLMProvider

_MODEL_RE = re.compile(r"^[A-Za-z0-9._:/\-]{1,128}$")


def parse_provider(value: object) -> LLMProvider:
    raw = str(value or "").strip()
    if raw == "qwen":
        return LLMProvider.DASHSCOPE
    try:
        return LLMProvider(raw)
    except ValueError as exc:
        raise LLMSettingsError("VALIDATION_ERROR", "请选择支持的模型供应商") from exc


def normalize_base_url(value: object) -> str:
    raw = str(value or "").strip().rstrip("/")
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise LLMSettingsError("INVALID_BASE_URL", "API 地址必须是合法的 http 或 https 网址")
    if parsed.scheme != "https" and parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise LLMSettingsError("INVALID_BASE_URL", "生产环境请使用 HTTPS 地址")
    return raw


def normalize_model(value: object) -> str:
    raw = str(value or "").strip()
    if not _MODEL_RE.fullmatch(raw):
        raise LLMSettingsError("VALIDATION_ERROR", "模型 ID 为 1～128 个字母、数字或常见分隔符")
    return raw


def normalize_timeout(value: object, default: int = 120) -> int:
    try:
        parsed = int(value if value is not None else default)
    except (TypeError, ValueError) as exc:
        raise LLMSettingsError("VALIDATION_ERROR", "超时时间必须是 10～300 的整数") from exc
    if parsed < 10 or parsed > 300:
        raise LLMSettingsError("VALIDATION_ERROR", "超时时间必须是 10～300 秒")
    return parsed


def normalize_retries(value: object, default: int = 2) -> int:
    try:
        parsed = int(value if value is not None else default)
    except (TypeError, ValueError) as exc:
        raise LLMSettingsError("VALIDATION_ERROR", "重试次数必须是 0～5 的整数") from exc
    if parsed < 0 or parsed > 5:
        raise LLMSettingsError("VALIDATION_ERROR", "重试次数必须是 0～5")
    return parsed


def mask_api_key(api_key: str) -> str:
    tail = "".join(ch for ch in api_key if ch.isalnum())[-4:]
    return f"••••{tail}" if tail else "••••"


def reject_if_looks_like_secret(payload: dict[str, object]) -> None:
    for key, value in payload.items():
        lowered = str(key).lower()
        if "key" in lowered or "secret" in lowered or "authorization" in lowered:
            if lowered in {"has_api_key", "api_key_mask", "keep_existing_api_key"}:
                continue
            if isinstance(value, str) and len(value) > 8 and value not in {"••••"}:
                # Defensive: callers must never serialize raw keys into views.
                payload[key] = "••••"

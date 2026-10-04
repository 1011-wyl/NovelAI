from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from novel_agent.features.llm_settings.models import LLMConfiguration, LLMProvider

SETTING_KEY = "llm.ui_configuration"


class LLMSettingsRepository:
    def __init__(self, store: Any) -> None:
        self._store = store

    def load(self) -> LLMConfiguration | None:
        raw = self._store.get_setting(SETTING_KEY)
        if not isinstance(raw, dict):
            return None
        return _from_payload(raw)

    def save(self, config: LLMConfiguration) -> None:
        self._store.save_setting(SETTING_KEY, _to_payload(config))

    def delete(self) -> None:
        self._store.delete_setting(SETTING_KEY)


def _to_payload(config: LLMConfiguration) -> dict[str, Any]:
    return {
        "id": config.id,
        "provider": config.provider.value,
        "base_url": config.base_url,
        "model": config.model,
        "enabled": config.enabled,
        "timeout_seconds": config.timeout_seconds,
        "max_retries": config.max_retries,
        "secret_ref": config.secret_ref,
        "api_key_mask": config.api_key_mask,
        "verification_status": config.verification_status,
        "last_tested_at": config.last_tested_at.isoformat() if config.last_tested_at else None,
        "last_error_code": config.last_error_code,
        "created_at": config.created_at.isoformat(),
        "updated_at": config.updated_at.isoformat(),
        "version": config.version,
    }


def _from_payload(raw: dict[str, Any]) -> LLMConfiguration:
    return LLMConfiguration(
        id=str(raw.get("id") or "llm-default"),
        provider=LLMProvider(str(raw.get("provider"))),
        base_url=str(raw.get("base_url") or ""),
        model=str(raw.get("model") or ""),
        enabled=bool(raw.get("enabled")),
        timeout_seconds=int(raw.get("timeout_seconds") or 120),
        max_retries=int(raw.get("max_retries") or 2),
        secret_ref=str(raw["secret_ref"]) if raw.get("secret_ref") else None,
        api_key_mask=str(raw["api_key_mask"]) if raw.get("api_key_mask") else None,
        verification_status=str(raw.get("verification_status") or "unverified"),
        last_tested_at=_parse_dt(raw.get("last_tested_at")),
        last_error_code=str(raw["last_error_code"]) if raw.get("last_error_code") else None,
        created_at=_parse_dt(raw.get("created_at")) or datetime.now(timezone.utc),
        updated_at=_parse_dt(raw.get("updated_at")) or datetime.now(timezone.utc),
        version=int(raw.get("version") or 1),
    )


def _parse_dt(value: object) -> datetime | None:
    if not value:
        return None
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text)

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from novel_agent.features.llm_settings.errors import LLMSettingsError, USER_MESSAGES
from novel_agent.features.llm_settings.factory import LLMClientFactory
from novel_agent.features.llm_settings.models import (
    EffectiveLLMConfig,
    LLMConfiguration,
    LLMConfigSource,
    LLMProvider,
)
from novel_agent.features.llm_settings.presets import PROVIDER_LABELS, presets_payload
from novel_agent.features.llm_settings.probe import map_probe_error, probe_connection
from novel_agent.features.llm_settings.repository import LLMSettingsRepository
from novel_agent.features.llm_settings.resolver import EffectiveLLMConfigResolver
from novel_agent.features.llm_settings.secret_store import SecretStore
from novel_agent.features.llm_settings.validation import (
    mask_api_key,
    normalize_base_url,
    normalize_model,
    normalize_retries,
    normalize_timeout,
    parse_provider,
)

LOGGER = logging.getLogger("novel_agent.llm_settings")


class LLMSettingsService:
    def __init__(
        self,
        repository: LLMSettingsRepository,
        secrets: SecretStore,
        resolver: EffectiveLLMConfigResolver,
        factory: LLMClientFactory,
        *,
        on_change=None,
    ) -> None:
        self._repository = repository
        self._secrets = secrets
        self._resolver = resolver
        self._factory = factory
        self._on_change = on_change

    def safe_view(self) -> dict[str, Any]:
        saved = self._repository.load()
        effective = self._resolver.resolve()
        return self._view(saved, effective)

    def runtime_card(self) -> dict[str, Any]:
        view = self.safe_view()
        status = view["card_status"]
        configured = view["source"] in {"saved", "environment"} or (
            view["source"] == "offline" and view["enabled"]
        )
        enabled = status == "enabled"
        return {
            "provider": view.get("provider") or None,
            "provider_label": view.get("provider_label") or None,
            "model": view.get("model") or None,
            "configured": bool(configured and view["source"] != "none"),
            "enabled": enabled,
            "card_status": status,
            "source": view["source"],
            "needs_attention": status == "needs_attention",
        }

    def save(self, payload: dict[str, Any]) -> dict[str, Any]:
        current = self._repository.load()
        expected = payload.get("expected_version")
        if current is not None and expected is not None and int(expected) != current.version:
            raise LLMSettingsError(
                "CONFIG_VERSION_CONFLICT",
                USER_MESSAGES["CONFIG_VERSION_CONFLICT"],
            )
        provider = parse_provider(payload.get("provider"))
        base_url = normalize_base_url(payload.get("base_url"))
        model = normalize_model(payload.get("model"))
        timeout_seconds = normalize_timeout(payload.get("timeout_seconds"))
        max_retries = normalize_retries(payload.get("max_retries"))
        enabled = bool(payload.get("enabled", True))
        submitted_key = str(payload.get("api_key") or "").strip()
        keep_existing = bool(payload.get("keep_existing_api_key"))
        now = datetime.now(timezone.utc)
        old_ref = current.secret_ref if current else None
        new_ref = None
        secret_ref = old_ref
        api_key_mask = current.api_key_mask if current else None
        if submitted_key:
            new_ref = f"llm-api-key-{uuid.uuid4().hex}"
            self._secrets.put(new_ref, submitted_key)
            secret_ref = new_ref
            api_key_mask = mask_api_key(submitted_key)
        elif keep_existing and old_ref and self._secrets.exists(old_ref):
            secret_ref = old_ref
        elif not enabled:
            secret_ref = old_ref
        else:
            raise LLMSettingsError("VALIDATION_ERROR", "新配置必须填写 API Key")
        if enabled and not secret_ref:
            if new_ref:
                self._secrets.delete(new_ref)
            raise LLMSettingsError("VALIDATION_ERROR", "新配置必须填写 API Key")
        changed_endpoint = (
            current is None
            or current.provider != provider
            or current.base_url != base_url
            or current.model != model
            or bool(submitted_key)
        )
        if enabled:
            verification = "valid"
            last_tested_at = now
            last_error = None
        elif changed_endpoint:
            verification = "unverified"
            last_tested_at = None
            last_error = None
        else:
            verification = current.verification_status if current else "unverified"
            last_tested_at = current.last_tested_at if current else None
            last_error = current.last_error_code if current else None
        config = LLMConfiguration(
            id=current.id if current else "llm-default",
            provider=provider,
            base_url=base_url,
            model=model,
            enabled=enabled,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            secret_ref=secret_ref,
            api_key_mask=api_key_mask,
            verification_status=verification,
            last_tested_at=last_tested_at,
            last_error_code=last_error,
            created_at=current.created_at if current else now,
            updated_at=now,
            version=(current.version + 1) if current else 1,
        )
        try:
            self._repository.save(config)
        except Exception:
            if new_ref:
                self._secrets.delete(new_ref)
            raise
        if new_ref and old_ref and old_ref != new_ref:
            self._secrets.delete(old_ref)
        self._notify_change()
        LOGGER.info(
            "llm settings saved provider=%s model=%s version=%s",
            provider.value,
            model,
            config.version,
        )
        return self.safe_view()

    def delete(self) -> dict[str, Any]:
        current = self._repository.load()
        self._repository.delete()
        if current and current.secret_ref:
            self._secrets.delete(current.secret_ref)
        self._notify_change()
        LOGGER.info("llm settings cleared")
        return self.safe_view()

    def test_connection(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        started = time.perf_counter()
        config = self._config_for_test(payload or {})
        if config.source is LLMConfigSource.OFFLINE:
            return {
                "ok": True,
                "code": "CONNECTION_OK",
                "message": "当前为离线演示模式，未连接远程服务",
                "latency_ms": 0,
                "tested_at": datetime.now(timezone.utc).isoformat(),
            }
        client = self._factory.create(config)
        try:
            probe_connection(client)
        except Exception as exc:
            mapped = map_probe_error(exc)
            LOGGER.info(
                "llm connection test failed provider=%s model=%s code=%s",
                config.adapter_name,
                config.model,
                mapped.code,
            )
            persist = not bool(str((payload or {}).get("api_key") or "").strip())
            if persist:
                self._record_test(False, mapped.code)
            raise mapped from exc
        latency_ms = int((time.perf_counter() - started) * 1000)
        persist = not bool(str((payload or {}).get("api_key") or "").strip())
        if persist:
            self._record_test(True, None)
        LOGGER.info(
            "llm connection test ok provider=%s model=%s latency_ms=%s",
            config.adapter_name,
            config.model,
            latency_ms,
        )
        return {
            "ok": True,
            "code": "CONNECTION_OK",
            "message": "连接成功",
            "latency_ms": latency_ms,
            "tested_at": datetime.now(timezone.utc).isoformat(),
        }

    def _config_for_test(self, payload: dict[str, Any]) -> EffectiveLLMConfig:
        submitted_key = str(payload.get("api_key") or "").strip()
        if payload.get("provider") or payload.get("base_url") or payload.get("model") or submitted_key:
            provider = parse_provider(payload.get("provider"))
            from novel_agent.features.llm_settings.presets import ADAPTER_NAMES

            api_key = submitted_key
            saved = self._repository.load()
            if not api_key:
                if saved and saved.secret_ref:
                    api_key = self._secrets.get(saved.secret_ref)
                else:
                    raise LLMSettingsError("VALIDATION_ERROR", "新配置必须填写 API Key")
            base_url = normalize_base_url(payload.get("base_url"))
            model = normalize_model(payload.get("model"))
            from novel_agent.features.llm_settings.models import LLMConfigSnapshot

            snapshot = LLMConfigSnapshot(
                provider=provider.value,
                provider_label=PROVIDER_LABELS[provider],
                model=model,
                base_url=base_url,
                source="form",
                version=saved.version if saved else 0,
                timeout_seconds=normalize_timeout(payload.get("timeout_seconds")),
                max_retries=normalize_retries(payload.get("max_retries")),
            )
            return EffectiveLLMConfig(
                source=LLMConfigSource.SAVED,
                provider=provider,
                adapter_name=ADAPTER_NAMES[provider],
                base_url=base_url,
                model=model,
                api_key=api_key,
                timeout_seconds=float(snapshot.timeout_seconds),
                max_retries=snapshot.max_retries,
                reasoning_budget_factor=3.0,
                version=snapshot.version,
                enabled=True,
                verification_status="unverified",
                last_tested_at=None,
                last_error_code=None,
                has_api_key=True,
                api_key_mask=mask_api_key(api_key),
                snapshot=snapshot,
            )
        effective = self._resolver.resolve()
        if effective.source in {LLMConfigSource.NONE}:
            raise LLMSettingsError("LLM_NOT_CONFIGURED", USER_MESSAGES["LLM_NOT_CONFIGURED"])
        return effective

    def _record_test(self, ok: bool, error_code: str | None) -> None:
        current = self._repository.load()
        if current is None:
            return
        now = datetime.now(timezone.utc)
        updated = LLMConfiguration(
            id=current.id,
            provider=current.provider,
            base_url=current.base_url,
            model=current.model,
            enabled=current.enabled,
            timeout_seconds=current.timeout_seconds,
            max_retries=current.max_retries,
            secret_ref=current.secret_ref,
            api_key_mask=current.api_key_mask,
            verification_status="valid" if ok else "invalid",
            last_tested_at=now,
            last_error_code=None if ok else error_code,
            created_at=current.created_at,
            updated_at=now,
            version=current.version,
        )
        self._repository.save(updated)

    def _notify_change(self) -> None:
        self._factory.invalidate()
        if self._on_change:
            self._on_change()

    def _view(self, saved, effective: EffectiveLLMConfig) -> dict[str, Any]:
        card_status = _card_status(saved, effective)
        provider = effective.provider.value if effective.provider else (saved.provider.value if saved else "")
        provider_label = (
            PROVIDER_LABELS[effective.provider]
            if effective.provider
            else (PROVIDER_LABELS[saved.provider] if saved else "")
        )
        if effective.source is LLMConfigSource.OFFLINE:
            provider = "offline"
            provider_label = "离线演示"
        payload = {
            "provider": provider or None,
            "provider_label": provider_label or None,
            "base_url": saved.base_url if saved else (effective.base_url or None),
            "model": (saved.model if saved else effective.model) or None,
            "enabled": bool(saved.enabled) if saved else effective.source in {
                LLMConfigSource.ENVIRONMENT,
                LLMConfigSource.OFFLINE,
                LLMConfigSource.SAVED,
            } and effective.enabled,
            "has_api_key": bool(saved.secret_ref) if saved else effective.has_api_key,
            "api_key_mask": saved.api_key_mask if saved else effective.api_key_mask,
            "verification_status": saved.verification_status if saved else effective.verification_status,
            "last_tested_at": saved.last_tested_at.isoformat() if saved and saved.last_tested_at else None,
            "last_error_code": saved.last_error_code if saved else effective.last_error_code,
            "source": effective.source.value,
            "version": saved.version if saved else 0,
            "timeout_seconds": saved.timeout_seconds if saved else int(effective.timeout_seconds),
            "max_retries": saved.max_retries if saved else int(effective.max_retries),
            "card_status": card_status,
            "presets": presets_payload(),
        }
        return payload


def _card_status(saved, effective: EffectiveLLMConfig) -> str:
    if saved is not None:
        if not saved.enabled:
            return "disabled"
        if saved.last_error_code in {"INVALID_API_KEY", "MODEL_NOT_FOUND"}:
            return "needs_attention"
        if saved.verification_status == "invalid":
            return "needs_attention"
        if effective.source is LLMConfigSource.SAVED and saved.secret_ref:
            return "enabled"
        if saved.verification_status == "unverified":
            return "unverified"
        return "unverified"
    if effective.source is LLMConfigSource.ENVIRONMENT:
        return "enabled"
    if effective.source is LLMConfigSource.OFFLINE:
        return "enabled"
    return "unconfigured"

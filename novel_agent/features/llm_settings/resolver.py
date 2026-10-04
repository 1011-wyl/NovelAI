from __future__ import annotations

from novel_agent.config import Settings
from novel_agent.features.llm_settings.models import (
    EffectiveLLMConfig,
    LLMConfigSnapshot,
    LLMConfigSource,
    LLMProvider,
)
from novel_agent.features.llm_settings.presets import ADAPTER_NAMES, PROVIDER_LABELS, PROVIDER_PRESETS
from novel_agent.features.llm_settings.repository import LLMSettingsRepository
from novel_agent.features.llm_settings.secret_store import SecretStore
from novel_agent.features.llm_settings.validation import mask_api_key, parse_provider


class EffectiveLLMConfigResolver:
    def __init__(
        self,
        settings: Settings,
        repository: LLMSettingsRepository,
        secrets: SecretStore,
    ) -> None:
        self._settings = settings
        self._repository = repository
        self._secrets = secrets

    def resolve(self) -> EffectiveLLMConfig:
        saved = self._try_saved()
        if saved is not None:
            return saved
        env = self._try_environment()
        if env is not None:
            return env
        if self._settings.mode == "offline":
            return self._offline()
        return self._none()

    def _try_saved(self) -> EffectiveLLMConfig | None:
        config = self._repository.load()
        if config is None:
            return None
        if not config.enabled:
            return self._disabled(config)
        if not config.secret_ref or not self._secrets.exists(config.secret_ref):
            return None
        api_key = self._secrets.get(config.secret_ref)
        adapter = ADAPTER_NAMES[config.provider]
        snapshot = LLMConfigSnapshot(
            provider=config.provider.value,
            provider_label=PROVIDER_LABELS[config.provider],
            model=config.model,
            base_url=config.base_url,
            source=LLMConfigSource.SAVED.value,
            version=config.version,
            timeout_seconds=config.timeout_seconds,
            max_retries=config.max_retries,
        )
        return EffectiveLLMConfig(
            source=LLMConfigSource.SAVED,
            provider=config.provider,
            adapter_name=adapter,
            base_url=config.base_url,
            model=config.model,
            api_key=api_key,
            timeout_seconds=float(config.timeout_seconds),
            max_retries=config.max_retries,
            reasoning_budget_factor=self._settings.llm_reasoning_budget_factor,
            version=config.version,
            enabled=True,
            verification_status=config.verification_status,
            last_tested_at=config.last_tested_at,
            last_error_code=config.last_error_code,
            has_api_key=True,
            api_key_mask=config.api_key_mask or mask_api_key(api_key),
            snapshot=snapshot,
        )

    def _disabled(self, config) -> EffectiveLLMConfig:
        snapshot = LLMConfigSnapshot(
            provider=config.provider.value,
            provider_label=PROVIDER_LABELS[config.provider],
            model=config.model,
            base_url=config.base_url,
            source=LLMConfigSource.SAVED.value,
            version=config.version,
            timeout_seconds=config.timeout_seconds,
            max_retries=config.max_retries,
        )
        return EffectiveLLMConfig(
            source=LLMConfigSource.SAVED,
            provider=config.provider,
            adapter_name="none",
            base_url=config.base_url,
            model=config.model,
            api_key=None,
            timeout_seconds=float(config.timeout_seconds),
            max_retries=config.max_retries,
            reasoning_budget_factor=self._settings.llm_reasoning_budget_factor,
            version=config.version,
            enabled=False,
            verification_status=config.verification_status,
            last_tested_at=config.last_tested_at,
            last_error_code=config.last_error_code,
            has_api_key=bool(config.secret_ref),
            api_key_mask=config.api_key_mask,
            snapshot=snapshot,
        )

    def _try_environment(self) -> EffectiveLLMConfig | None:
        settings = self._settings
        if settings.llm_provider in {"", "disabled"}:
            return None
        if not (settings.llm_api_key and settings.llm_base_url and settings.llm_model):
            return None
        try:
            provider = parse_provider(settings.llm_provider)
        except Exception:
            provider = None
            adapter = settings.llm_provider
        else:
            adapter = ADAPTER_NAMES[provider]
        label = PROVIDER_LABELS.get(provider, settings.llm_provider) if provider else settings.llm_provider
        snapshot = LLMConfigSnapshot(
            provider=provider.value if provider else settings.llm_provider,
            provider_label=str(label),
            model=settings.llm_model,
            base_url=settings.llm_base_url,
            source=LLMConfigSource.ENVIRONMENT.value,
            version=0,
            timeout_seconds=int(settings.llm_timeout_seconds),
            max_retries=int(settings.llm_max_retries),
        )
        return EffectiveLLMConfig(
            source=LLMConfigSource.ENVIRONMENT,
            provider=provider,
            adapter_name=adapter,
            base_url=settings.llm_base_url,
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            timeout_seconds=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
            reasoning_budget_factor=settings.llm_reasoning_budget_factor,
            version=0,
            enabled=True,
            verification_status="valid",
            last_tested_at=None,
            last_error_code=None,
            has_api_key=True,
            api_key_mask=mask_api_key(settings.llm_api_key),
            snapshot=snapshot,
        )

    def _offline(self) -> EffectiveLLMConfig:
        snapshot = LLMConfigSnapshot(
            provider="offline",
            provider_label="离线演示",
            model="offline-deterministic",
            base_url="",
            source=LLMConfigSource.OFFLINE.value,
            version=0,
            timeout_seconds=int(self._settings.llm_timeout_seconds),
            max_retries=int(self._settings.llm_max_retries),
        )
        return EffectiveLLMConfig(
            source=LLMConfigSource.OFFLINE,
            provider=None,
            adapter_name="disabled",
            base_url="",
            model="offline-deterministic",
            api_key=None,
            timeout_seconds=self._settings.llm_timeout_seconds,
            max_retries=self._settings.llm_max_retries,
            reasoning_budget_factor=self._settings.llm_reasoning_budget_factor,
            version=0,
            enabled=True,
            verification_status="valid",
            last_tested_at=None,
            last_error_code=None,
            has_api_key=False,
            api_key_mask=None,
            snapshot=snapshot,
        )

    def _none(self) -> EffectiveLLMConfig:
        snapshot = LLMConfigSnapshot(
            provider="",
            provider_label="",
            model="",
            base_url="",
            source=LLMConfigSource.NONE.value,
            version=0,
            timeout_seconds=int(self._settings.llm_timeout_seconds),
            max_retries=int(self._settings.llm_max_retries),
        )
        return EffectiveLLMConfig(
            source=LLMConfigSource.NONE,
            provider=None,
            adapter_name="none",
            base_url="",
            model="",
            api_key=None,
            timeout_seconds=self._settings.llm_timeout_seconds,
            max_retries=self._settings.llm_max_retries,
            reasoning_budget_factor=self._settings.llm_reasoning_budget_factor,
            version=0,
            enabled=False,
            verification_status="unverified",
            last_tested_at=None,
            last_error_code=None,
            has_api_key=False,
            api_key_mask=None,
            snapshot=snapshot,
        )


def empty_preset_provider() -> LLMProvider:
    return LLMProvider.DEEPSEEK


def default_fields(provider: LLMProvider) -> dict[str, str]:
    values = PROVIDER_PRESETS[provider]
    return {"base_url": values["base_url"], "model": values["model"]}

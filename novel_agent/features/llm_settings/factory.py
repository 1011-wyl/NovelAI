from __future__ import annotations

from typing import Any

from novel_agent.features.llm_settings.errors import LLMSettingsError
from novel_agent.features.llm_settings.models import EffectiveLLMConfig, LLMConfigSource
from novel_agent.integrations.factories import _build_llm_gateway_from_values
from novel_agent.integrations.http_transport import Transport
from novel_agent.ports import LLMGateway
from novel_agent.ports.telemetry import LLMCallSink, LLMUsageSink


class LLMClientFactory:
    """Single production factory for provider adapters."""

    def __init__(
        self,
        *,
        reasoning_budget_factor: float = 3.0,
        on_call: LLMCallSink | None = None,
        on_usage: LLMUsageSink | None = None,
        transport: Transport | None = None,
    ) -> None:
        self._reasoning_budget_factor = reasoning_budget_factor
        self._on_call = on_call
        self._on_usage = on_usage
        self._transport = transport
        self._generation = 0

    def invalidate(self) -> None:
        self._generation += 1

    def create(self, config: EffectiveLLMConfig) -> LLMGateway:
        return self._build(config)

    def _build(self, config: EffectiveLLMConfig) -> LLMGateway:
        if config.source is LLMConfigSource.NONE or not config.enabled:
            from novel_agent.features.llm_settings.unconfigured import UnconfiguredLLMGateway

            message = "大模型已停用，请在设置中保存并启用后再试" if not config.enabled and config.source is not LLMConfigSource.NONE else "尚未配置大模型服务"
            return UnconfiguredLLMGateway(message=message)
        mode = "offline" if config.source is LLMConfigSource.OFFLINE else "online"
        kwargs: dict[str, Any] = {
            "api_key": config.api_key,
            "base_url": config.base_url,
            "model": config.model,
            "timeout_seconds": config.timeout_seconds,
            "max_retries": config.max_retries,
            "reasoning_budget_factor": self._reasoning_budget_factor,
            "on_call": self._on_call,
            "on_usage": self._on_usage,
        }
        gateway = _build_llm_gateway_from_values(mode, config.adapter_name, **kwargs)
        if self._transport is not None and hasattr(gateway, "transport"):
            gateway.transport = self._transport
        return gateway


def require_configured(config: EffectiveLLMConfig) -> None:
    if config.source is LLMConfigSource.NONE or not config.enabled:
        raise LLMSettingsError(
            "LLM_NOT_CONFIGURED",
            "大模型已停用，请在设置中保存并启用后再试" if not config.enabled and config.source is not LLMConfigSource.NONE else "尚未配置大模型服务",
        )

"""Settings-driven provider factories.

Provider selection lives here once. adapters.py wrappers and bootstrap both
delegate to the private *_from_values helpers / public Settings builders.
"""

from __future__ import annotations

from novel_agent.integrations.embedding.disabled import DisabledEmbeddingGateway
from novel_agent.integrations.errors import APIConfigurationRequired
from novel_agent.integrations.llm.disabled import DisabledRemoteGateway
from novel_agent.integrations.llm.offline import OfflineLLMGateway
from novel_agent.integrations.publishing.fanqie import FanqiePublisherAdapter
from novel_agent.integrations.publishing.mock import MockPublisher
from novel_agent.integrations.search.disabled import DisabledSearchAdapter
from novel_agent.ports import EmbeddingGateway, LLMGateway, PublisherAdapter, SearchAdapter
from novel_agent.ports.telemetry import LLMCallSink, LLMUsageSink
from novel_agent.config import Settings


_OPENAI_COMPATIBLE_LLM_PROVIDERS = frozenset(
    {"deepseek", "openai-compatible", "dashscope", "qwen"}
)


def _build_llm_gateway_from_values(
    mode: str,
    provider: str,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    timeout_seconds: float = 120.0,
    max_retries: int = 2,
    reasoning_budget_factor: float = 3.0,
    on_call: LLMCallSink | None = None,
    on_usage: LLMUsageSink | None = None,
) -> LLMGateway:
    if mode == "offline" or provider == "disabled":
        return OfflineLLMGateway()
    if provider in _OPENAI_COMPATIBLE_LLM_PROVIDERS:
        from novel_agent.integrations.llm.deepseek import DeepSeekLLMGateway

        default_url = "https://api.deepseek.com"
        default_model = "deepseek-v4-pro"
        if provider in {"dashscope", "qwen"}:
            default_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
            default_model = "qwen3.7-plus"
        elif provider == "openai-compatible":
            default_url = ""
            default_model = ""

        return DeepSeekLLMGateway(
            api_key=api_key or "",
            base_url=base_url or default_url,
            model=model or default_model,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            reasoning_budget_factor=reasoning_budget_factor,
            provider_name=provider,
            on_call=on_call,
            on_usage=on_usage,
        )
    return DisabledRemoteGateway(provider=provider)


def _build_search_adapter_from_values(
    mode: str,
    provider: str,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    timeout_seconds: float = 30.0,
    max_results: int = 3,
) -> SearchAdapter:
    if mode == "offline" or provider == "disabled":
        return DisabledSearchAdapter()
    if provider == "tavily":
        from novel_agent.integrations.search.tavily import TavilySearchAdapter

        return TavilySearchAdapter(
            api_key=api_key or "",
            base_url=base_url or "https://api.tavily.com",
            timeout_seconds=timeout_seconds,
            max_results=max_results,
        )
    raise APIConfigurationRequired(f"不支持的搜索供应商：{provider}")


def _build_embedding_gateway_from_values(
    mode: str,
    provider: str,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    timeout_seconds: float = 60.0,
) -> EmbeddingGateway:
    if mode == "offline" or provider == "disabled":
        return DisabledEmbeddingGateway()
    if provider in {"siliconflow", "openai-compatible"}:
        from novel_agent.integrations.embedding.openai_compatible import (
            OpenAICompatibleEmbeddingGateway,
        )

        default_url = "https://api.siliconflow.cn/v1" if provider == "siliconflow" else ""
        return OpenAICompatibleEmbeddingGateway(
            provider=provider,
            api_key=api_key or "",
            base_url=base_url or default_url,
            model=model or "BAAI/bge-m3",
            timeout_seconds=timeout_seconds,
        )
    raise APIConfigurationRequired(f"不支持的 Embedding 供应商：{provider}")


def _build_publisher_from_values(
    provider: str,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    platform_book_id: str | None = None,
) -> PublisherAdapter:
    if provider == "mock":
        return MockPublisher()
    if provider == "fanqie":
        return FanqiePublisherAdapter(
            api_key=api_key or "",
            base_url=base_url or "",
            platform_book_id=platform_book_id or "",
        )
    raise APIConfigurationRequired(f"不支持的发布供应商：{provider}")


def build_llm_gateway(
    settings: Settings,
    *,
    on_call: LLMCallSink | None = None,
    on_usage: LLMUsageSink | None = None,
) -> LLMGateway:
    return _build_llm_gateway_from_values(
        settings.mode,
        settings.llm_provider,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        timeout_seconds=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
        reasoning_budget_factor=settings.llm_reasoning_budget_factor,
        on_call=on_call,
        on_usage=on_usage,
    )


def build_search_adapter(settings: Settings) -> SearchAdapter:
    return _build_search_adapter_from_values(
        settings.mode,
        settings.search_provider,
        api_key=settings.search_api_key,
        base_url=settings.search_base_url,
        timeout_seconds=settings.search_timeout_seconds,
        max_results=settings.search_max_results,
    )


def build_embedding_gateway(settings: Settings) -> EmbeddingGateway:
    return _build_embedding_gateway_from_values(
        settings.mode,
        settings.embedding_provider,
        api_key=settings.embedding_api_key,
        base_url=settings.embedding_base_url,
        model=settings.embedding_model,
        timeout_seconds=settings.embedding_timeout_seconds,
    )


def build_publisher(settings: Settings) -> PublisherAdapter:
    return _build_publisher_from_values(
        settings.publisher_provider,
        api_key=settings.publisher_api_key,
        base_url=settings.publisher_base_url,
    )

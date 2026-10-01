from __future__ import annotations

from novel_agent.integrations.embedding.disabled import DisabledEmbeddingGateway
from novel_agent.integrations.errors import APIConfigurationRequired
from novel_agent.integrations.factories import (
    _build_embedding_gateway_from_values,
    _build_llm_gateway_from_values,
    _build_search_adapter_from_values,
)
from novel_agent.integrations.llm.disabled import DisabledRemoteGateway
from novel_agent.integrations.llm.offline import OfflineLLMGateway
from novel_agent.integrations.publishing.mock import MockPublisher
from novel_agent.integrations.search.disabled import DisabledSearchAdapter
from novel_agent.ports import (
    EmbeddingGateway,
    LLMCallSink,
    LLMGateway,
    LLMUsageSink,
    PublisherAdapter,
    SearchAdapter,
)

# Compatibility re-exports: Ports live in novel_agent.ports; local/disabled/mock
# implementations and shared errors live in novel_agent.integrations.*; old imports keep working.
__all__ = [
    "APIConfigurationRequired",
    "DisabledEmbeddingGateway",
    "DisabledRemoteGateway",
    "DisabledSearchAdapter",
    "EmbeddingGateway",
    "LLMCallSink",
    "LLMGateway",
    "LLMUsageSink",
    "MockPublisher",
    "OfflineLLMGateway",
    "PublisherAdapter",
    "SearchAdapter",
    "build_embedding_gateway",
    "build_gateway",
    "build_search_adapter",
]


def build_gateway(
    mode: str,
    provider: str,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    timeout_seconds: float = 120.0,
    max_retries: int = 2,
    reasoning_budget_factor: float = 3.0,
) -> LLMGateway:
    return _build_llm_gateway_from_values(
        mode,
        provider,
        api_key=api_key,
        base_url=base_url,
        model=model,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        reasoning_budget_factor=reasoning_budget_factor,
    )


def build_search_adapter(
    mode: str,
    provider: str,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    timeout_seconds: float = 30.0,
    max_results: int = 3,
) -> SearchAdapter:
    return _build_search_adapter_from_values(
        mode,
        provider,
        api_key=api_key,
        base_url=base_url,
        timeout_seconds=timeout_seconds,
        max_results=max_results,
    )


def build_embedding_gateway(
    mode: str,
    provider: str,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    timeout_seconds: float = 60.0,
) -> EmbeddingGateway:
    return _build_embedding_gateway_from_values(
        mode,
        provider,
        api_key=api_key,
        base_url=base_url,
        model=model,
        timeout_seconds=timeout_seconds,
    )

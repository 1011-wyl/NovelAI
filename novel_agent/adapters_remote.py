"""Remote provider adapters compatibility facade.

Implementations live under novel_agent.integrations.*; this module re-exports
the historical public names used by tests and older imports.
"""

from __future__ import annotations

from novel_agent.integrations.embedding.openai_compatible import (
    OpenAICompatibleEmbeddingGateway,
)
from novel_agent.integrations.errors import APIConfigurationRequired
from novel_agent.integrations.http_transport import Transport, _urllib_transport
from novel_agent.integrations.llm.deepseek import DeepSeekLLMGateway, OpenAICompatibleLLMGateway
from novel_agent.integrations.llm.errors import (
    LLMAuthenticationError,
    LLMProviderError,
    LLMRateLimitError,
    LLMResponseError,
    LLMTimeoutError,
)
from novel_agent.integrations.llm.json_util import _compact_json, _tail
from novel_agent.integrations.publishing.fanqie import FanqiePublisherAdapter
from novel_agent.integrations.search.tavily import (
    RemoteSearchAdapter,
    TavilySearchAdapter,
)

__all__ = [
    "APIConfigurationRequired",
    "DeepSeekLLMGateway",
    "FanqiePublisherAdapter",
    "LLMAuthenticationError",
    "LLMProviderError",
    "LLMRateLimitError",
    "LLMResponseError",
    "LLMTimeoutError",
    "OpenAICompatibleEmbeddingGateway",
    "OpenAICompatibleLLMGateway",
    "RemoteSearchAdapter",
    "TavilySearchAdapter",
    "Transport",
    "_compact_json",
    "_tail",
    "_urllib_transport",
]

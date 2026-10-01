"""Stable capability ports for external integrations.

Business layers should depend on these abstractions, not concrete Providers.
"""

from __future__ import annotations

from .embedding import EmbeddingGateway
from .llm import LLMGateway
from .publishing import PublisherAdapter
from .search import SearchAdapter
from .telemetry import LLMCallSink, LLMUsageSink

__all__ = [
    "EmbeddingGateway",
    "LLMCallSink",
    "LLMGateway",
    "LLMUsageSink",
    "PublisherAdapter",
    "SearchAdapter",
]

"""Remote LLM / provider failure taxonomy.

These exceptions are also reused by search and embedding adapters today;
keep the class identity stable for API mapping and isinstance checks.
"""

from __future__ import annotations


class LLMProviderError(RuntimeError):
    """Base error for a remote model provider failure."""


class LLMAuthenticationError(LLMProviderError):
    pass


class LLMRateLimitError(LLMProviderError):
    pass


class LLMTimeoutError(LLMProviderError):
    pass


class LLMResponseError(LLMProviderError):
    pass

from __future__ import annotations

import threading
from typing import Any

from novel_agent.features.llm_settings.factory import LLMClientFactory
from novel_agent.features.llm_settings.models import EffectiveLLMConfig, LLMConfigSnapshot
from novel_agent.features.llm_settings.resolver import EffectiveLLMConfigResolver
from novel_agent.ports import LLMGateway


class SnapshotLLMGateway:
    """Resolves a client at task start and keeps it for the current thread."""

    def __init__(self, resolver: EffectiveLLMConfigResolver, factory: LLMClientFactory) -> None:
        self._resolver = resolver
        self._factory = factory
        self._local = threading.local()

    def begin_task(self) -> LLMConfigSnapshot:
        config = self._resolver.resolve()
        client = self._factory.create(config)
        self._local.config = config
        self._local.client = client
        return config.snapshot

    def invalidate(self) -> None:
        self._factory.invalidate()

    def current_snapshot(self) -> LLMConfigSnapshot:
        config = getattr(self._local, "config", None)
        if config is None:
            return self.begin_task()
        return config.snapshot

    def task_client(self) -> LLMGateway:
        return self._inner()

    @property
    def name(self) -> str:
        return getattr(self._inner(), "name", "llm")

    def usage_summary(self) -> dict[str, Any]:
        inner = self._inner()
        if hasattr(inner, "usage_summary"):
            return inner.usage_summary()
        return {"model": self.name, "request_count": 0}

    def _inner(self) -> LLMGateway:
        client = getattr(self._local, "client", None)
        if client is None:
            self.begin_task()
            client = self._local.client
        return client

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner(), name)

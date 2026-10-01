"""OpenAI-compatible /embeddings client (SiliconFlow and similar)."""

from __future__ import annotations

import socket
import urllib.error
from dataclasses import dataclass, field

from novel_agent.integrations.errors import APIConfigurationRequired
from novel_agent.integrations.http_transport import Transport, _urllib_transport
from novel_agent.integrations.llm.errors import (
    LLMAuthenticationError,
    LLMProviderError,
    LLMRateLimitError,
    LLMResponseError,
    LLMTimeoutError,
)


@dataclass(slots=True)
class OpenAICompatibleEmbeddingGateway:
    """Provider-neutral /embeddings client; defaults are suitable for SiliconFlow."""

    provider: str
    api_key: str
    base_url: str
    model: str = "BAAI/bge-m3"
    timeout_seconds: float = 60.0
    transport: Transport = _urllib_transport
    name: str = field(init=False)
    enabled: bool = field(default=True, init=False)

    def __post_init__(self) -> None:
        if not self.api_key.strip():
            raise APIConfigurationRequired("缺少 Embedding API Key，请填写 EMBEDDING_API_KEY")
        if not self.base_url.startswith("https://"):
            raise APIConfigurationRequired("EMBEDDING_BASE_URL 必须使用 HTTPS")
        if not self.model.strip():
            raise APIConfigurationRequired("缺少 EMBEDDING_MODEL")
        self.base_url = self.base_url.rstrip("/")
        self.name = f"{self.provider}:{self.model}"

    def embed(self, texts: list[str]) -> list[list[float]]:
        inputs = [text.strip() for text in texts if text and text.strip()]
        if not inputs:
            return []
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "NovelAgent/0.1",
        }
        try:
            response = self.transport(
                f"{self.base_url}/embeddings",
                headers,
                {"model": self.model, "input": inputs, "encoding_format": "float"},
                self.timeout_seconds,
            )
        except urllib.error.HTTPError as exc:
            if exc.code in {401, 403}:
                raise LLMAuthenticationError("Embedding 密钥无效或没有模型权限") from exc
            if exc.code == 429:
                raise LLMRateLimitError("Embedding 请求达到频率或额度限制") from exc
            raise LLMProviderError(f"Embedding HTTP 请求失败：{exc.code}") from exc
        except (TimeoutError, socket.timeout) as exc:
            raise LLMTimeoutError("Embedding 请求超时") from exc
        except urllib.error.URLError as exc:
            raise LLMProviderError("无法连接 Embedding API") from exc
        data = response.get("data")
        if not isinstance(data, list) or len(data) != len(inputs):
            raise LLMResponseError("Embedding 响应数量与输入不一致")
        ordered = sorted(data, key=lambda item: int(item.get("index", 0)))
        vectors: list[list[float]] = []
        dimension: int | None = None
        for item in ordered:
            vector = item.get("embedding") if isinstance(item, dict) else None
            if not isinstance(vector, list) or not vector:
                raise LLMResponseError("Embedding 响应缺少有效向量")
            parsed = [float(value) for value in vector]
            dimension = dimension or len(parsed)
            if len(parsed) != dimension:
                raise LLMResponseError("Embedding 响应向量维度不一致")
            vectors.append(parsed)
        return vectors

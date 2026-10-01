"""Shared urllib JSON POST transport for remote providers.

Used by DeepSeek, Tavily, and OpenAI-compatible Embedding gateways.
"""

from __future__ import annotations

import json
import urllib.request
from typing import Any, Callable

from novel_agent.integrations.llm.errors import LLMResponseError

Transport = Callable[[str, dict[str, str], dict[str, Any], float], dict[str, Any]]


def _urllib_transport(
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout: float,
) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8")
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise LLMResponseError("远程接口返回的顶层数据不是 JSON 对象")
    return parsed

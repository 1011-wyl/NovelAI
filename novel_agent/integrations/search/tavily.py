"""Tavily search adapter and its minimal RemoteSearchAdapter base.

RemoteSearchAdapter is only used by Tavily today, so both live here rather
than a separate unused remote.py module.
"""

from __future__ import annotations

import re
import socket
import urllib.error
import urllib.parse
from dataclasses import dataclass, field
from typing import Any

from novel_agent.integrations.errors import APIConfigurationRequired
from novel_agent.integrations.http_transport import Transport, _urllib_transport
from novel_agent.integrations.llm.errors import (
    LLMAuthenticationError,
    LLMProviderError,
    LLMRateLimitError,
    LLMResponseError,
    LLMTimeoutError,
)


class RemoteSearchAdapter:
    enabled = False

    def research(self, questions: list[str]) -> list[dict[str, Any]]:
        raise NotImplementedError


@dataclass(slots=True)
class TavilySearchAdapter(RemoteSearchAdapter):
    """Searches the web and reads cleaned page content through Tavily."""

    api_key: str
    base_url: str = "https://api.tavily.com"
    timeout_seconds: float = 30.0
    max_results: int = 3
    transport: Transport = _urllib_transport
    name: str = field(default="tavily", init=False)
    enabled: bool = field(default=True, init=False)

    def __post_init__(self) -> None:
        if not self.api_key.strip():
            raise APIConfigurationRequired("缺少 Tavily API Key，请填写 SEARCH_API_KEY")
        if not self.base_url.startswith("https://"):
            raise APIConfigurationRequired("SEARCH_BASE_URL 必须使用 HTTPS")
        self.base_url = self.base_url.rstrip("/")
        self.max_results = max(1, min(int(self.max_results), 5))

    def research(self, questions: list[str]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "NovelAgent/0.1",
        }
        for question in [item.strip() for item in questions if item.strip()][:5]:
            response = self._post(
                "/search",
                headers,
                {
                    "query": question,
                    "search_depth": "basic",
                    "max_results": self.max_results,
                    "include_answer": False,
                    "include_raw_content": "text",
                    "include_images": False,
                },
            )
            results = response.get("results")
            if not isinstance(results, list):
                raise LLMResponseError("Tavily 响应缺少 results 数组")
            missing_urls = [
                str(item.get("url", ""))
                for item in results
                if isinstance(item, dict) and item.get("url") and not item.get("raw_content")
            ]
            extracted: dict[str, str] = {}
            if missing_urls:
                extract_response = self._post(
                    "/extract",
                    headers,
                    {"urls": missing_urls, "extract_depth": "basic", "format": "text"},
                )
                for item in extract_response.get("results", []):
                    if isinstance(item, dict) and item.get("url"):
                        extracted[str(item["url"])] = str(item.get("raw_content", ""))
            question_rows: list[dict[str, Any]] = []
            for item in results:
                if not isinstance(item, dict) or not item.get("url"):
                    continue
                url = str(item["url"])
                domain = urllib.parse.urlparse(url).netloc.lower().removeprefix("www.")
                raw = str(item.get("raw_content") or extracted.get(url) or item.get("content") or "")
                content = self._clean_content(raw)[:4000]
                if not content:
                    continue
                provider_score = float(item.get("score") or 0.0)
                question_rows.append(
                    {
                        "query": question,
                        "title": str(item.get("title") or domain or "未命名来源")[:300],
                        "url": url,
                        "domain": domain,
                        "reliability": self._reliability(domain, provider_score),
                        "excerpt": content[:1200],
                        "fact": content[:1200],
                        "content": content,
                        "published_at": item.get("published_date"),
                    }
                )
            domains = {row["domain"] for row in question_rows if row["domain"]}
            for row in question_rows:
                row["verified"] = len(domains) >= 2
                row["verification_notes"] = (
                    f"同一问题获得 {len(domains)} 个独立域名来源，可交叉核验"
                    if len(domains) >= 2
                    else "仅有单一域名来源，正文应采用保守表述"
                )
            normalized.extend(question_rows)
        return normalized

    def _post(
        self, path: str, headers: dict[str, str], payload: dict[str, Any]
    ) -> dict[str, Any]:
        try:
            return self.transport(
                f"{self.base_url}{path}", headers, payload, self.timeout_seconds
            )
        except urllib.error.HTTPError as exc:
            if exc.code in {401, 403}:
                raise LLMAuthenticationError("Tavily 密钥无效或没有接口权限") from exc
            if exc.code == 429:
                raise LLMRateLimitError("Tavily 达到频率或额度限制") from exc
            raise LLMProviderError(f"Tavily HTTP 请求失败：{exc.code}") from exc
        except (TimeoutError, socket.timeout) as exc:
            raise LLMTimeoutError("Tavily 请求超时") from exc
        except urllib.error.URLError as exc:
            raise LLMProviderError("无法连接 Tavily API") from exc

    @staticmethod
    def _clean_content(content: str) -> str:
        content = content.replace("\x00", " ")
        content = re.sub(r"```.*?```", " ", content, flags=re.DOTALL)
        content = re.sub(r"\s+", " ", content)
        return content.strip()

    @staticmethod
    def _reliability(domain: str, provider_score: float) -> float:
        authority = 0.58
        if domain.endswith((".gov", ".gov.cn", ".edu", ".edu.cn")):
            authority = 0.95
        elif domain.endswith((".org", ".org.cn")):
            authority = 0.78
        elif domain in {"wikipedia.org", "baike.baidu.com"}:
            authority = 0.62
        score = max(0.0, min(provider_score, 1.0))
        return round(authority * 0.7 + score * 0.3, 3)

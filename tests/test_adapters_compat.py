"""Characterization tests for External Integrations / Provider Adapters split.

Phase 0 freezes old import paths, factory defaults, exception hierarchy,
constructor signatures, and telemetry callback semantics before any move.
Phase 1 adds ports vs adapters identity checks.
"""

from __future__ import annotations

import inspect
import unittest
import urllib.error

from novel_agent.adapters import (
    APIConfigurationRequired,
    DisabledEmbeddingGateway,
    DisabledRemoteGateway,
    DisabledSearchAdapter,
    MockPublisher,
    OfflineLLMGateway,
    build_embedding_gateway,
    build_gateway,
    build_search_adapter,
)
from novel_agent.adapters_remote import (
    DeepSeekLLMGateway,
    FanqiePublisherAdapter,
    LLMAuthenticationError,
    LLMProviderError,
    LLMRateLimitError,
    LLMResponseError,
    LLMTimeoutError,
    OpenAICompatibleEmbeddingGateway,
    TavilySearchAdapter,
)
from novel_agent.models import ChapterPlan, CreativeBrief, NovelCreateRequest
from novel_agent.ports import (
    EmbeddingGateway as PortsEmbeddingGateway,
    LLMCallSink,
    LLMGateway as PortsLLMGateway,
    LLMUsageSink,
    PublisherAdapter as PortsPublisherAdapter,
    SearchAdapter as PortsSearchAdapter,
)
from tests.test_deepseek_gateway import (
    RecordingTransport,
    brief_payload,
    completion,
    plan_payload,
)


def _usage_completion(content: str = "完整正文") -> dict:
    payload = completion(content)
    payload["model"] = "deepseek-v4-pro"
    payload["usage"] = {
        "prompt_tokens": 11,
        "completion_tokens": 7,
        "total_tokens": 18,
        "prompt_cache_hit_tokens": 2,
    }
    return payload


class _DeepSeekHelpers(unittest.TestCase):
    def request(self) -> NovelCreateRequest:
        return NovelCreateRequest(
            genre="末世",
            experiences=["爽文"],
            elements=["囤货", "经营建设"],
            protagonist_tags=["普通人成长"],
            idea="仓储管理员依靠有限资源建立社区。",
            exclude=["无限空间"],
            chapter_target_chars=1200,
        )

    def gateway(self, transport) -> DeepSeekLLMGateway:
        return DeepSeekLLMGateway(
            api_key="test-key",
            transport=transport,
            sleep=lambda _: None,
        )

    def write_once(self, gateway: DeepSeekLLMGateway) -> str:
        return gateway.write_chapter(
            self.request(),
            CreativeBrief.model_validate(brief_payload()),
            ChapterPlan.model_validate(plan_payload()),
            "林川",
            [],
        )


class AdaptersImportSmokeTests(unittest.TestCase):
    def test_old_adapters_path_exports_core_symbols(self) -> None:
        from novel_agent import adapters

        for name in (
            "APIConfigurationRequired",
            "LLMGateway",
            "SearchAdapter",
            "EmbeddingGateway",
            "PublisherAdapter",
            "DisabledSearchAdapter",
            "DisabledEmbeddingGateway",
            "MockPublisher",
            "DisabledRemoteGateway",
            "OfflineLLMGateway",
            "build_gateway",
            "build_search_adapter",
            "build_embedding_gateway",
        ):
            self.assertTrue(hasattr(adapters, name), name)

    def test_old_adapters_remote_path_exports_providers(self) -> None:
        from novel_agent import adapters_remote

        for name in (
            "LLMProviderError",
            "LLMAuthenticationError",
            "LLMRateLimitError",
            "LLMTimeoutError",
            "LLMResponseError",
            "DeepSeekLLMGateway",
            "TavilySearchAdapter",
            "OpenAICompatibleEmbeddingGateway",
            "FanqiePublisherAdapter",
        ):
            self.assertTrue(hasattr(adapters_remote, name), name)


class PortIdentityTests(unittest.TestCase):
    def test_ports_and_adapters_export_same_protocol_objects(self) -> None:
        from novel_agent.adapters import (
            EmbeddingGateway as AdaptersEmbeddingGateway,
            LLMGateway as AdaptersLLMGateway,
            PublisherAdapter as AdaptersPublisherAdapter,
            SearchAdapter as AdaptersSearchAdapter,
        )

        self.assertIs(AdaptersLLMGateway, PortsLLMGateway)
        self.assertIs(AdaptersSearchAdapter, PortsSearchAdapter)
        self.assertIs(AdaptersEmbeddingGateway, PortsEmbeddingGateway)
        self.assertIs(AdaptersPublisherAdapter, PortsPublisherAdapter)

    def test_telemetry_sink_types_are_callable_protocols(self) -> None:
        def sink(**payload: object) -> None:
            return None

        self.assertTrue(isinstance(sink, LLMCallSink))
        self.assertTrue(isinstance(sink, LLMUsageSink))

    def test_business_modules_import_ports_not_adapter_protocols(self) -> None:
        import novel_agent.service as service_mod
        import novel_agent.workflow as workflow_mod

        self.assertIs(service_mod.LLMGateway, PortsLLMGateway)
        self.assertIs(service_mod.SearchAdapter, PortsSearchAdapter)
        self.assertIs(service_mod.EmbeddingGateway, PortsEmbeddingGateway)
        self.assertIs(workflow_mod.LLMGateway, PortsLLMGateway)
        self.assertIs(workflow_mod.SearchAdapter, PortsSearchAdapter)
        self.assertIs(workflow_mod.EmbeddingGateway, PortsEmbeddingGateway)


class IntegrationIdentityTests(unittest.TestCase):
    def test_local_implementations_are_single_class_objects(self) -> None:
        from novel_agent.integrations.embedding.disabled import (
            DisabledEmbeddingGateway as NewDisabledEmbeddingGateway,
        )
        from novel_agent.integrations.llm.disabled import (
            DisabledRemoteGateway as NewDisabledRemoteGateway,
        )
        from novel_agent.integrations.llm.offline import (
            OfflineLLMGateway as NewOfflineLLMGateway,
        )
        from novel_agent.integrations.publishing.mock import MockPublisher as NewMockPublisher
        from novel_agent.integrations.search.disabled import (
            DisabledSearchAdapter as NewDisabledSearchAdapter,
        )

        self.assertIs(OfflineLLMGateway, NewOfflineLLMGateway)
        self.assertIs(DisabledRemoteGateway, NewDisabledRemoteGateway)
        self.assertIs(DisabledSearchAdapter, NewDisabledSearchAdapter)
        self.assertIs(DisabledEmbeddingGateway, NewDisabledEmbeddingGateway)
        self.assertIs(MockPublisher, NewMockPublisher)
        self.assertEqual(
            DisabledRemoteGateway.__module__,
            "novel_agent.integrations.llm.disabled",
        )

    def test_error_and_transport_identities(self) -> None:
        from novel_agent.adapters import APIConfigurationRequired as OldConfigError
        from novel_agent.adapters_remote import (
            FanqiePublisherAdapter as OldFanqie,
            LLMAuthenticationError as OldAuth,
            LLMProviderError as OldProvider,
            LLMRateLimitError as OldRate,
            LLMResponseError as OldResponse,
            LLMTimeoutError as OldTimeout,
            OpenAICompatibleEmbeddingGateway as OldEmbed,
            RemoteSearchAdapter as OldRemoteSearch,
            TavilySearchAdapter as OldTavily,
            _compact_json as OldCompact,
            _tail as OldTail,
            _urllib_transport as OldTransport,
        )
        from novel_agent.integrations.embedding.openai_compatible import (
            OpenAICompatibleEmbeddingGateway as NewEmbed,
        )
        from novel_agent.integrations.errors import APIConfigurationRequired as NewConfigError
        from novel_agent.integrations.http_transport import _urllib_transport as NewTransport
        from novel_agent.integrations.llm.errors import (
            LLMAuthenticationError as NewAuth,
            LLMProviderError as NewProvider,
            LLMRateLimitError as NewRate,
            LLMResponseError as NewResponse,
            LLMTimeoutError as NewTimeout,
        )
        from novel_agent.integrations.llm.json_util import (
            _compact_json as NewCompact,
            _tail as NewTail,
        )
        from novel_agent.integrations.publishing.fanqie import FanqiePublisherAdapter as NewFanqie
        from novel_agent.integrations.search.tavily import (
            RemoteSearchAdapter as NewRemoteSearch,
            TavilySearchAdapter as NewTavily,
        )

        self.assertIs(OldConfigError, NewConfigError)
        self.assertIs(OldProvider, NewProvider)
        self.assertIs(OldAuth, NewAuth)
        self.assertIs(OldRate, NewRate)
        self.assertIs(OldTimeout, NewTimeout)
        self.assertIs(OldResponse, NewResponse)
        self.assertIs(OldTransport, NewTransport)
        self.assertIs(OldCompact, NewCompact)
        self.assertIs(OldTail, NewTail)
        self.assertIs(OldRemoteSearch, NewRemoteSearch)
        self.assertIs(OldTavily, NewTavily)
        self.assertIs(OldEmbed, NewEmbed)
        self.assertIs(OldFanqie, NewFanqie)

        from novel_agent.adapters_remote import DeepSeekLLMGateway as OldDeepSeek
        from novel_agent.integrations.llm.deepseek import DeepSeekLLMGateway as NewDeepSeek

        self.assertIs(OldDeepSeek, NewDeepSeek)
        self.assertEqual(NewDeepSeek.__module__, "novel_agent.integrations.llm.deepseek")

    def test_integrations_and_ports_do_not_import_compat_facades(self) -> None:
        import ast
        from pathlib import Path

        roots = [
            Path(__file__).resolve().parents[1] / "novel_agent" / "integrations",
            Path(__file__).resolve().parents[1] / "novel_agent" / "ports",
        ]
        forbidden_prefixes = ("novel_agent.adapters", "novel_agent.adapters_remote")
        offenders: list[str] = []
        for root in roots:
            for path in root.rglob("*.py"):
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
                for node in ast.walk(tree):
                    names: list[str] = []
                    if isinstance(node, ast.Import):
                        names = [alias.name for alias in node.names]
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        names = [node.module]
                    for name in names:
                        if any(
                            name == prefix or name.startswith(prefix + ".")
                            for prefix in forbidden_prefixes
                        ):
                            offenders.append(f"{path}: {name}")
                        if root.name == "ports" and (
                            name == "novel_agent.integrations"
                            or name.startswith("novel_agent.integrations.")
                        ):
                            offenders.append(f"{path}: {name}")
        self.assertEqual(offenders, [])


class LocalImplementationBehaviorTests(unittest.TestCase):
    def test_disabled_search_and_embedding_behavior(self) -> None:
        search = DisabledSearchAdapter()
        self.assertEqual(search.name, "disabled")
        self.assertFalse(search.enabled)
        self.assertEqual(search.research(["q1", "q2"]), [])

        embedding = DisabledEmbeddingGateway()
        self.assertEqual(embedding.name, "disabled")
        self.assertEqual(embedding.model, "disabled")
        self.assertFalse(embedding.enabled)
        self.assertEqual(embedding.embed(["a", "b"]), [])

    def test_mock_publisher_fingerprint(self) -> None:
        import hashlib

        publisher = MockPublisher()
        result = publisher.publish("proj", "chap", "标题", "正文")
        expected = hashlib.sha256(b"proj:chap").hexdigest()[:16]
        self.assertEqual(result, {"status": "MOCK_PUBLISHED", "external_id": f"mock_{expected}"})

    def test_disabled_remote_gateway_message_and_type(self) -> None:
        gateway = DisabledRemoteGateway(provider="acme")
        self.assertEqual(gateway.name, "remote-disabled-until-implemented")
        with self.assertRaises(APIConfigurationRequired) as ctx:
            gateway.create_brief(
                NovelCreateRequest(
                    genre="末世",
                    idea="测试",
                    exclude=[],
                )
            )
        self.assertIn("acme", str(ctx.exception))
        self.assertIn("adapters_remote.py", str(ctx.exception))

    def test_offline_create_brief_is_deterministic(self) -> None:
        request = NovelCreateRequest(
            genre="末世",
            experiences=["爽文"],
            elements=["囤货"],
            idea="仓储管理员依靠有限资源建立社区。",
            exclude=["无限空间"],
        )
        first = OfflineLLMGateway().create_brief(request)
        second = OfflineLLMGateway().create_brief(request)
        self.assertEqual(first.model_dump(), second.model_dump())
        self.assertEqual(first.protagonist_name, first.protagonist)


class FactoryDefaultCharacterizationTests(unittest.TestCase):
    def test_offline_and_disabled_factories(self) -> None:
        self.assertIsInstance(build_gateway("offline", "deepseek"), OfflineLLMGateway)
        self.assertIsInstance(build_gateway("online", "disabled"), OfflineLLMGateway)
        self.assertIsInstance(build_search_adapter("offline", "tavily"), DisabledSearchAdapter)
        self.assertIsInstance(build_search_adapter("online", "disabled"), DisabledSearchAdapter)
        self.assertIsInstance(
            build_embedding_gateway("offline", "siliconflow"), DisabledEmbeddingGateway
        )
        self.assertIsInstance(
            build_embedding_gateway("online", "disabled"), DisabledEmbeddingGateway
        )

    def test_deepseek_factory_defaults_and_missing_key(self) -> None:
        with self.assertRaises(APIConfigurationRequired):
            build_gateway("online", "deepseek", api_key=None)
        with self.assertRaises(APIConfigurationRequired):
            build_gateway("online", "deepseek", api_key="   ")
        gateway = build_gateway("online", "deepseek", api_key="test-key")
        self.assertIsInstance(gateway, DeepSeekLLMGateway)
        self.assertEqual(gateway.base_url, "https://api.deepseek.com")
        self.assertEqual(gateway.model, "deepseek-v4-pro")
        self.assertEqual(gateway.timeout_seconds, 120.0)
        self.assertEqual(gateway.max_retries, 2)

    def test_tavily_factory_defaults_and_missing_key(self) -> None:
        with self.assertRaises(APIConfigurationRequired):
            build_search_adapter("online", "tavily", api_key=None)
        adapter = build_search_adapter("online", "tavily", api_key="test-key")
        self.assertIsInstance(adapter, TavilySearchAdapter)
        self.assertEqual(adapter.base_url, "https://api.tavily.com")
        self.assertEqual(adapter.timeout_seconds, 30.0)
        self.assertEqual(adapter.max_results, 3)

    def test_embedding_factory_defaults_by_provider(self) -> None:
        with self.assertRaises(APIConfigurationRequired):
            build_embedding_gateway("online", "siliconflow", api_key=None)
        silicon = build_embedding_gateway("online", "siliconflow", api_key="test-key")
        self.assertIsInstance(silicon, OpenAICompatibleEmbeddingGateway)
        self.assertEqual(silicon.base_url, "https://api.siliconflow.cn/v1")
        self.assertEqual(silicon.model, "BAAI/bge-m3")
        with self.assertRaises(APIConfigurationRequired):
            build_embedding_gateway("online", "openai-compatible", api_key="test-key")
        openai_compat = build_embedding_gateway(
            "online",
            "openai-compatible",
            api_key="test-key",
            base_url="https://example.com/v1",
        )
        self.assertEqual(openai_compat.base_url, "https://example.com/v1")
        self.assertEqual(openai_compat.model, "BAAI/bge-m3")

    def test_unsupported_provider_names(self) -> None:
        with self.assertRaises(APIConfigurationRequired):
            build_search_adapter("online", "bing")
        with self.assertRaises(APIConfigurationRequired):
            build_embedding_gateway("online", "unknown-embed")
        gated = build_gateway("online", "unknown-llm")
        self.assertIsInstance(gated, DisabledRemoteGateway)


class ConstructorSignatureCharacterizationTests(unittest.TestCase):
    """Freeze public constructor signatures before Provider file moves."""

    def test_deepseek_signature(self) -> None:
        params = inspect.signature(DeepSeekLLMGateway).parameters
        self.assertEqual(
            list(params),
            [
                "api_key",
                "base_url",
                "model",
                "timeout_seconds",
                "max_retries",
                "reasoning_budget_factor",
                "transport",
                "sleep",
                "on_call",
                "on_usage",
            ],
        )
        self.assertEqual(params["base_url"].default, "https://api.deepseek.com")
        self.assertEqual(params["model"].default, "deepseek-v4-pro")
        self.assertEqual(params["timeout_seconds"].default, 120.0)
        self.assertEqual(params["max_retries"].default, 2)
        self.assertEqual(params["reasoning_budget_factor"].default, 3.0)
        self.assertEqual(params["on_call"].kind, inspect.Parameter.KEYWORD_ONLY)
        self.assertEqual(params["on_usage"].kind, inspect.Parameter.KEYWORD_ONLY)
        self.assertIsNone(params["on_call"].default)
        self.assertIsNone(params["on_usage"].default)

    def test_tavily_signature(self) -> None:
        params = inspect.signature(TavilySearchAdapter).parameters
        self.assertEqual(
            list(params),
            ["api_key", "base_url", "timeout_seconds", "max_results", "transport"],
        )
        self.assertEqual(params["base_url"].default, "https://api.tavily.com")
        self.assertEqual(params["timeout_seconds"].default, 30.0)
        self.assertEqual(params["max_results"].default, 3)

    def test_embedding_signature(self) -> None:
        params = inspect.signature(OpenAICompatibleEmbeddingGateway).parameters
        self.assertEqual(
            list(params),
            ["provider", "api_key", "base_url", "model", "timeout_seconds", "transport"],
        )
        self.assertEqual(params["model"].default, "BAAI/bge-m3")
        self.assertEqual(params["timeout_seconds"].default, 60.0)
        self.assertIs(params["base_url"].default, inspect.Parameter.empty)

    def test_fanqie_remains_gated_on_construction(self) -> None:
        params = inspect.signature(FanqiePublisherAdapter.__init__).parameters
        self.assertEqual(list(params), ["self", "api_key", "base_url", "platform_book_id"])
        with self.assertRaises(APIConfigurationRequired):
            FanqiePublisherAdapter(
                api_key="x",
                base_url="https://example.com",
                platform_book_id="book-1",
            )


class ExceptionHierarchyCharacterizationTests(_DeepSeekHelpers):
    def test_provider_error_tree(self) -> None:
        self.assertTrue(issubclass(LLMAuthenticationError, LLMProviderError))
        self.assertTrue(issubclass(LLMRateLimitError, LLMProviderError))
        self.assertTrue(issubclass(LLMTimeoutError, LLMProviderError))
        self.assertTrue(issubclass(LLMResponseError, LLMProviderError))
        self.assertTrue(issubclass(LLMProviderError, RuntimeError))
        self.assertTrue(issubclass(APIConfigurationRequired, RuntimeError))
        self.assertFalse(issubclass(APIConfigurationRequired, LLMProviderError))

    def test_http_status_mapping_for_deepseek(self) -> None:
        # 401/403 fail immediately; 429/5xx exhaust retries then map.
        cases = [
            (401, LLMAuthenticationError, 1),
            (403, LLMAuthenticationError, 1),
            (429, LLMRateLimitError, 3),
            (500, LLMProviderError, 3),
        ]
        for status, expected, copies in cases:
            with self.subTest(status=status):
                errors = [
                    urllib.error.HTTPError("url", status, "error", None, None)
                    for _ in range(copies)
                ]
                gateway = self.gateway(RecordingTransport(errors))
                with self.assertRaises(expected):
                    self.write_once(gateway)


class TelemetryCallbackCharacterizationTests(_DeepSeekHelpers):
    def test_on_usage_receives_expected_payload_keys(self) -> None:
        gateway = self.gateway(RecordingTransport([_usage_completion()]))
        saved: list[dict] = []
        gateway._on_usage = lambda **payload: saved.append(payload)

        result = self.write_once(gateway)

        self.assertEqual(result, "完整正文")
        self.assertEqual(len(saved), 1)
        payload = saved[0]
        for key in (
            "date",
            "operation",
            "model",
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "retry_count",
            "project_id",
            "chapter_id",
            "run_id",
            "category",
            "provider",
            "status",
            "latency_ms",
            "first_token_ms",
            "cache_tokens",
            "error_type",
            "error_message",
            "error_status_code",
        ):
            self.assertIn(key, payload)
        self.assertEqual(payload["provider"], "deepseek")
        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["prompt_tokens"], 11)
        self.assertEqual(payload["completion_tokens"], 7)
        self.assertEqual(payload["total_tokens"], 18)
        self.assertEqual(payload["cache_tokens"], 2)

    def test_on_call_takes_priority_over_on_usage(self) -> None:
        gateway = self.gateway(RecordingTransport([_usage_completion()]))
        calls: list[str] = []
        gateway._on_call = lambda **payload: calls.append("call")
        gateway._on_usage = lambda **payload: calls.append("usage")
        self.write_once(gateway)
        self.assertEqual(calls, ["call"])

    def test_callback_failure_does_not_fail_main_call(self) -> None:
        gateway = self.gateway(RecordingTransport([_usage_completion()]))

        def boom(**payload: object) -> None:
            raise RuntimeError("telemetry boom")

        gateway._on_usage = boom
        self.assertEqual(self.write_once(gateway), "完整正文")


class OfflineSubclassCompatibilityTests(unittest.TestCase):
    def test_offline_gateway_remains_subclassable(self) -> None:
        class RecordingGateway(OfflineLLMGateway):
            def __init__(self) -> None:
                self.calls = 0

            def write_chapter(self, *args, **kwargs):  # type: ignore[no-untyped-def]
                self.calls += 1
                return super().write_chapter(*args, **kwargs)

        gateway = RecordingGateway()
        self.assertEqual(gateway.name, "offline-deterministic")
        self.assertIsInstance(gateway, OfflineLLMGateway)

        request = NovelCreateRequest(
            genre="末世",
            experiences=["爽文"],
            elements=["囤货"],
            idea="仓储管理员依靠有限资源建立社区。",
            exclude=["无限空间"],
            chapter_target_chars=1200,
        )
        brief = gateway.create_brief(request)
        plan = gateway.plan_chapter(request, brief, 1, [], [])
        content = gateway.write_chapter(request, brief, plan, brief.protagonist_name, [])
        self.assertEqual(gateway.calls, 1)
        self.assertGreaterEqual(len(content), request.chapter_target_chars)


class HttpTransportHelperTests(unittest.TestCase):
    def test_compact_json_and_tail_helpers(self) -> None:
        from novel_agent.integrations.llm.json_util import _compact_json, _tail

        self.assertEqual(_compact_json({"a": 1, "b": [2]}), '{"a":1,"b":[2]}')
        self.assertEqual(_tail("abcdef", 3), "def")
        self.assertEqual(_tail("", 3), "")

    def test_urllib_transport_posts_json_without_real_network(self) -> None:
        import io
        import json
        from unittest.mock import patch

        from novel_agent.integrations.http_transport import _urllib_transport
        from novel_agent.integrations.llm.errors import LLMResponseError

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return json.dumps({"ok": True, "value": 1}).encode("utf-8")

        captured: dict[str, object] = {}

        def fake_urlopen(request, timeout=None):
            captured["url"] = request.full_url
            captured["method"] = request.get_method()
            captured["headers"] = dict(request.headers)
            captured["body"] = request.data
            captured["timeout"] = timeout
            return FakeResponse()

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            result = _urllib_transport(
                "https://example.test/v1",
                {"Authorization": "Bearer secret", "Content-Type": "application/json"},
                {"prompt": "hi"},
                12.5,
            )

        self.assertEqual(result, {"ok": True, "value": 1})
        self.assertEqual(captured["url"], "https://example.test/v1")
        self.assertEqual(captured["method"], "POST")
        self.assertEqual(captured["timeout"], 12.5)
        self.assertEqual(json.loads(captured["body"]), {"prompt": "hi"})
        self.assertNotIn("secret", str(captured["body"]))

        class ListResponse(FakeResponse):
            def read(self):
                return b"[1, 2]"

        with patch("urllib.request.urlopen", return_value=ListResponse()):
            with self.assertRaises(LLMResponseError):
                _urllib_transport("https://example.test/v1", {}, {}, 1.0)

    def test_provider_defaults_use_injected_transport_not_module_global(self) -> None:
        from novel_agent.adapters_remote import DeepSeekLLMGateway

        calls: list[tuple] = []

        def fake_transport(url, headers, payload, timeout):
            calls.append((url, headers, payload, timeout))
            return {
                "choices": [{"finish_reason": "stop", "message": {"content": "正文"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            }

        gateway = DeepSeekLLMGateway(
            api_key="test-key",
            transport=fake_transport,
            sleep=lambda _: None,
        )
        result = gateway.write_chapter(
            NovelCreateRequest(
                genre="末世",
                experiences=["爽文"],
                elements=["囤货"],
                idea="仓储管理员依靠有限资源建立社区。",
                exclude=["无限空间"],
                chapter_target_chars=800,
            ),
            CreativeBrief.model_validate(brief_payload()),
            ChapterPlan.model_validate(plan_payload()),
            "林川",
            [],
        )
        self.assertEqual(result, "正文")
        self.assertEqual(len(calls), 1)
        self.assertTrue(str(calls[0][0]).endswith("/chat/completions"))


class ApiErrorMappingTests(unittest.TestCase):
    def test_new_path_exceptions_map_to_stable_http_codes(self) -> None:
        from http import HTTPStatus

        from novel_agent.api import NovelAgentHandler
        from novel_agent.integrations.errors import APIConfigurationRequired
        from novel_agent.integrations.llm.errors import (
            LLMAuthenticationError,
            LLMProviderError,
            LLMRateLimitError,
            LLMResponseError,
            LLMTimeoutError,
        )

        cases = [
            (APIConfigurationRequired("missing"), HTTPStatus.SERVICE_UNAVAILABLE, "API_NOT_CONFIGURED"),
            (LLMAuthenticationError("auth"), HTTPStatus.BAD_GATEWAY, "LLM_AUTH_ERROR"),
            (LLMRateLimitError("limit"), HTTPStatus.TOO_MANY_REQUESTS, "LLM_RATE_LIMITED"),
            (LLMTimeoutError("timeout"), HTTPStatus.GATEWAY_TIMEOUT, "LLM_TIMEOUT"),
            (LLMResponseError("bad"), HTTPStatus.BAD_GATEWAY, "LLM_RESPONSE_ERROR"),
            (LLMProviderError("other"), HTTPStatus.BAD_GATEWAY, "LLM_PROVIDER_ERROR"),
        ]

        for exc, status, code in cases:
            with self.subTest(error=code):
                captured: dict[str, object] = {}

                class FakeHandler(NovelAgentHandler):
                    def __init__(self) -> None:
                        self.request_version = "HTTP/1.1"
                        self.headers = {}

                    def _send_json(self, payload, status_code):  # type: ignore[no-untyped-def]
                        captured["payload"] = payload
                        captured["status"] = status_code

                    def _cors_headers(self) -> None:
                        return None

                FakeHandler()._handle_error(exc)
                self.assertEqual(captured["status"], status)
                self.assertEqual(captured["payload"]["error"], code)
                self.assertEqual(captured["payload"]["message"], str(exc))


class Phase4ProviderMigrationTests(unittest.TestCase):
    def test_adapters_remote_no_longer_defines_migrated_provider_classes(self) -> None:
        import ast
        from pathlib import Path

        tree = ast.parse(
            (Path(__file__).resolve().parents[1] / "novel_agent" / "adapters_remote.py").read_text(
                encoding="utf-8"
            )
        )
        defined = {
            node.name
            for node in tree.body
            if isinstance(node, ast.ClassDef)
        }
        self.assertNotIn("DeepSeekLLMGateway", defined)
        for name in (
            "RemoteSearchAdapter",
            "TavilySearchAdapter",
            "OpenAICompatibleEmbeddingGateway",
            "FanqiePublisherAdapter",
        ):
            self.assertNotIn(name, defined)

    def test_tavily_request_normalization_and_empty_or_bad_responses(self) -> None:
        from novel_agent.integrations.llm.errors import LLMResponseError
        from novel_agent.integrations.search.tavily import TavilySearchAdapter

        calls: list[tuple] = []

        def transport(url, headers, payload, timeout):
            calls.append((url, headers, payload, timeout))
            if url.endswith("/search"):
                return {
                    "results": [
                        {
                            "title": "官方",
                            "url": "https://a.example.gov.cn/x",
                            "score": 0.9,
                            "raw_content": "正文一",
                        },
                        {
                            "title": "",
                            "url": "https://b.example.edu.cn/y",
                            "score": 0.5,
                            "raw_content": "正文二",
                        },
                    ]
                }
            raise AssertionError("unexpected extract call")

        adapter = TavilySearchAdapter(api_key="key", transport=transport, max_results=2)
        rows = adapter.research([" 安全边界 ", "", "  "])
        self.assertEqual(len(rows), 2)
        self.assertEqual(calls[0][3], 30.0)
        self.assertTrue(calls[0][0].endswith("/search"))
        self.assertEqual(
            calls[0][2],
            {
                "query": "安全边界",
                "search_depth": "basic",
                "max_results": 2,
                "include_answer": False,
                "include_raw_content": "text",
                "include_images": False,
            },
        )
        self.assertTrue(all(row["verified"] for row in rows))
        self.assertEqual(rows[0]["title"], "官方")
        self.assertEqual(rows[1]["title"], "b.example.edu.cn")

        bad = TavilySearchAdapter(
            api_key="key",
            transport=lambda *args: {"results": "nope"},
        )
        with self.assertRaises(LLMResponseError):
            bad.research(["q"])

        empty = TavilySearchAdapter(
            api_key="key",
            transport=lambda *args: {"results": [{"url": "https://x.test", "raw_content": "   "}]},
        )
        self.assertEqual(empty.research(["q"]), [])

    def test_embedding_request_validation_and_errors(self) -> None:
        from novel_agent.integrations.embedding.openai_compatible import (
            OpenAICompatibleEmbeddingGateway,
        )
        from novel_agent.integrations.llm.errors import LLMResponseError

        calls: list[tuple] = []

        def transport(url, headers, payload, timeout):
            calls.append((url, headers, payload, timeout))
            return {
                "data": [
                    {"index": 1, "embedding": [0.0, 1.0]},
                    {"index": 0, "embedding": [1.0, 0.0]},
                ]
            }

        gateway = OpenAICompatibleEmbeddingGateway(
            provider="openai-compatible",
            api_key="key",
            base_url="https://example.com/v1/",
            transport=transport,
        )
        self.assertEqual(gateway.embed([" a ", "", "b"]), [[1.0, 0.0], [0.0, 1.0]])
        self.assertEqual(calls[0][0], "https://example.com/v1/embeddings")
        self.assertEqual(calls[0][2]["model"], "BAAI/bge-m3")
        self.assertEqual(calls[0][2]["input"], ["a", "b"])
        self.assertEqual(calls[0][3], 60.0)
        self.assertEqual(gateway.embed(["", "  "]), [])

        missing = OpenAICompatibleEmbeddingGateway(
            provider="x",
            api_key="key",
            base_url="https://example.com/v1",
            transport=lambda *args: {"data": [{"index": 0}]},
        )
        with self.assertRaises(LLMResponseError):
            missing.embed(["a"])

        mismatch = OpenAICompatibleEmbeddingGateway(
            provider="x",
            api_key="key",
            base_url="https://example.com/v1",
            transport=lambda *args: {"data": []},
        )
        with self.assertRaises(LLMResponseError):
            mismatch.embed(["a"])

    def test_fanqie_gate_on_both_import_paths(self) -> None:
        from novel_agent.adapters_remote import FanqiePublisherAdapter as OldFanqie
        from novel_agent.integrations.publishing.fanqie import FanqiePublisherAdapter as NewFanqie

        for cls in (OldFanqie, NewFanqie):
            with self.assertRaises(APIConfigurationRequired) as ctx:
                cls(api_key="k", base_url="https://example.com", platform_book_id="b1")
            self.assertIn("MockPublisher", str(ctx.exception))
            self.assertIn("安全闸门", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()

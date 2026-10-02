"""Phase 6 factory matrix, wrapper compatibility, and bootstrap telemetry tests."""

from __future__ import annotations

import ast
import inspect
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from novel_agent.adapters import (  # 兼容入口：旧工厂 wrapper 行为回归
    build_embedding_gateway as old_build_embedding,
    build_gateway as old_build_gateway,
    build_search_adapter as old_build_search,
)
from novel_agent.bootstrap import create_context
from novel_agent.config import Settings
from novel_agent.integrations.embedding.disabled import DisabledEmbeddingGateway
from novel_agent.integrations.embedding.openai_compatible import OpenAICompatibleEmbeddingGateway
from novel_agent.integrations.errors import APIConfigurationRequired
from novel_agent.integrations.factories import (
    build_embedding_gateway,
    build_llm_gateway,
    build_publisher,
    build_search_adapter,
)
from novel_agent.integrations.llm.deepseek import DeepSeekLLMGateway
from novel_agent.integrations.llm.disabled import DisabledRemoteGateway
from novel_agent.integrations.llm.offline import OfflineLLMGateway
from novel_agent.integrations.publishing.mock import MockPublisher
from novel_agent.integrations.search.disabled import DisabledSearchAdapter
from novel_agent.integrations.search.tavily import TavilySearchAdapter
from novel_agent.models import ChapterPlan, CreativeBrief, NovelCreateRequest
from tests.test_deepseek_gateway import RecordingTransport, brief_payload, completion, plan_payload


def _settings(**overrides: object) -> Settings:
    base = Settings(
        mode="online",
        database_path=Path("data/test.db"),
        host="127.0.0.1",
        port=8000,
        llm_provider="disabled",
        llm_api_key=None,
        llm_base_url=None,
        llm_model=None,
        llm_timeout_seconds=120.0,
        llm_max_retries=2,
        llm_reasoning_budget_factor=3.0,
        search_provider="disabled",
        search_api_key=None,
        search_base_url=None,
        search_timeout_seconds=30.0,
        search_max_results=3,
        embedding_provider="disabled",
        embedding_api_key=None,
        embedding_base_url=None,
        embedding_model=None,
        embedding_timeout_seconds=60.0,
        semantic_retrieval_limit=6,
        publisher_provider="mock",
        publisher_api_key=None,
        publisher_base_url=None,
        story_skills_enabled=False,
        oh_story_enabled=False,
    )
    return replace(base, **overrides)  # type: ignore[arg-type]


class FactoryMatrixTests(unittest.TestCase):
    def test_llm_matrix(self) -> None:
        self.assertIsInstance(
            build_llm_gateway(_settings(mode="offline", llm_provider="deepseek")),
            OfflineLLMGateway,
        )
        self.assertIsInstance(
            build_llm_gateway(_settings(llm_provider="disabled")),
            OfflineLLMGateway,
        )
        gateway = build_llm_gateway(
            _settings(
                llm_provider="deepseek",
                llm_api_key="test-key",
                llm_base_url="https://api.deepseek.com",
                llm_model="deepseek-v4-pro",
            )
        )
        self.assertIsInstance(gateway, DeepSeekLLMGateway)
        self.assertEqual(gateway.model, "deepseek-v4-pro")
        self.assertEqual(gateway.base_url, "https://api.deepseek.com")
        self.assertEqual(gateway.provider_name, "deepseek")
        qwen = build_llm_gateway(
            _settings(
                llm_provider="dashscope",
                llm_api_key="test-key",
                llm_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                llm_model="qwen3.7-plus",
            )
        )
        self.assertIsInstance(qwen, DeepSeekLLMGateway)
        self.assertEqual(qwen.provider_name, "dashscope")
        self.assertEqual(qwen.model, "qwen3.7-plus")
        self.assertEqual(
            qwen.base_url, "https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        compatible = build_llm_gateway(
            _settings(
                llm_provider="openai-compatible",
                llm_api_key="test-key",
                llm_base_url="https://example.com/v1",
                llm_model="my-model",
            )
        )
        self.assertEqual(compatible.provider_name, "openai-compatible")
        self.assertIsInstance(
            build_llm_gateway(_settings(llm_provider="acme")),
            DisabledRemoteGateway,
        )
        with self.assertRaises(APIConfigurationRequired):
            build_llm_gateway(
                _settings(
                    llm_provider="deepseek",
                    llm_api_key=None,
                    llm_base_url="https://api.deepseek.com",
                    llm_model="deepseek-v4-pro",
                )
            )

    def test_search_matrix(self) -> None:
        self.assertIsInstance(
            build_search_adapter(_settings(mode="offline", search_provider="tavily")),
            DisabledSearchAdapter,
        )
        adapter = build_search_adapter(
            _settings(
                search_provider="tavily",
                search_api_key="key",
                search_base_url="https://api.tavily.com",
            )
        )
        self.assertIsInstance(adapter, TavilySearchAdapter)
        self.assertEqual(adapter.base_url, "https://api.tavily.com")
        with self.assertRaises(APIConfigurationRequired):
            build_search_adapter(_settings(search_provider="bing"))
        with self.assertRaises(APIConfigurationRequired):
            build_search_adapter(
                _settings(
                    search_provider="tavily",
                    search_api_key=None,
                    search_base_url="https://api.tavily.com",
                )
            )

    def test_embedding_matrix(self) -> None:
        self.assertIsInstance(
            build_embedding_gateway(_settings(embedding_provider="disabled")),
            DisabledEmbeddingGateway,
        )
        silicon = build_embedding_gateway(
            _settings(
                embedding_provider="siliconflow",
                embedding_api_key="key",
                embedding_base_url="https://api.siliconflow.cn/v1",
                embedding_model="BAAI/bge-m3",
            )
        )
        self.assertIsInstance(silicon, OpenAICompatibleEmbeddingGateway)
        self.assertEqual(silicon.base_url, "https://api.siliconflow.cn/v1")
        with self.assertRaises(APIConfigurationRequired):
            build_embedding_gateway(
                _settings(
                    embedding_provider="openai-compatible",
                    embedding_api_key="key",
                    embedding_base_url=None,
                    embedding_model="BAAI/bge-m3",
                )
            )
        with self.assertRaises(APIConfigurationRequired):
            build_embedding_gateway(_settings(embedding_provider="unknown"))

    def test_publisher_matrix(self) -> None:
        self.assertIsInstance(build_publisher(_settings(publisher_provider="mock")), MockPublisher)
        with self.assertRaises(APIConfigurationRequired) as ctx:
            build_publisher(_settings(publisher_provider="fanqie", publisher_api_key="k"))
        self.assertIn("安全闸门", str(ctx.exception))
        with self.assertRaises(APIConfigurationRequired):
            build_publisher(_settings(publisher_provider="unknown"))


class OldWrapperCompatibilityTests(unittest.TestCase):
    def test_old_signatures_unchanged(self) -> None:
        self.assertEqual(
            list(inspect.signature(old_build_gateway).parameters),
            [
                "mode",
                "provider",
                "api_key",
                "base_url",
                "model",
                "timeout_seconds",
                "max_retries",
                "reasoning_budget_factor",
            ],
        )
        self.assertEqual(
            list(inspect.signature(old_build_search).parameters),
            ["mode", "provider", "api_key", "base_url", "timeout_seconds", "max_results"],
        )
        self.assertEqual(
            list(inspect.signature(old_build_embedding).parameters),
            ["mode", "provider", "api_key", "base_url", "model", "timeout_seconds"],
        )

    def test_old_and_new_factories_agree(self) -> None:
        self.assertIs(
            type(old_build_gateway("online", "disabled")),
            type(build_llm_gateway(_settings(llm_provider="disabled"))),
        )
        self.assertIs(
            type(old_build_gateway("online", "deepseek", api_key="k")),
            DeepSeekLLMGateway,
        )
        self.assertIs(
            type(old_build_search("online", "tavily", api_key="k")),
            TavilySearchAdapter,
        )
        with self.assertRaises(APIConfigurationRequired) as old_ctx:
            old_build_search("online", "bing")
        with self.assertRaises(APIConfigurationRequired) as new_ctx:
            build_search_adapter(_settings(search_provider="bing"))
        self.assertEqual(str(old_ctx.exception), str(new_ctx.exception))


class BootstrapTelemetryTests(unittest.TestCase):
    def test_bootstrap_source_has_no_private_telemetry_access(self) -> None:
        source = Path("novel_agent/bootstrap.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        offenders: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in {"_on_call", "_on_usage"}:
                offenders.append(node.attr)
            if isinstance(node, ast.Constant) and node.value in {"_on_call", "_on_usage"}:
                offenders.append(str(node.value))
        self.assertEqual(offenders, [])
        self.assertIn("on_call=", source)
        self.assertIn("build_llm_gateway", source)
        self.assertIn("AnalyticsService", source)

    def test_create_context_injects_public_on_call_for_deepseek(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "apps" / "web").mkdir(parents=True)
            (root / "apps" / "web" / "index.html").write_text("<html></html>", encoding="utf-8")
            env = {
                "NOVEL_AGENT_MODE": "online",
                "LLM_PROVIDER": "deepseek",
                "LLM_API_KEY": "test-key",
                "SEARCH_PROVIDER": "disabled",
                "EMBEDDING_PROVIDER": "disabled",
                "PUBLISHER_PROVIDER": "mock",
                "STORY_SKILLS_ENABLED": "false",
                "OH_STORY_ENABLED": "false",
            }
            with patch.dict("os.environ", env, clear=False):
                context = create_context(root=root, database_path=root / "t.db")

            self.assertIsNotNone(context.projects)
            self.assertIsNotNone(context.story_design)
            self.assertIs(context.projects, context.service.projects)
            self.assertIs(context.story_design, context.service.story_design)

            gateway = context.service.gateway
            self.assertIsInstance(gateway, DeepSeekLLMGateway)
            self.assertEqual(
                gateway._on_call.__func__,  # type: ignore[union-attr]
                context.repository.analytics.save_token_usage.__func__,
            )
            self.assertIs(gateway._on_call.__self__, context.repository.analytics)  # type: ignore[union-attr]
            self.assertIsNone(gateway._on_usage)

            recorded: list[dict] = []
            original = gateway._on_call

            def spy(**payload: object) -> None:
                recorded.append(dict(payload))
                return original(**payload)

            gateway._on_call = spy
            gateway.transport = RecordingTransport([completion("完整正文")])
            gateway.sleep = lambda _: None
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
            self.assertEqual(result, "完整正文")
            self.assertEqual(len(recorded), 1)
            self.assertEqual(recorded[0]["status"], "success")
            self.assertIsNotNone(context.analytics)


class DependencyBoundaryTests(unittest.TestCase):
    def test_factories_and_providers_do_not_import_facades_or_factories_wrong_way(self) -> None:
        root = Path("novel_agent/integrations")
        offenders: list[str] = []
        for path in root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                mods: list[str] = []
                if isinstance(node, ast.Import):
                    mods = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    mods = [node.module]
                for mod in mods:
                    if mod.startswith("novel_agent.adapters"):
                        offenders.append(f"{path}: {mod}")
                    if path.name != "factories.py" and (
                        mod == "novel_agent.integrations.factories"
                        or mod.startswith("novel_agent.integrations.factories.")
                    ):
                        offenders.append(f"{path}: {mod}")
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import tempfile
import unittest
from http import HTTPStatus
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from email.message import Message
from urllib.error import HTTPError

from novel_agent.api import AppContext, NovelAgentHandler
from novel_agent.config import Settings
from novel_agent.features.llm_settings.errors import LLMSettingsError
from novel_agent.features.llm_settings.factory import LLMClientFactory
from novel_agent.features.llm_settings.models import LLMConfigSource, LLMProvider
from novel_agent.features.llm_settings.repository import LLMSettingsRepository, SETTING_KEY
from novel_agent.features.llm_settings.resolver import EffectiveLLMConfigResolver
from novel_agent.features.llm_settings.runtime import SnapshotLLMGateway
from novel_agent.features.llm_settings.secret_store import MemorySecretStore
from novel_agent.features.llm_settings.service import LLMSettingsService
from novel_agent.features.llm_settings.validation import normalize_base_url, normalize_model
from novel_agent.integrations.llm.deepseek import DeepSeekLLMGateway
from novel_agent.integrations.search.disabled import DisabledSearchAdapter
from novel_agent.repository import SQLiteRepository
from novel_agent.service import NovelAgentService
from tests.test_deepseek_gateway import RecordingTransport, completion


TEST_KEY = "test-llm-key-aaaa"
REPLACEMENT_KEY = "test-llm-key-bbbb"


def _settings(**overrides: object) -> Settings:
    from dataclasses import replace
    from tests.test_factories import _settings as base

    return replace(base(), **overrides)  # type: ignore[arg-type]


class _Harness:
    def __init__(self, *, env_key: str | None = None, mode: str = "online") -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        root = Path(self._tmpdir.name)
        self.repository = SQLiteRepository(root / "llm.db")
        self.secrets = MemorySecretStore()
        self.settings = _settings(
            mode=mode,
            database_path=root / "llm.db",
            llm_provider="deepseek" if env_key else "disabled",
            llm_api_key=env_key,
            llm_base_url="https://api.deepseek.com" if env_key else None,
            llm_model="deepseek-v4-pro" if env_key else None,
        )
        self.repo = LLMSettingsRepository(self.repository)
        self.resolver = EffectiveLLMConfigResolver(self.settings, self.repo, self.secrets)
        self.transport = RecordingTransport([completion("ok")])
        self.factory = LLMClientFactory(transport=self.transport)
        self.runtime = SnapshotLLMGateway(self.resolver, self.factory)
        self.service = LLMSettingsService(
            self.repo,
            self.secrets,
            self.resolver,
            self.factory,
            on_change=self.runtime.invalidate,
        )

    def cleanup(self) -> None:
        self._tmpdir.cleanup()

    def save_ok(self, **overrides: object) -> dict:
        payload = {
            "provider": "dashscope",
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "model": "qwen-plus",
            "api_key": TEST_KEY,
            "enabled": True,
            "timeout_seconds": 120,
            "max_retries": 2,
            "expected_version": 0,
        }
        payload.update(overrides)
        return self.service.save(payload)


class ValidationTests(unittest.TestCase):
    def test_rejects_bad_provider_url_and_model(self) -> None:
        with self.assertRaises(LLMSettingsError):
            normalize_base_url("ftp://example.com")
        with self.assertRaises(LLMSettingsError):
            normalize_model("")
        with self.assertRaises(LLMSettingsError):
            normalize_model("bad model with spaces!")


class ResolverPriorityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.harness = _Harness(env_key=TEST_KEY, mode="online")

    def tearDown(self) -> None:
        self.harness.cleanup()

    def test_saved_beats_environment_beats_offline_beats_none(self) -> None:
        env = self.harness.resolver.resolve()
        self.assertEqual(env.source, LLMConfigSource.ENVIRONMENT)
        self.harness.save_ok()
        saved = self.harness.resolver.resolve()
        self.assertEqual(saved.source, LLMConfigSource.SAVED)
        self.assertEqual(saved.provider, LLMProvider.DASHSCOPE)
        self.assertEqual(saved.model, "qwen-plus")
        self.harness.service.delete()
        again = self.harness.resolver.resolve()
        self.assertEqual(again.source, LLMConfigSource.ENVIRONMENT)
        empty = _Harness(mode="offline")
        self.addCleanup(empty.cleanup)
        self.assertEqual(empty.resolver.resolve().source, LLMConfigSource.OFFLINE)
        none = _Harness(mode="online")
        self.addCleanup(none.cleanup)
        self.assertEqual(none.resolver.resolve().source, LLMConfigSource.NONE)

    def test_disable_blocks_environment_fallback(self) -> None:
        view = self.harness.service.save(
            {
                "provider": "dashscope",
                "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "model": "qwen-plus",
                "enabled": False,
                "timeout_seconds": 120,
                "max_retries": 2,
            }
        )
        self.assertEqual(view["card_status"], "disabled")
        self.assertEqual(view["source"], "saved")
        resolved = self.harness.resolver.resolve()
        self.assertFalse(resolved.enabled)
        self.assertEqual(resolved.source, LLMConfigSource.SAVED)
        self.assertIsNone(resolved.api_key)
        from novel_agent.features.llm_settings.unconfigured import UnconfiguredLLMGateway

        client = self.harness.factory.create(resolved)
        self.assertIsInstance(client, UnconfiguredLLMGateway)
        self.harness.service.delete()
        again = self.harness.resolver.resolve()
        self.assertEqual(again.source, LLMConfigSource.ENVIRONMENT)
        self.assertTrue(again.enabled)


class SecretAndSaveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.harness = _Harness()

    def tearDown(self) -> None:
        self.harness.cleanup()

    def test_view_never_contains_api_key(self) -> None:
        view = self.harness.save_ok()
        dumped = json.dumps(view)
        self.assertNotIn(TEST_KEY, dumped)
        self.assertTrue(view["has_api_key"])
        self.assertEqual(view["api_key_mask"], "••••aaaa")
        self.assertNotIn("api_key", view)
        self.assertEqual(view["card_status"], "enabled")
        self.assertEqual(view["verification_status"], "valid")

    def test_keep_existing_key_and_replace(self) -> None:
        first = self.harness.save_ok()
        kept = self.harness.service.save(
            {
                "provider": "dashscope",
                "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "model": "qwen-plus",
                "keep_existing_api_key": True,
                "enabled": True,
                "timeout_seconds": 90,
                "max_retries": 1,
                "expected_version": first["version"],
            }
        )
        self.assertEqual(self.harness.resolver.resolve().api_key, TEST_KEY)
        self.assertEqual(kept["timeout_seconds"], 90)
        replaced = self.harness.service.save(
            {
                "provider": "dashscope",
                "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "model": "qwen-plus",
                "api_key": REPLACEMENT_KEY,
                "enabled": True,
                "timeout_seconds": 90,
                "max_retries": 1,
                "expected_version": kept["version"],
            }
        )
        self.assertEqual(self.harness.resolver.resolve().api_key, REPLACEMENT_KEY)
        self.assertEqual(replaced["api_key_mask"], "••••bbbb")
        self.assertFalse(self.harness.secrets.exists(first.get("secret_ref") or "missing"))

    def test_version_conflict_and_failed_save_keeps_old_secret(self) -> None:
        first = self.harness.save_ok()
        with self.assertRaises(LLMSettingsError) as ctx:
            self.harness.service.save(
                {
                    "provider": "deepseek",
                    "base_url": "https://api.deepseek.com",
                    "model": "deepseek-chat",
                    "api_key": REPLACEMENT_KEY,
                    "enabled": True,
                    "expected_version": 99,
                }
            )
        self.assertEqual(ctx.exception.code, "CONFIG_VERSION_CONFLICT")
        self.assertEqual(self.harness.resolver.resolve().api_key, TEST_KEY)

        original_save = self.harness.repo.save

        def boom(config) -> None:
            raise RuntimeError("disk full")

        self.harness.repo.save = boom  # type: ignore[method-assign]
        with self.assertRaises(RuntimeError):
            self.harness.service.save(
                {
                    "provider": "deepseek",
                    "base_url": "https://api.deepseek.com",
                    "model": "deepseek-chat",
                    "api_key": REPLACEMENT_KEY,
                    "keep_existing_api_key": False,
                    "enabled": True,
                    "expected_version": first["version"],
                }
            )
        self.harness.repo.save = original_save  # type: ignore[method-assign]
        self.assertEqual(self.harness.resolver.resolve().api_key, TEST_KEY)

    def test_logs_do_not_include_key(self) -> None:
        with self.assertLogs("novel_agent.llm_settings", level="INFO") as captured:
            self.harness.save_ok()
        joined = "\n".join(captured.output)
        self.assertNotIn(TEST_KEY, joined)

    def test_disable_then_enable_keeps_secret(self) -> None:
        first = self.harness.save_ok()
        disabled = self.harness.service.save(
            {
                "provider": "dashscope",
                "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "model": "qwen-plus",
                "keep_existing_api_key": True,
                "enabled": False,
                "timeout_seconds": 120,
                "max_retries": 2,
                "expected_version": first["version"],
            }
        )
        self.assertEqual(disabled["card_status"], "disabled")
        self.assertIsNone(self.harness.resolver.resolve().api_key)
        enabled = self.harness.service.save(
            {
                "provider": "dashscope",
                "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "model": "qwen-plus",
                "keep_existing_api_key": True,
                "enabled": True,
                "timeout_seconds": 120,
                "max_retries": 2,
                "expected_version": disabled["version"],
            }
        )
        self.assertEqual(enabled["card_status"], "enabled")
        self.assertEqual(self.harness.resolver.resolve().api_key, TEST_KEY)


class ProbeAndFactoryTests(unittest.TestCase):
    def test_providers_map_to_adapters(self) -> None:
        factory = LLMClientFactory(transport=RecordingTransport([completion("ok")]))
        harness = _Harness()
        self.addCleanup(harness.cleanup)
        mapping = {
            "deepseek": "deepseek",
            "dashscope": "dashscope",
            "openai": "openai",
            "openai_compatible": "openai-compatible",
        }
        for provider, adapter in mapping.items():
            view = harness.save_ok(
                provider=provider,
                base_url="https://example.com/v1" if provider == "openai_compatible" else {
                    "deepseek": "https://api.deepseek.com",
                    "dashscope": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                    "openai": "https://api.openai.com/v1",
                    "openai_compatible": "https://example.com/v1",
                }[provider],
                model="demo-model",
                expected_version=harness.repo.load().version if harness.repo.load() else 0,
            )
            config = harness.resolver.resolve()
            client = factory.create(config)
            self.assertIsInstance(client, DeepSeekLLMGateway)
            self.assertEqual(client.provider_name, adapter)
            self.assertEqual(view["provider"], provider)

    def test_probe_error_codes(self) -> None:
        harness = _Harness()
        self.addCleanup(harness.cleanup)
        harness.save_ok()
        headers = Message()
        error = HTTPError("https://example.com", 401, "no", hdrs=headers, fp=BytesIO())
        harness.factory._transport = RecordingTransport([error])
        with self.assertRaises(LLMSettingsError) as ctx:
            harness.service.test_connection({})
        self.assertEqual(ctx.exception.code, "INVALID_API_KEY")

    def test_snapshot_survives_config_change(self) -> None:
        harness = _Harness()
        self.addCleanup(harness.cleanup)
        harness.save_ok()
        harness.runtime.begin_task()
        first = harness.runtime.task_client()
        harness.save_ok(model="qwen-max", expected_version=harness.repo.load().version)
        self.assertIs(harness.runtime.task_client(), first)
        harness.runtime.begin_task()
        self.assertIsNot(harness.runtime.task_client(), first)
        self.assertEqual(harness.runtime.current_snapshot().model, "qwen-max")


class HttpLlmSettingsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.harness = _Harness()
        root = Path(self.harness._tmpdir.name)
        web = root / "apps" / "web"
        web.mkdir(parents=True)
        (web / "index.html").write_text("<html></html>", encoding="utf-8")
        agent = NovelAgentService(
            repository=self.harness.repository,
            gateway=self.harness.runtime,
            search=DisabledSearchAdapter(),
        )
        self.context = AppContext(
            self.harness.settings,
            agent,
            self.harness.repository,
            web,
            llm_settings=self.harness.service,
        )
        self.handler_cls = type("Handler", (NovelAgentHandler,), {"context": self.context})

    def tearDown(self) -> None:
        self.harness.cleanup()

    def _request(self, method: str, path: str, payload: dict | None = None) -> tuple[int, dict]:
        body = json.dumps(payload or {}).encode("utf-8") if payload is not None else b"{}"

        class FakeHandler(self.handler_cls):  # type: ignore[misc,valid-type]
            def __init__(self) -> None:
                self.path = path
                self.command = method
                self.request_version = "HTTP/1.1"
                self.headers = {"Content-Length": str(len(body))}
                self.rfile = BytesIO(body)
                self._status = 200
                self._body = b""

            def send_response(self, code: int, message: str | None = None) -> None:
                self._status = int(code)

            def send_header(self, keyword: str, value: str) -> None:
                return None

            def end_headers(self) -> None:
                return None

            def _cors_headers(self) -> None:
                return None

            @property
            def wfile(self):
                handler = self

                class Writer:
                    def write(self, data: bytes) -> int:
                        handler._body += data
                        return len(data)

                return Writer()

        fake = FakeHandler()
        getattr(fake, f"do_{method}")()
        parsed = json.loads(fake._body.decode("utf-8") or "{}")
        dumped = json.dumps(parsed)
        self.assertNotIn(TEST_KEY, dumped)
        self.assertNotIn(REPLACEMENT_KEY, dumped)
        return fake._status, parsed

    def test_get_put_test_delete(self) -> None:
        status, view = self._request("GET", "/api/settings/llm")
        self.assertEqual(status, 200)
        self.assertFalse(view.get("has_api_key"))
        status, saved = self._request(
            "PUT",
            "/api/settings/llm",
            {
                "provider": "dashscope",
                "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "model": "qwen-plus",
                "api_key": TEST_KEY,
                "enabled": True,
                "timeout_seconds": 120,
                "max_retries": 2,
            },
        )
        self.assertEqual(status, 200)
        self.assertTrue(saved["has_api_key"])
        self.assertNotIn("api_key", saved)
        stored = self.harness.repository.get_setting(SETTING_KEY)
        self.assertNotIn(TEST_KEY, json.dumps(stored))
        status, tested = self._request("POST", "/api/settings/llm/test", {})
        self.assertEqual(status, 200)
        self.assertTrue(tested["ok"])
        status, deleted = self._request("DELETE", "/api/settings/llm")
        self.assertEqual(status, 200)
        self.assertIn(deleted["source"], {"none", "offline", "environment"})

    def test_unified_factory_after_save(self) -> None:
        self._request(
            "PUT",
            "/api/settings/llm",
            {
                "provider": "openai",
                "base_url": "https://api.openai.com/v1",
                "model": "gpt-4o-mini",
                "api_key": TEST_KEY,
                "enabled": True,
            },
        )
        self.context.bind_llm_task()
        client = self.context.service.gateway.task_client()
        self.assertIsInstance(client, DeepSeekLLMGateway)
        self.assertEqual(client.provider_name, "openai")
        self.assertEqual(client.model, "gpt-4o-mini")
        design = self.context.story_design.gateway.task_client()
        self.assertEqual(design.provider_name, "openai")
        self.assertEqual(design.model, client.model)

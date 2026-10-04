from __future__ import annotations

from typing import Protocol

from novel_agent.features.llm_settings.errors import LLMSettingsError, USER_MESSAGES


class SecretStore(Protocol):
    def put(self, secret_ref: str, value: str) -> None: ...

    def get(self, secret_ref: str) -> str: ...

    def delete(self, secret_ref: str) -> None: ...

    def exists(self, secret_ref: str) -> bool: ...


class MemorySecretStore:
    def __init__(self) -> None:
        self._values: dict[str, str] = {}

    def put(self, secret_ref: str, value: str) -> None:
        self._values[secret_ref] = value

    def get(self, secret_ref: str) -> str:
        try:
            return self._values[secret_ref]
        except KeyError as exc:
            raise LLMSettingsError("LLM_NOT_CONFIGURED", "尚未配置大模型服务") from exc

    def delete(self, secret_ref: str) -> None:
        self._values.pop(secret_ref, None)

    def exists(self, secret_ref: str) -> bool:
        return secret_ref in self._values


class KeyringSecretStore:
    SERVICE = "NovelAgent.LLM"

    def put(self, secret_ref: str, value: str) -> None:
        backend = _keyring()
        try:
            backend.set_password(self.SERVICE, secret_ref, value)
        except Exception as exc:
            raise LLMSettingsError(
                "SECRET_STORE_UNAVAILABLE",
                USER_MESSAGES["SECRET_STORE_UNAVAILABLE"],
            ) from exc

    def get(self, secret_ref: str) -> str:
        backend = _keyring()
        try:
            value = backend.get_password(self.SERVICE, secret_ref)
        except Exception as exc:
            raise LLMSettingsError(
                "SECRET_STORE_UNAVAILABLE",
                USER_MESSAGES["SECRET_STORE_UNAVAILABLE"],
            ) from exc
        if not value:
            raise LLMSettingsError("LLM_NOT_CONFIGURED", "尚未配置大模型服务")
        return value

    def delete(self, secret_ref: str) -> None:
        backend = _keyring()
        try:
            backend.delete_password(self.SERVICE, secret_ref)
        except Exception:
            return

    def exists(self, secret_ref: str) -> bool:
        backend = _keyring()
        try:
            return bool(backend.get_password(self.SERVICE, secret_ref))
        except Exception as exc:
            raise LLMSettingsError(
                "SECRET_STORE_UNAVAILABLE",
                USER_MESSAGES["SECRET_STORE_UNAVAILABLE"],
            ) from exc


def _keyring():
    try:
        import keyring
    except Exception as exc:
        raise LLMSettingsError(
            "SECRET_STORE_UNAVAILABLE",
            USER_MESSAGES["SECRET_STORE_UNAVAILABLE"],
        ) from exc
    return keyring


def build_secret_store() -> SecretStore:
    import os

    mode = (os.getenv("NOVEL_AGENT_SECRET_STORE") or "keyring").strip().lower()
    if mode == "memory":
        return MemorySecretStore()
    return KeyringSecretStore()

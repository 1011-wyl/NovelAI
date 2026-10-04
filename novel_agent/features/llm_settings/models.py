from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class LLMProvider(str, Enum):
    DEEPSEEK = "deepseek"
    DASHSCOPE = "dashscope"
    OPENAI = "openai"
    OPENAI_COMPATIBLE = "openai_compatible"


class LLMConfigSource(str, Enum):
    SAVED = "saved"
    ENVIRONMENT = "environment"
    OFFLINE = "offline"
    NONE = "none"


@dataclass(frozen=True, slots=True)
class LLMConfiguration:
    id: str
    provider: LLMProvider
    base_url: str
    model: str
    enabled: bool
    timeout_seconds: int
    max_retries: int
    secret_ref: str | None
    api_key_mask: str | None
    verification_status: str
    last_tested_at: datetime | None
    last_error_code: str | None
    created_at: datetime
    updated_at: datetime
    version: int


@dataclass(frozen=True, slots=True)
class ResolvedLLMCredentials:
    secret_ref: str
    api_key: str


@dataclass(frozen=True, slots=True)
class LLMConfigSnapshot:
    provider: str
    provider_label: str
    model: str
    base_url: str
    source: str
    version: int
    timeout_seconds: int
    max_retries: int


@dataclass(frozen=True, slots=True)
class EffectiveLLMConfig:
    source: LLMConfigSource
    provider: LLMProvider | None
    adapter_name: str
    base_url: str
    model: str
    api_key: str | None
    timeout_seconds: float
    max_retries: int
    reasoning_budget_factor: float
    version: int
    enabled: bool
    verification_status: str
    last_tested_at: datetime | None
    last_error_code: str | None
    has_api_key: bool
    api_key_mask: str | None
    snapshot: LLMConfigSnapshot

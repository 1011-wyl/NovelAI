from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field, replace
from typing import Iterator


@dataclass(frozen=True, slots=True)
class LLMCallContext:
    project_id: str | None = None
    chapter_id: str | None = None
    run_id: str | None = None
    category: str = "agent"


@dataclass(frozen=True, slots=True)
class LLMCallRecord:
    date: str
    operation: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    retry_count: int = 0
    project_id: str | None = None
    chapter_id: str | None = None
    run_id: str | None = None
    category: str = "agent"
    provider: str | None = None
    status: str = "success"
    latency_ms: int | None = None
    first_token_ms: int | None = None
    cache_tokens: int = 0
    error_type: str | None = None
    error_message: str | None = None
    error_status_code: int | None = None


_LLM_CALL_CONTEXT: ContextVar[LLMCallContext] = ContextVar(
    "novel_agent_llm_call_context",
    default=LLMCallContext(),
)


def current_llm_context() -> LLMCallContext:
    return _LLM_CALL_CONTEXT.get()


@contextmanager
def llm_call_scope(
    *,
    project_id: str | None = None,
    chapter_id: str | None = None,
    run_id: str | None = None,
    category: str | None = None,
) -> Iterator[LLMCallContext]:
    current = current_llm_context()
    updates: dict[str, object] = {}
    if project_id is not None:
        updates["project_id"] = project_id
    if chapter_id is not None:
        updates["chapter_id"] = chapter_id
    if run_id is not None:
        updates["run_id"] = run_id
    if category is not None:
        updates["category"] = category
    scoped = replace(current, **updates) if updates else current
    token = _LLM_CALL_CONTEXT.set(scoped)
    try:
        yield scoped
    finally:
        _LLM_CALL_CONTEXT.reset(token)


def classify_llm_error(exc: BaseException) -> tuple[str, str, int | None]:
    """Return safe (error_type, short_message, status_code) without secrets."""
    name = type(exc).__name__
    message = str(exc).strip() or name
    if len(message) > 240:
        message = message[:237] + "..."
    status_code: int | None = None
    lowered = message.lower()
    if "401" in message or "403" in message or "密钥" in message or "auth" in lowered:
        status_code = 401 if "401" in message else 403 if "403" in message else None
    elif "429" in message or "频率" in message or "额度" in message:
        status_code = 429
    elif "超时" in message or "timeout" in lowered:
        status_code = None
    return name, message, status_code

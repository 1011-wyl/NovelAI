"""Provider telemetry sink types.

These describe how a Gateway reports call/usage events. They intentionally do
not depend on Analytics storage or `novel_agent.telemetry.LLMCallRecord`.

Current DeepSeek behavior treats `_on_call` and `_on_usage` as interchangeable
callables invoked with the same keyword payload; both Protocols mirror that.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMCallSink(Protocol):
    def __call__(self, **payload: object) -> None: ...


@runtime_checkable
class LLMUsageSink(Protocol):
    def __call__(self, **payload: object) -> None: ...

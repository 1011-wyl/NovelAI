"""Fanqie publishing adapter — intentionally gated until a real integration exists."""

from __future__ import annotations

from novel_agent.integrations.errors import APIConfigurationRequired


class FanqiePublisherAdapter:
    name = "fanqie-disabled"

    def __init__(self, *, api_key: str, base_url: str, platform_book_id: str):
        raise APIConfigurationRequired("真实番茄发布仍被安全闸门禁用；当前只允许 MockPublisher")

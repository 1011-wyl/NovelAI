from __future__ import annotations


class AnalyticsError(RuntimeError):
    """Base error for analytics persistence and query failures."""


class AnalyticsValidationError(AnalyticsError, ValueError):
    """Invalid analytics filter, date, timezone, pagination, or sort input."""

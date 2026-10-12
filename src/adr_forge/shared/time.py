"""Timezone-safe clock helpers."""

from __future__ import annotations

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return the current timezone-aware UTC time."""
    return datetime.now(UTC)


def require_utc(value: datetime) -> datetime:
    """Normalize an aware datetime to UTC, rejecting ambiguous naive values."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(UTC)

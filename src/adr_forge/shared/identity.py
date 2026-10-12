"""Application-owned identifiers."""

from __future__ import annotations

import secrets
import time
from uuid import UUID


def new_uuid7() -> UUID:
    """Return a time-ordered UUIDv7 without relying on a Python-version-specific API."""
    timestamp_ms = time.time_ns() // 1_000_000
    rand_a = secrets.randbits(12)
    rand_b = secrets.randbits(62)
    value = (timestamp_ms << 80) | (0x7 << 76) | (rand_a << 64) | (0b10 << 62) | rand_b
    return UUID(int=value)


def new_uuid() -> UUID:
    """Return the standard ADR Forge UUID (UUIDv7)."""
    return new_uuid7()

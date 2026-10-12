"""Deterministic JSON and SHA-256 helpers used in persisted provenance."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from adr_forge.shared.time import require_utc


def _normalise(value: Any) -> Any:
    if value is None or isinstance(value, (bool, str, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("canonical JSON does not support non-finite floats")
        return value
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("canonical JSON does not support non-finite decimals")
        normalized_decimal = value.normalize()
        return format(normalized_decimal, "f")
    if isinstance(value, datetime):
        normalized_datetime = require_utc(value)
        return normalized_datetime.isoformat().replace("+00:00", "Z")
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise TypeError("canonical JSON object keys must be strings")
        return {key: _normalise(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, memoryview)):
        return [_normalise(item) for item in value]
    raise TypeError(f"unsupported canonical JSON value: {type(value).__name__}")


def canonical_json(value: Any) -> str:
    """Serialize supported values as compact, sorted, UTF-8-safe JSON."""
    return json.dumps(
        _normalise(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def canonical_json_bytes(value: Any) -> bytes:
    return canonical_json(value).encode("utf-8")


def sha256_hex(value: bytes | bytearray | memoryview) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_sha256(value: Any) -> str:
    return sha256_hex(canonical_json_bytes(value))

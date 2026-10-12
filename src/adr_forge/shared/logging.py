"""Structured, secret-safe logging primitives."""

from __future__ import annotations

import contextvars
import json
import logging
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import Any

_correlation: contextvars.ContextVar[dict[str, str] | None] = contextvars.ContextVar(
    "correlation", default=None
)
_SENSITIVE_KEY_PARTS = (
    "token",
    "secret",
    "password",
    "prompt",
    "retrieved",
    "content",
    "authorization",
)
REDACTED = "[REDACTED]"


def redact(value: Any, *, key: str | None = None) -> Any:
    if key and any(part in key.lower() for part in _SENSITIVE_KEY_PARTS):
        return REDACTED
    if isinstance(value, Mapping):
        return {
            str(item_key): redact(item_value, key=str(item_key))
            for item_key, item_value in value.items()
        }
    if isinstance(value, list | tuple | set | frozenset):
        return [redact(item) for item in value]
    return value


@contextmanager
def log_context(**values: str) -> Iterator[None]:
    current = _correlation.get() or {}
    additions = {key: value for key, value in values.items() if value}
    token = _correlation.set({**current, **additions})
    try:
        yield
    finally:
        _correlation.reset(token)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            **(_correlation.get() or {}),
        }
        extra = getattr(record, "structured", None)
        if isinstance(extra, Mapping):
            payload.update(redact(extra))
        return json.dumps(redact(payload), ensure_ascii=False, sort_keys=True, default=str)


def configure_logging(*, level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger("adr_forge")
    logger.setLevel(level)
    logger.propagate = False
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
    return logger

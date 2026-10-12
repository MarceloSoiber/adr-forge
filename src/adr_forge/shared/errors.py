"""Stable application errors that API adapters map to Problem Details."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ErrorCode(StrEnum):
    VALIDATION = "validation_error"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    PRECONDITION_FAILED = "precondition_failed"
    RESOURCE_UNAVAILABLE = "resource_unavailable"
    INTERNAL = "internal_error"


@dataclass(slots=True)
class DomainError(Exception):
    code: ErrorCode
    title: str
    status: int
    detail: str | None = None

    def __str__(self) -> str:
        return self.detail or self.title


class ValidationError(DomainError):
    def __init__(self, detail: str | None = None) -> None:
        super().__init__(ErrorCode.VALIDATION, "Validation failed", 422, detail)


class NotFoundError(DomainError):
    def __init__(self, detail: str | None = None) -> None:
        super().__init__(ErrorCode.NOT_FOUND, "Resource not found", 404, detail)


class ConflictError(DomainError):
    def __init__(self, detail: str | None = None) -> None:
        super().__init__(ErrorCode.CONFLICT, "Conflict", 409, detail)


class PreconditionFailedError(DomainError):
    def __init__(self, detail: str | None = None) -> None:
        super().__init__(ErrorCode.PRECONDITION_FAILED, "Precondition failed", 503, detail)

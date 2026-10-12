"""Dependency-inversion protocols shared by application modules."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence
from pathlib import Path
from typing import Any, Protocol, TypeVar, runtime_checkable
from uuid import UUID

T = TypeVar("T")


@runtime_checkable
class ModelRuntime(Protocol):
    async def generate(self, prompt: str, *, cancellation: CancellationToken) -> str: ...


@runtime_checkable
class RetrievalProvider(Protocol):
    async def retrieve(
        self, query: str, *, filters: Mapping[str, str] | None = None
    ) -> Sequence[Mapping[str, Any]]: ...


@runtime_checkable
class AnalysisStrategy(Protocol):
    id: str
    version: str

    async def analyze(self, scenario: Any, *, retrieval_snapshot: Any | None = None) -> Any: ...


@runtime_checkable
class Repository(Protocol[T]):
    async def get(self, identity: UUID) -> T | None: ...

    async def add(self, entity: T) -> None: ...


@runtime_checkable
class Transaction(Protocol):
    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...


@runtime_checkable
class UnitOfWork(Transaction, Protocol):
    async def __aenter__(self) -> UnitOfWork: ...

    async def __aexit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None: ...


@runtime_checkable
class DiskCapacityProbe(Protocol):
    def free_bytes(self, path: Path) -> int: ...


@runtime_checkable
class ArtifactReferenceQuery(Protocol):
    async def has_references(self, artifact_id: UUID) -> bool: ...


@runtime_checkable
class ProgressPublisher(Protocol):
    async def publish(self, run_id: UUID, snapshot: Mapping[str, Any]) -> None: ...

    async def subscribe(self, run_id: UUID) -> AsyncIterator[Mapping[str, Any]]: ...


@runtime_checkable
class CancellationToken(Protocol):
    @property
    def cancelled(self) -> bool: ...

    def raise_if_cancelled(self) -> None: ...


@runtime_checkable
class DiagnosticProbe(Protocol):
    def diagnose(self) -> Mapping[str, Any]: ...

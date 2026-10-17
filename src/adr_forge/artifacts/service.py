"""Quota decisions independent of persistence and host-probe implementations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol
from uuid import uuid4

from adr_forge.artifacts.repository import ArtifactRepository, CatalogArtifact
from adr_forge.artifacts.store import ArtifactStore, ArtifactStoreError
from adr_forge.shared.time import utc_now


class DiskCapacityProbe(Protocol):
    def free_bytes(self) -> int: ...


class ArtifactCatalog(Protocol):
    async def physical_bytes(self) -> int: ...


class ArtifactCapacityError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class QuotaStatus:
    used_bytes: int
    warning_bytes: int
    limit_bytes: int
    free_bytes: int
    reserve_bytes: int

    @property
    def warning(self) -> bool:
        return self.used_bytes >= self.warning_bytes


class ArtifactQuota:
    def __init__(
        self,
        catalog: ArtifactCatalog,
        disk: DiskCapacityProbe,
        *,
        warning_bytes: int,
        limit_bytes: int,
        reserve_bytes: int,
    ) -> None:
        self.catalog = catalog
        self.disk = disk
        self.warning_bytes = warning_bytes
        self.limit_bytes = limit_bytes
        self.reserve_bytes = reserve_bytes

    async def status(self) -> QuotaStatus:
        return QuotaStatus(
            await self.catalog.physical_bytes(),
            self.warning_bytes,
            self.limit_bytes,
            self.disk.free_bytes(),
            self.reserve_bytes,
        )

    async def ensure_capacity(self, incoming_bytes: int) -> QuotaStatus:
        if incoming_bytes < 0:
            raise ArtifactCapacityError("artifact size cannot be negative")
        state = await self.status()
        if state.used_bytes + incoming_bytes > state.limit_bytes:
            raise ArtifactCapacityError("artifact quota limit reached")
        if state.free_bytes - incoming_bytes < state.reserve_bytes:
            raise ArtifactCapacityError("free disk reserve would be violated")
        return state


@dataclass(frozen=True, slots=True)
class PruneResult:
    artifact_id: str
    status: str
    reason: str
    reclaimed_bytes: int


@dataclass(frozen=True, slots=True)
class PruneReport:
    operation_id: str
    results: tuple[PruneResult, ...]

    @property
    def reclaimed_bytes(self) -> int:
        return sum(item.reclaimed_bytes for item in self.results)


class ArtifactMaintenance:
    """Conservative artifact listing and filesystem-first cleanup policy."""

    temporary_ttl = timedelta(days=1)

    def __init__(self, repository: ArtifactRepository, store: ArtifactStore) -> None:
        self._repository = repository
        self._store = store

    async def list(self) -> list[CatalogArtifact]:
        return await self._repository.list_catalog()

    async def prune(self, *, confirmed: bool) -> PruneReport:
        if not confirmed:
            raise ArtifactCapacityError("artifact prune requires --confirm")
        operation_id = str(uuid4())
        now = utc_now()
        results: list[PruneResult] = []
        for artifact in await self._repository.list_catalog():
            candidate_reason = self._candidate_reason(artifact, now=now)
            if candidate_reason is None:
                continue
            try:
                removed = await self._store.remove(artifact.relative_path)
                reclaimed = artifact.size_bytes if removed else 0
                reason = candidate_reason if removed else "missing_bytes"
                await self._repository.record_prune(
                    artifact,
                    operation_id=operation_id,
                    reason=reason,
                    reclaimed_bytes=reclaimed,
                    pruned_at=now,
                )
                results.append(PruneResult(artifact.id, "deleted", reason, reclaimed))
            except (ArtifactStoreError, OSError, ValueError) as exc:
                results.append(PruneResult(artifact.id, "failed", str(exc), 0))
        return PruneReport(operation_id, tuple(results))

    def _candidate_reason(self, artifact: CatalogArtifact, *, now: datetime) -> str | None:
        if artifact.reference_count:
            return None
        if artifact.retention == "prunable":
            return "unreferenced_prunable"
        if artifact.retention == "temporary" and artifact.created_at <= now - self.temporary_ttl:
            return "expired_temporary"
        return None

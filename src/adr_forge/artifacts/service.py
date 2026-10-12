"""Quota decisions independent of persistence and host-probe implementations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


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

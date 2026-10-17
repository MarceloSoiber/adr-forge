"""Guarded foreground orchestration for local SFT runs."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from dataclasses import dataclass

from adr_forge.system.gpu_lease import GpuLease, PreflightResult
from adr_forge.training.sft import SFTConfig, SFTResult, Trainer


class TrainingPreconditionError(RuntimeError):
    """Raised before model allocation when local safety checks fail."""


@dataclass(frozen=True, slots=True)
class TrainingServiceResult:
    result: SFTResult
    free_disk_bytes: int


class TrainingService:
    """Own resource checks and the exclusive lease, never ML implementation details."""

    def __init__(
        self,
        *,
        preflight: Callable[[], PreflightResult],
        lease: GpuLease,
        minimum_free_disk_bytes: int,
    ) -> None:
        self._preflight = preflight
        self._lease = lease
        self._minimum_free_disk_bytes = minimum_free_disk_bytes

    def run(
        self,
        config: SFTConfig,
        *,
        trainer_factory: Callable[[SFTConfig, list[dict[str, object]]], Trainer] | None = None,
        resume: bool = False,
    ) -> TrainingServiceResult:
        """Validate capacity, acquire the lease, then lazily invoke the SFT core."""
        config.output_dir.parent.mkdir(parents=True, exist_ok=True)
        disk = shutil.disk_usage(config.output_dir.parent).free
        if disk < self._minimum_free_disk_bytes:
            raise TrainingPreconditionError("insufficient_disk_capacity")
        readiness = self._preflight()
        if not readiness.ready:
            raise TrainingPreconditionError("gpu_preflight_failed:" + ",".join(readiness.blockers))
        # Import is intentionally deferred until all preconditions and the OS
        # lease have succeeded, so CPU-only checks never initialize ML packages.
        from adr_forge.training.sft import run_sft

        with self._lease:
            result = run_sft(config, trainer_factory=trainer_factory, resume=resume)
        return TrainingServiceResult(result=result, free_disk_bytes=disk)

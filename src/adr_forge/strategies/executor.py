"""Single-worker local executor for cooperative analysis generation."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from adr_forge.experiments.run_models import AnalysisRun, RunStatus
from adr_forge.experiments.run_repository import RunRepository
from adr_forge.system.gpu_lease import GpuLease, GpuPreflight
from adr_forge.system.progress import CancellationToken, ProgressPublisher

RunJob = Callable[[CancellationToken], Awaitable[None]]
PersistSnapshot = Callable[[str, str, str, int | None], Awaitable[bool | None]]


@dataclass(slots=True)
class _QueuedJob:
    run_id: str
    job: RunJob
    requires_gpu: bool = False


class AnalysisExecutor:
    """Run exactly one local inference job at a time without blocking request handlers."""

    def __init__(
        self,
        progress: ProgressPublisher | None = None,
        *,
        persist_snapshot: PersistSnapshot | None = None,
        gpu_preflight: GpuPreflight | None = None,
        gpu_lease: GpuLease | None = None,
    ) -> None:
        self.progress = progress or ProgressPublisher()
        self._persist_snapshot = persist_snapshot
        self._gpu_preflight = gpu_preflight
        self._gpu_lease = gpu_lease
        self._queue: asyncio.Queue[_QueuedJob] = asyncio.Queue()
        self._worker: asyncio.Task[None] | None = None
        self._closed = False

    async def start(self) -> None:
        if self._worker is None:
            self._worker = asyncio.create_task(self._work(), name="adr-forge-analysis-worker")

    async def stop(self) -> None:
        self._closed = True
        if self._worker is not None:
            self._worker.cancel()
            try:
                await self._worker
            except asyncio.CancelledError:
                pass
            self._worker = None

    async def enqueue(self, run_id: str, job: RunJob, *, requires_gpu: bool = False) -> None:
        if self._closed:
            raise RuntimeError("analysis executor is stopped")
        await self.start()
        await self._publish_after_persist(run_id, "waiting_resources", 0)
        await self._queue.put(_QueuedJob(run_id=run_id, job=job, requires_gpu=requires_gpu))

    def cancel(self, run_id: str) -> bool:
        return self.progress.request_cancel(run_id)

    async def cancel_async(self, run_id: str) -> bool:
        """Request cancellation and durably expose it if the job has not started."""
        requested = self.cancel(run_id)
        if requested:
            current = self.progress.current(run_id)
            if current is not None and current.stage == "waiting_resources":
                await self._publish_after_persist(run_id, "cancelled", 100)
        return requested

    async def recover_abandoned_runs(self, repository: RunRepository) -> int:
        """Convert pending work left by a prior process to a terminal interruption.

        The compare-and-swap update means a concurrent actor can safely win the
        race; only snapshots actually persisted are published locally.
        """
        recovered = 0
        for stored in await repository.list_non_terminal():
            fields = {
                name: stored[name]
                for name in AnalysisRun.model_fields
                if name in stored
            }
            run = AnalysisRun.model_validate(fields)
            interrupted = run.transition(
                RunStatus.INTERRUPTED,
                stage="startup_recovery",
                progress_percent=100,
                failure_code="interrupted_restart",
                failure_detail="A execução foi interrompida pela reinicialização local.",
            )
            payload = {
                **interrupted.model_dump(mode="python"),
                "validation_attempts": stored.get("validation_attempts", []),
            }
            if await repository.transition(payload, run.progress_sequence):
                recovered += 1
                self.progress.publish(str(run.id), "startup_recovery", 100)
        return recovered

    async def _publish_after_persist(
        self, run_id: str, stage: str, progress_percent: int | None
    ) -> None:
        if self._persist_snapshot is not None:
            persisted = await self._persist_snapshot(
                run_id, self._status_for(stage), stage, progress_percent
            )
            if persisted is False:
                raise RuntimeError("analysis run snapshot was not persisted")
        self.progress.publish(run_id, stage, progress_percent)

    @staticmethod
    def _status_for(stage: str) -> str:
        return {
            "waiting_resources": RunStatus.WAITING_RESOURCES.value,
            "running": RunStatus.RUNNING.value,
            "completed": RunStatus.COMPLETED.value,
            "cancelled": RunStatus.CANCELLED.value,
            "failed": RunStatus.FAILED.value,
        }.get(stage, RunStatus.RUNNING.value)

    async def _work(self) -> None:
        while True:
            queued = await self._queue.get()
            try:
                token = self.progress.cancellation_token(queued.run_id)
                if token.is_cancelled:
                    await self._publish_after_persist(queued.run_id, "cancelled", 100)
                    continue
                await self._publish_after_persist(queued.run_id, "running", 1)
                if queued.requires_gpu:
                    await self._run_gpu_job(queued.job, token)
                else:
                    await queued.job(token)
                # Fetching again avoids treating the earlier preflight check as a
                # stable value: cancellation may be requested while the job awaits.
                if self.progress.cancellation_token(queued.run_id).is_cancelled:
                    await self._publish_after_persist(queued.run_id, "cancelled", 100)
                else:
                    await self._publish_after_persist(queued.run_id, "completed", 100)
            except InterruptedError:
                await self._publish_after_persist(queued.run_id, "cancelled", 100)
            except Exception:
                await self._publish_after_persist(queued.run_id, "failed", 100)
            finally:
                self._queue.task_done()

    async def _run_gpu_job(self, job: RunJob, token: CancellationToken) -> None:
        if self._gpu_preflight is None or self._gpu_lease is None:
            raise RuntimeError("GPU runtime requires configured preflight and lease")
        if not self._gpu_preflight.check().ready:
            raise RuntimeError("GPU preflight failed")
        self._gpu_lease.acquire()
        try:
            await job(token)
        finally:
            self._gpu_lease.release()


async def run_blocking(callback: Callable[[], Any], cancellation: CancellationToken) -> Any:
    """Move blocking runtime work off the event loop while preserving cancellation checks."""
    cancellation.raise_if_cancelled()
    result = await asyncio.to_thread(callback)
    cancellation.raise_if_cancelled()
    return result

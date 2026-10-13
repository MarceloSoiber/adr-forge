"""Single-worker local executor for cooperative analysis generation."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from adr_forge.system.progress import CancellationToken, ProgressPublisher

RunJob = Callable[[CancellationToken], Awaitable[None]]


@dataclass(slots=True)
class _QueuedJob:
    run_id: str
    job: RunJob


class AnalysisExecutor:
    """Run exactly one local inference job at a time without blocking request handlers."""

    def __init__(self, progress: ProgressPublisher | None = None) -> None:
        self.progress = progress or ProgressPublisher()
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

    async def enqueue(self, run_id: str, job: RunJob) -> None:
        if self._closed:
            raise RuntimeError("analysis executor is stopped")
        await self.start()
        self.progress.publish(run_id, "waiting_resources", 0)
        await self._queue.put(_QueuedJob(run_id=run_id, job=job))

    def cancel(self, run_id: str) -> bool:
        return self.progress.request_cancel(run_id)

    async def _work(self) -> None:
        while True:
            queued = await self._queue.get()
            try:
                token = self.progress.cancellation_token(queued.run_id)
                if token.is_cancelled:
                    self.progress.publish(queued.run_id, "cancelled", 100)
                    continue
                self.progress.publish(queued.run_id, "running", 1)
                await queued.job(token)
            except InterruptedError:
                self.progress.publish(queued.run_id, "cancelled", 100)
            except Exception:
                self.progress.publish(queued.run_id, "failed", 100)
            finally:
                self._queue.task_done()


async def run_blocking(callback: Callable[[], Any], cancellation: CancellationToken) -> Any:
    """Move blocking runtime work off the event loop while preserving cancellation checks."""
    cancellation.raise_if_cancelled()
    result = await asyncio.to_thread(callback)
    cancellation.raise_if_cancelled()
    return result

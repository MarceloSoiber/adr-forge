"""Runtime-agnostic in-process progress publication and cancellation."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import RLock


@dataclass(frozen=True, slots=True)
class ProgressSnapshot:
    run_id: str
    stage: str
    progress_percent: int | None
    cancellation_requested: bool
    updated_at: datetime


class CancellationToken:
    def __init__(self) -> None:
        self._lock = RLock()
        self._requested = False

    def request_cancel(self) -> bool:
        """Request cancellation; returns true only for the first request."""
        with self._lock:
            if self._requested:
                return False
            self._requested = True
            return True

    @property
    def is_cancelled(self) -> bool:
        with self._lock:
            return self._requested

    @property
    def cancelled(self) -> bool:
        return self.is_cancelled

    def raise_if_cancelled(self) -> None:
        if self.is_cancelled:
            raise InterruptedError("cancellation requested")


class ProgressPublisher:
    def __init__(self) -> None:
        self._lock = RLock()
        self._snapshots: dict[str, ProgressSnapshot] = {}
        self._tokens: dict[str, CancellationToken] = {}
        self._subscribers: dict[str, dict[int, Callable[[ProgressSnapshot], None]]] = {}
        self._next_subscription = 0

    def publish(
        self, run_id: str, stage: str, progress_percent: int | None = None
    ) -> ProgressSnapshot:
        if progress_percent is not None and not 0 <= progress_percent <= 100:
            raise ValueError("progress_percent must be between 0 and 100")
        with self._lock:
            token = self._tokens.setdefault(run_id, CancellationToken())
            snapshot = ProgressSnapshot(
                run_id=run_id,
                stage=stage,
                progress_percent=progress_percent,
                cancellation_requested=token.is_cancelled,
                updated_at=datetime.now(UTC),
            )
            self._snapshots[run_id] = snapshot
            subscribers = tuple(self._subscribers.get(run_id, {}).values())
        for subscriber in subscribers:
            subscriber(snapshot)
        return snapshot

    def current(self, run_id: str) -> ProgressSnapshot | None:
        with self._lock:
            return self._snapshots.get(run_id)

    def cancellation_token(self, run_id: str) -> CancellationToken:
        with self._lock:
            return self._tokens.setdefault(run_id, CancellationToken())

    def request_cancel(self, run_id: str) -> bool:
        first_request = self.cancellation_token(run_id).request_cancel()
        if not first_request:
            return False
        with self._lock:
            current = self._snapshots.get(run_id)
        if current is not None:
            self.publish(run_id, current.stage, current.progress_percent)
        return first_request

    def subscribe(
        self, run_id: str, callback: Callable[[ProgressSnapshot], None]
    ) -> Callable[[], None]:
        with self._lock:
            subscription = self._next_subscription
            self._next_subscription += 1
            self._subscribers.setdefault(run_id, {})[subscription] = callback

        def unsubscribe() -> None:
            with self._lock:
                subscribers = self._subscribers.get(run_id)
                if subscribers is not None:
                    subscribers.pop(subscription, None)

        return unsubscribe

    async def subscribe_async(self, run_id: str) -> AsyncIterator[ProgressSnapshot]:
        """Yield snapshots through an async adapter suitable for SSE responses.

        The callback is registered before the current snapshot is read.  This can
        intentionally yield a duplicate at the subscription boundary, but never
        loses a progress update while a consumer reconnects.
        """
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[ProgressSnapshot] = asyncio.Queue()

        def enqueue(snapshot: ProgressSnapshot) -> None:
            loop.call_soon_threadsafe(queue.put_nowait, snapshot)

        unsubscribe = self.subscribe(run_id, enqueue)
        current = self.current(run_id)
        if current is not None:
            queue.put_nowait(current)
        try:
            while True:
                yield await queue.get()
        finally:
            unsubscribe()

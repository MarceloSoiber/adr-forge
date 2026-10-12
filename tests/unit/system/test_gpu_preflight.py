from __future__ import annotations

import multiprocessing
from pathlib import Path
from typing import Any

import pytest

from adr_forge.system.gpu_lease import GpuLease, GpuLeaseUnavailable, GpuPreflight
from adr_forge.system.progress import ProgressPublisher, ProgressSnapshot
from adr_forge.system.resources import GpuCapacity, GpuProcess


class FakeGpuProbe:
    def __init__(self, capacity: GpuCapacity) -> None:
        self.capacity = capacity

    def gpu_capacity(self) -> GpuCapacity:
        return self.capacity


def _hold_lease(path: str, ready: Any, release: Any) -> None:
    with GpuLease(Path(path)):
        ready.set()
        release.wait(5)


def test_preflight_reports_insufficient_vram_without_secret_output() -> None:
    result = GpuPreflight(
        FakeGpuProbe(GpuCapacity(True, 12_000, 100, reason="token=should-not-appear")), 500
    ).check()

    assert result.ready is False
    assert result.blockers == ("insufficient_vram",)
    assert "token=should-not-appear" not in repr(result)


def test_preflight_reports_external_lm_studio_process() -> None:
    gpu = GpuCapacity(True, 12_000, 10_000, (GpuProcess(42, "LM Studio", 2_000),))

    result = GpuPreflight(FakeGpuProbe(gpu), 500).check()

    assert result.ready is False
    assert result.blockers == ("external_gpu_processes",)
    assert result.gpu.processes[0].name == "LM Studio"


def test_gpu_lease_excludes_another_local_process(tmp_path: Path) -> None:
    context = multiprocessing.get_context("spawn")
    ready, release = context.Event(), context.Event()
    process = context.Process(target=_hold_lease, args=(str(tmp_path / "gpu.lock"), ready, release))
    process.start()
    assert ready.wait(5)
    try:
        with pytest.raises(GpuLeaseUnavailable):
            GpuLease(tmp_path / "gpu.lock").acquire()
    finally:
        release.set()
        process.join(5)
    assert process.exitcode == 0


def test_lease_releases_after_context_exit(tmp_path: Path) -> None:
    path = tmp_path / "gpu.lock"
    with GpuLease(path):
        pass
    lease = GpuLease(path)
    lease.acquire()
    lease.release()


def test_progress_snapshot_and_cancellation_are_idempotent() -> None:
    publisher = ProgressPublisher()
    snapshots: list[ProgressSnapshot] = []
    unsubscribe = publisher.subscribe("run-1", snapshots.append)

    first = publisher.publish("run-1", "generating", 30)
    assert publisher.request_cancel("run-1") is True
    assert publisher.request_cancel("run-1") is False
    current = publisher.current("run-1")
    unsubscribe()

    assert first.cancellation_requested is False
    assert current is not None and current.cancellation_requested is True
    assert publisher.cancellation_token("run-1").is_cancelled is True
    assert len(snapshots) == 2

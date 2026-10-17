"""Cross-process GPU exclusion and read-only preflight checks."""

from __future__ import annotations

import fcntl
import json
import os
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, TextIO

from adr_forge.system.resources import GpuCapacity


class GpuCapacityProbe(Protocol):
    def gpu_capacity(self) -> GpuCapacity: ...


class GpuLeaseUnavailable(RuntimeError):
    """Raised when another ADR Forge process owns the local GPU lease."""


@dataclass(frozen=True, slots=True)
class GpuLeaseOwner:
    pid: int
    process_start_time: int | None


@dataclass(frozen=True, slots=True)
class PreflightResult:
    ready: bool
    blockers: tuple[str, ...]
    gpu: GpuCapacity


class GpuLease:
    """An advisory OS file lock; a PID file alone is intentionally not trusted."""

    def __init__(self, lock_path: Path) -> None:
        self._path = lock_path
        self._handle: TextIO | None = None
        self._token: str | None = None

    def acquire(self) -> None:
        if self._handle is not None:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        handle = self._path.open("a+", encoding="utf-8")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            handle.close()
            raise GpuLeaseUnavailable("gpu lease is held by another process") from exc
        token = secrets.token_urlsafe(16)
        handle.seek(0)
        handle.truncate()
        json.dump(
            {
                "pid": os.getpid(),
                "process_start_time": _process_start_time(),
                "ownership_token": token,
            },
            handle,
            separators=(",", ":"),
        )
        handle.flush()
        os.fsync(handle.fileno())
        self._handle = handle
        self._token = token

    def release(self) -> None:
        handle = self._handle
        if handle is None:
            return
        try:
            handle.seek(0)
            try:
                metadata = json.load(handle)
            except (ValueError, OSError):
                metadata = {}
            if metadata.get("ownership_token") == self._token:
                handle.seek(0)
                handle.truncate()
                handle.flush()
                os.fsync(handle.fileno())
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()
            self._handle = None
            self._token = None

    def __enter__(self) -> GpuLease:
        self.acquire()
        return self

    def __exit__(self, *_: object) -> None:
        self.release()

    @property
    def acquired(self) -> bool:
        return self._handle is not None

    def owner(self) -> GpuLeaseOwner | None:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            return GpuLeaseOwner(
                pid=int(data["pid"]), process_start_time=data.get("process_start_time")
            )
        except (OSError, ValueError, KeyError, TypeError):
            return None


class GpuPreflight:
    def __init__(self, probe: GpuCapacityProbe, minimum_free_vram_bytes: int) -> None:
        self._probe = probe
        self._minimum_free_vram_bytes = minimum_free_vram_bytes

    def check(self) -> PreflightResult:
        observed = self._probe.gpu_capacity()
        # Probes must be able to carry an operational reason internally, but public
        # diagnostics never reflect arbitrary driver or command output.
        gpu = GpuCapacity(
            available=observed.available,
            total_vram_bytes=observed.total_vram_bytes,
            free_vram_bytes=observed.free_vram_bytes,
            processes=observed.processes,
            reason=(None if observed.available else "gpu diagnostics unavailable"),
        )
        blockers: list[str] = []
        if not gpu.available:
            blockers.append("gpu_unavailable")
        elif gpu.free_vram_bytes is None or gpu.free_vram_bytes < self._minimum_free_vram_bytes:
            blockers.append("insufficient_vram")
        # Desktop applications routinely hold a small CUDA allocation.  They
        # cannot meaningfully compete with a local model, whereas an LLM does.
        if any(process.used_vram_bytes >= 1024**3 for process in gpu.processes):
            blockers.append("external_gpu_processes")
        return PreflightResult(not blockers, tuple(blockers), gpu)


def _process_start_time() -> int | None:
    try:
        return int(Path("/proc/self/stat").read_text(encoding="ascii").split()[21])
    except (OSError, ValueError, IndexError):
        return None

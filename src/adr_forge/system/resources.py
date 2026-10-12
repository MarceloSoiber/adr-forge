"""Sanitized, read-only observations of the local machine.

The probe deliberately exposes capacities rather than command output or process command lines.
It is therefore safe to use in the API and ``doctor`` output.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class DiskCapacity:
    """Filesystem capacity in bytes, without exposing the queried path."""

    total_bytes: int | None
    free_bytes: int | None
    available: bool
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class MemoryCapacity:
    total_bytes: int | None
    available_bytes: int | None
    available: bool
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class GpuProcess:
    pid: int
    name: str
    used_vram_bytes: int | None


@dataclass(frozen=True, slots=True)
class GpuCapacity:
    available: bool
    total_vram_bytes: int | None
    free_vram_bytes: int | None
    processes: tuple[GpuProcess, ...] = ()
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class ResourceSnapshot:
    disk: DiskCapacity
    memory: MemoryCapacity
    gpu: GpuCapacity


class HostResourceProbe:
    """Read host capacity without changing host state or managing processes."""

    def disk_capacity(self, path: Path) -> DiskCapacity:
        try:
            # Diagnostics are read-only: query the nearest existing parent rather
            # than creating a configured artifact directory just to inspect it.
            target = path
            while not target.exists() and target != target.parent:
                target = target.parent
            usage = shutil.disk_usage(target)
        except OSError:
            return DiskCapacity(None, None, False, "disk capacity unavailable")
        return DiskCapacity(usage.total, usage.free, True)

    def free_bytes(self, path: Path) -> int:
        """Implement the shared disk-capacity port for artifact services."""
        capacity = self.disk_capacity(path)
        if capacity.free_bytes is None:
            raise OSError(capacity.reason or "disk capacity unavailable")
        return capacity.free_bytes

    def memory_capacity(self) -> MemoryCapacity:
        try:
            values: dict[str, int] = {}
            for line in Path("/proc/meminfo").read_text(encoding="ascii").splitlines():
                key, value = line.split(":", 1)
                values[key] = int(value.split()[0]) * 1024
            return MemoryCapacity(values["MemTotal"], values["MemAvailable"], True)
        except (OSError, KeyError, ValueError, IndexError):
            return MemoryCapacity(None, None, False, "memory capacity unavailable")

    def gpu_capacity(self) -> GpuCapacity:
        executable = shutil.which("nvidia-smi")
        if executable is None:
            return GpuCapacity(False, None, None, reason="nvidia-smi unavailable")
        try:
            gpu_rows = self._nvidia_smi(
                executable, "--query-gpu=memory.total,memory.free", "csv,noheader,nounits"
            )
            totals, free = zip(*(self._parse_memory_row(row) for row in gpu_rows), strict=True)
            processes = tuple(
                self._parse_process(row)
                for row in self._nvidia_smi(
                    executable,
                    "--query-compute-apps=pid,process_name,used_memory",
                    "csv,noheader,nounits",
                )
                if row.strip()
            )
        except (OSError, ValueError, subprocess.SubprocessError):
            return GpuCapacity(False, None, None, reason="gpu diagnostics unavailable")
        return GpuCapacity(True, sum(totals), sum(free), processes)

    def snapshot(self, disk_path: Path) -> ResourceSnapshot:
        return ResourceSnapshot(
            disk=self.disk_capacity(disk_path),
            memory=self.memory_capacity(),
            gpu=self.gpu_capacity(),
        )

    @staticmethod
    def _nvidia_smi(executable: str, query: str, fmt: str) -> tuple[str, ...]:
        completed = subprocess.run(  # noqa: S603
            [executable, query, f"--format={fmt}"],
            capture_output=True,
            check=True,
            encoding="utf-8",
            errors="replace",
            timeout=2,
        )
        return tuple(line for line in completed.stdout.splitlines() if line.strip())

    @staticmethod
    def _parse_memory_row(row: str) -> tuple[int, int]:
        total, free = (int(value.strip()) * 1024 * 1024 for value in row.split(",", maxsplit=1))
        return total, free

    @staticmethod
    def _parse_process(row: str) -> GpuProcess:
        pid, name, used = (value.strip() for value in row.split(",", maxsplit=2))
        # A process name is useful operational metadata; never retain its command line or arguments.
        return GpuProcess(
            pid=int(pid),
            name=os.path.basename(name)[:120],
            used_vram_bytes=int(used) * 1024 * 1024,
        )

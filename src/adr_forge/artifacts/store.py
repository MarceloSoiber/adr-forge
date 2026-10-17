"""Safe, content-addressed filesystem storage for artifacts."""

from __future__ import annotations

import asyncio
import hashlib
import os
import re
from pathlib import Path

_DIGEST = re.compile(r"^[0-9a-f]{64}$")


class ArtifactStoreError(ValueError):
    """Raised when an artifact operation would violate storage safety."""


class ArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self._temporary = self.root / ".tmp"

    def path_for(self, sha256: str) -> Path:
        if not _DIGEST.fullmatch(sha256):
            raise ArtifactStoreError("artifact sha256 must be 64 lowercase hexadecimal characters")
        path = self.root / sha256[:2] / sha256[2:4] / sha256
        self._assert_under_root(path)
        return path

    def normalize_relative_path(self, value: str) -> str:
        if "\\" in value:
            raise ArtifactStoreError("artifact path must use safe POSIX separators")
        candidate = Path(value)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise ArtifactStoreError("artifact path must remain below the artifact root")
        normalized = Path(*(part for part in candidate.parts if part not in ("", ".")))
        if not normalized.parts:
            raise ArtifactStoreError("artifact path cannot be empty")
        self._assert_under_root(self.root / normalized)
        return normalized.as_posix()

    async def put_bytes(self, content: bytes) -> tuple[str, int, str]:
        return await asyncio.to_thread(self._put_bytes, content)

    def _put_bytes(self, content: bytes) -> tuple[str, int, str]:
        self.root.mkdir(parents=True, exist_ok=True)
        self._temporary.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256(content).hexdigest()
        target = self.path_for(digest)
        relative = target.relative_to(self.root).as_posix()
        if target.exists():
            return digest, len(content), relative
        temporary = self._temporary / f"{digest}.{os.getpid()}.part"
        try:
            with temporary.open("xb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        return digest, len(content), relative

    async def read_bytes(self, relative_path: str) -> bytes:
        path = self.root / self.normalize_relative_path(relative_path)
        self._assert_under_root(path)
        return await asyncio.to_thread(path.read_bytes)

    async def remove(self, relative_path: str) -> bool:
        path = self.root / self.normalize_relative_path(relative_path)
        self._assert_under_root(path)
        return await asyncio.to_thread(self._unlink, path)

    @staticmethod
    def _unlink(path: Path) -> bool:
        if not path.exists():
            return False
        path.unlink()
        return True

    async def reconcile_temporary(self) -> int:
        if not self._temporary.exists():
            return 0
        count = 0
        for path in self._temporary.glob("*.part"):
            if path.is_file():
                await asyncio.to_thread(path.unlink)
                count += 1
        return count

    def _assert_under_root(self, candidate: Path) -> None:
        try:
            candidate.resolve().relative_to(self.root)
        except ValueError as exc:
            raise ArtifactStoreError("artifact path must remain below the artifact root") from exc

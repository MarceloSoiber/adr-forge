"""Verified, non-overwriting SQLite online backup support."""

from __future__ import annotations

import os
import sqlite3
import tempfile
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from adr_forge.shared.hashing import canonical_json_bytes
from adr_forge.shared.time import utc_now

MANIFEST_VERSION = 1


class BackupError(RuntimeError):
    """Raised when a backup cannot be safely created or verified."""


@dataclass(frozen=True)
class DatabaseBackupManifest:
    """Independent metadata needed to verify a published SQLite backup."""

    created_at: str
    schema_revision: str
    database_size_bytes: int
    database_sha256: str
    application_version: str
    manifest_version: int = MANIFEST_VERSION

    def as_dict(self) -> dict[str, int | str]:
        return {
            "application_version": self.application_version,
            "created_at": self.created_at,
            "database_sha256": self.database_sha256,
            "database_size_bytes": self.database_size_bytes,
            "manifest_version": self.manifest_version,
            "schema_revision": self.schema_revision,
        }


@dataclass(frozen=True)
class DatabaseBackupResult:
    """The two independently usable files published by one backup operation."""

    database_path: Path
    manifest_path: Path
    manifest: DatabaseBackupManifest


def create_sqlite_backup(
    source_path: Path,
    output_path: Path,
    *,
    application_version: str,
) -> DatabaseBackupResult:
    """Publish a verified online SQLite backup and canonical sidecar manifest.

    SQLite's backup API takes a consistent snapshot even when the source uses WAL.
    Both published names are non-overwriting; failed publication removes only files
    created by this invocation.
    """

    source = source_path.resolve(strict=True)
    output = output_path.resolve(strict=False)
    manifest_path = output.with_name(f"{output.name}.manifest.json")
    if not source.is_file():
        raise BackupError("configured live database is not a file")
    if source == output:
        raise BackupError("backup destination must not be the live database")
    if output.exists() or manifest_path.exists():
        raise BackupError("backup output or manifest already exists")

    output.parent.mkdir(parents=True, exist_ok=True)
    database_temp = _temporary_sibling(output)
    manifest_temp = _temporary_sibling(manifest_path)
    published_database = False
    try:
        _copy_online(source, database_temp)
        schema_revision = _verify_copy(database_temp)
        manifest = DatabaseBackupManifest(
            created_at=utc_now().isoformat().replace("+00:00", "Z"),
            schema_revision=schema_revision,
            database_size_bytes=database_temp.stat().st_size,
            database_sha256=_file_sha256(database_temp),
            application_version=application_version,
        )
        manifest_temp.write_bytes(canonical_json_bytes(manifest.as_dict()))
        _publish_without_overwrite(database_temp, output)
        published_database = True
        _publish_without_overwrite(manifest_temp, manifest_path)
        return DatabaseBackupResult(output, manifest_path, manifest)
    except Exception as exc:
        if published_database:
            output.unlink(missing_ok=True)
        if isinstance(exc, BackupError):
            raise
        raise BackupError("backup creation or publication failed") from exc
    finally:
        database_temp.unlink(missing_ok=True)
        manifest_temp.unlink(missing_ok=True)


def _temporary_sibling(destination: Path) -> Path:
    descriptor, raw_path = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    os.close(descriptor)
    return Path(raw_path)


def _copy_online(source_path: Path, destination_path: Path) -> None:
    with sqlite3.connect(source_path) as source, sqlite3.connect(destination_path) as destination:
        source.backup(destination)


def _verify_copy(path: Path) -> str:
    with sqlite3.connect(path) as connection:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()
        if integrity != ("ok",):
            raise BackupError("backup integrity check failed")
        try:
            revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()
        except sqlite3.DatabaseError as exc:
            raise BackupError("backup has no Alembic schema revision") from exc
    if revision is None or not isinstance(revision[0], str) or not revision[0]:
        raise BackupError("backup has no Alembic schema revision")
    return revision[0]


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as file:
        while chunk := file.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _publish_without_overwrite(temporary_path: Path, destination: Path) -> None:
    try:
        os.link(temporary_path, destination)
    except FileExistsError as exc:
        raise BackupError("backup output or manifest already exists") from exc

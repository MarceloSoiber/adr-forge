"""Integration tests for the non-overwriting SQLite backup workflow."""

from __future__ import annotations

import json
import sqlite3
from hashlib import sha256
from pathlib import Path

import pytest

from adr_forge.persistence.backup import BackupError, create_sqlite_backup


def _create_live_database(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
        connection.execute("INSERT INTO alembic_version VALUES ('0008_blind_evaluation')")
        connection.execute("CREATE TABLE evidence (value TEXT NOT NULL)")
        connection.execute("INSERT INTO evidence VALUES ('committed before backup')")
        connection.commit()


def test_creates_verified_online_backup_and_canonical_manifest(tmp_path: Path) -> None:
    source = tmp_path / "live.sqlite3"
    output = tmp_path / "backups" / "adr-forge.sqlite3"
    _create_live_database(source)

    result = create_sqlite_backup(source, output, application_version="0.1.0")

    assert result.database_path == output
    assert result.manifest_path == output.with_name("adr-forge.sqlite3.manifest.json")
    assert result.manifest.schema_revision == "0008_blind_evaluation"
    assert result.manifest.database_size_bytes == output.stat().st_size
    assert result.manifest.database_sha256 == sha256(output.read_bytes()).hexdigest()
    assert json.loads(result.manifest_path.read_text(encoding="utf-8")) == result.manifest.as_dict()

    with sqlite3.connect(output) as restored:
        assert restored.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert restored.execute("SELECT value FROM evidence").fetchone() == (
            "committed before backup",
        )


@pytest.mark.parametrize("existing", ["backup", "manifest"])
def test_refuses_to_overwrite_any_published_backup_output(tmp_path: Path, existing: str) -> None:
    source = tmp_path / "live.sqlite3"
    output = tmp_path / "backup.sqlite3"
    _create_live_database(source)
    existing_path = (
        output if existing == "backup" else output.with_name("backup.sqlite3.manifest.json")
    )
    existing_path.write_text("do not replace", encoding="utf-8")

    with pytest.raises(BackupError, match="already exists"):
        create_sqlite_backup(source, output, application_version="0.1.0")

    assert existing_path.read_text(encoding="utf-8") == "do not replace"
    assert not output.exists() or existing == "backup"


def test_refuses_live_database_as_backup_destination(tmp_path: Path) -> None:
    source = tmp_path / "live.sqlite3"
    _create_live_database(source)

    with pytest.raises(BackupError, match="live database"):
        create_sqlite_backup(source, source, application_version="0.1.0")

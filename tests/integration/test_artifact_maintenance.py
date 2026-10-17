"""Integration coverage for catalog inspection and conservative artifact pruning."""

from __future__ import annotations

import asyncio
import sqlite3
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

from adr_forge.artifacts.repository import ArtifactRepository
from adr_forge.artifacts.service import ArtifactCapacityError, ArtifactMaintenance
from adr_forge.artifacts.store import ArtifactStore
from adr_forge.persistence.database import create_database_engine, create_session_factory
from adr_forge.shared.time import utc_now


@pytest.fixture
async def maintenance(tmp_path: Path):  # type: ignore[no-untyped-def]
    """Migrate an isolated catalog to head and expose its maintenance boundary."""
    database_path = tmp_path / "adr-forge.sqlite3"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{database_path}")
    await asyncio.to_thread(command.upgrade, config, "head")

    engine = create_database_engine(f"sqlite+aiosqlite:///{database_path}")
    repository = ArtifactRepository(create_session_factory(engine))
    store = ArtifactStore(tmp_path / "artifacts")
    try:
        yield ArtifactMaintenance(repository, store), repository, store, database_path
    finally:
        await engine.dispose()


async def _create_artifact(
    repository: ArtifactRepository,
    store: ArtifactStore,
    *,
    content: bytes,
    retention: str,
    created_at_offset: timedelta = timedelta(),
) -> str:
    digest, size, relative_path = await store.put_bytes(content)
    return await repository.create(
        kind="report",
        sha256=digest,
        relative_path=relative_path,
        size_bytes=size,
        media_type="text/plain",
        created_at=utc_now() + created_at_offset,
        retention=retention,
    )


async def test_migration_to_head_installs_prune_audit_table(maintenance: tuple) -> None:
    _service, _repository, _store, database_path = maintenance

    with sqlite3.connect(database_path) as connection:
        version = connection.execute("SELECT version_num FROM alembic_version").fetchone()
        audit_table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'artifact_prune_audits'"
        ).fetchone()

    assert version == ("0010_artifact_prune_audit",)
    assert audit_table == ("artifact_prune_audits",)


async def test_list_is_deterministic_and_read_only(maintenance: tuple) -> None:
    service, repository, store, _database_path = maintenance
    first_id = await _create_artifact(
        repository,
        store,
        content=b"first",
        retention="keep",
        created_at_offset=timedelta(seconds=-2),
    )
    second_id = await _create_artifact(
        repository,
        store,
        content=b"second",
        retention="prunable",
        created_at_offset=timedelta(seconds=-1),
    )

    first_listing = await service.list()
    second_listing = await service.list()

    assert [artifact.id for artifact in first_listing] == [first_id, second_id]
    assert second_listing == first_listing
    assert [artifact.id for artifact in await repository.list_catalog()] == [first_id, second_id]


async def test_prune_requires_explicit_confirmation(maintenance: tuple) -> None:
    service, repository, store, _database_path = maintenance
    artifact_id = await _create_artifact(
        repository, store, content=b"delete me", retention="prunable"
    )
    artifact = (await repository.list_catalog())[0]

    with pytest.raises(ArtifactCapacityError, match="requires --confirm"):
        await service.prune(confirmed=False)

    assert artifact.id == artifact_id
    assert await store.read_bytes(artifact.relative_path) == b"delete me"
    assert [row.id for row in await repository.list_catalog()] == [artifact_id]


async def test_prune_preserves_protected_items_and_audits_reclaimed_bytes(
    maintenance: tuple,
) -> None:
    service, repository, store, _database_path = maintenance
    keep_id = await _create_artifact(repository, store, content=b"keep", retention="keep")
    referenced_id = await _create_artifact(
        repository, store, content=b"referenced", retention="prunable"
    )
    await repository.reference(referenced_id, "test", uuid4())
    fresh_temporary_id = await _create_artifact(
        repository, store, content=b"fresh", retention="temporary"
    )
    prunable_id = await _create_artifact(
        repository, store, content=b"reclaim", retention="prunable"
    )
    expired_temporary_id = await _create_artifact(
        repository,
        store,
        content=b"expired",
        retention="temporary",
        created_at_offset=timedelta(days=-2),
    )
    before = {artifact.id: artifact for artifact in await repository.list_catalog()}

    report = await service.prune(confirmed=True)

    assert {result.artifact_id for result in report.results} == {prunable_id, expired_temporary_id}
    assert {result.reason for result in report.results} == {
        "unreferenced_prunable",
        "expired_temporary",
    }
    assert report.reclaimed_bytes == len(b"reclaim") + len(b"expired")
    assert {artifact.id for artifact in await repository.list_catalog()} == {
        keep_id,
        referenced_id,
        fresh_temporary_id,
    }
    for artifact_id in (keep_id, referenced_id, fresh_temporary_id):
        assert await store.read_bytes(before[artifact_id].relative_path)
    for artifact_id in (prunable_id, expired_temporary_id):
        assert not (store.root / before[artifact_id].relative_path).exists()

    engine = create_database_engine(f"sqlite+aiosqlite:///{_database_path}")
    try:
        async with engine.connect() as connection:
            audits = (
                await connection.execute(
                    text(
                        "SELECT artifact_id, reason, reclaimed_bytes FROM artifact_prune_audits "
                        "ORDER BY artifact_id"
                    )
                )
            ).all()
    finally:
        await engine.dispose()
    assert {(row.artifact_id, row.reason, row.reclaimed_bytes) for row in audits} == {
        (prunable_id, "unreferenced_prunable", len(b"reclaim")),
        (expired_temporary_id, "expired_temporary", len(b"expired")),
    }

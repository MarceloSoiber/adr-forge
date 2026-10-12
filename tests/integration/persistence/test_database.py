"""Integration tests for async SQLite persistence infrastructure."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

from adr_forge.persistence.database import create_database_engine, create_session_factory
from adr_forge.persistence.unit_of_work import UnitOfWork


@pytest.mark.asyncio
async def test_sqlite_engine_enables_wal_and_foreign_keys(tmp_path: Path) -> None:
    database_path = tmp_path / "adr-forge.sqlite3"
    engine = create_database_engine(f"sqlite+aiosqlite:///{database_path}")
    try:
        async with engine.connect() as connection:
            journal_mode = (await connection.execute(text("PRAGMA journal_mode"))).scalar_one()
            foreign_keys = (await connection.execute(text("PRAGMA foreign_keys"))).scalar_one()

        assert journal_mode == "wal"
        assert foreign_keys == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_unit_of_work_commits_and_rolls_back(tmp_path: Path) -> None:
    database_path = tmp_path / "adr-forge.sqlite3"
    engine = create_database_engine(f"sqlite+aiosqlite:///{database_path}")
    factory = create_session_factory(engine)
    try:
        async with engine.begin() as connection:
            await connection.execute(text("CREATE TABLE entries (value TEXT NOT NULL)"))

        async with UnitOfWork(factory) as unit_of_work:
            await unit_of_work.session.execute(text("INSERT INTO entries VALUES ('kept')"))

        with pytest.raises(RuntimeError):
            async with UnitOfWork(factory) as unit_of_work:
                await unit_of_work.session.execute(text("INSERT INTO entries VALUES ('discarded')"))
                raise RuntimeError("force rollback")

        async with factory() as session:
            values = (await session.execute(text("SELECT value FROM entries"))).scalars().all()
        assert values == ["kept"]
    finally:
        await engine.dispose()


def test_rejects_non_sqlite_database_urls() -> None:
    with pytest.raises(ValueError, match="SQLite"):
        create_database_engine("postgresql+asyncpg://example.invalid/adr_forge")


def test_initial_migration_uses_alembic_version_as_schema_authority(tmp_path: Path) -> None:
    database_path = tmp_path / "adr-forge.sqlite3"
    repository_root = Path(__file__).parents[3]
    config = Config()
    config.set_main_option("script_location", str(repository_root / "alembic"))
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{database_path}")

    command.upgrade(config, "0001_schema_version")

    with sqlite3.connect(database_path) as connection:
        version = connection.execute("SELECT version_num FROM alembic_version").fetchone()
    assert version == ("0001_schema_version",)

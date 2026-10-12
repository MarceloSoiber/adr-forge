"""Async SQLite database infrastructure for ADR Forge."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Protocol, cast

from sqlalchemy import event
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


class _DbapiCursor(Protocol):
    def execute(self, statement: str) -> object: ...

    def close(self) -> None: ...


class _SqliteConnection(Protocol):
    def cursor(self) -> _DbapiCursor: ...


def create_database_engine(database_url: str | URL) -> AsyncEngine:
    """Create an async SQLite engine with the required local safety pragmas.

    WAL permits concurrent readers while preserving SQLite's single-writer semantics.
    Foreign keys are enabled per connection because SQLite disables them by default.
    """

    url = make_url(database_url)
    if url.get_backend_name() != "sqlite":
        msg = "ADR Forge persistence currently supports SQLite only."
        raise ValueError(msg)

    engine = create_async_engine(url, future=True)

    @event.listens_for(engine.sync_engine, "connect")
    def configure_sqlite_connection(dbapi_connection: object, _connection_record: object) -> None:
        cursor = cast(_SqliteConnection, dbapi_connection).cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
        finally:
            cursor.close()

    return engine


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Build sessions that do not expire values after a successful transaction."""

    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)


@asynccontextmanager
async def session_scope(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Yield one session and guarantee it is closed after use.

    Transactional application work should use :class:`UnitOfWork`; this helper is
    intended for read-only operations and migration-adjacent diagnostics.
    """

    async with session_factory() as session:
        yield session

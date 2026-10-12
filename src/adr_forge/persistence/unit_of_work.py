"""Transaction boundary for application persistence operations."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class UnitOfWork:
    """Commit successful work atomically and roll back failures.

    A unit of work owns exactly one ``AsyncSession`` and transaction. Domain
    services may share its session with repositories so their metadata changes
    commit together.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None

    @property
    def session(self) -> AsyncSession:
        """Return the session while this unit of work is active."""

        if self._session is None:
            msg = "UnitOfWork.session is available only inside its context."
            raise RuntimeError(msg)
        return self._session

    async def __aenter__(self) -> UnitOfWork:
        self._session = self._session_factory()
        await self._session.begin()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: object | None,
    ) -> bool:
        session = self.session
        try:
            if exc_type is None:
                await session.commit()
            else:
                await session.rollback()
        finally:
            await session.close()
            self._session = None
        return False

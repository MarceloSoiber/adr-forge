"""Minimal SQL catalog for content-addressed artifact ownership."""

from __future__ import annotations

from datetime import datetime
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class ArtifactRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create_raw_output(
        self, *, sha256: str, relative_path: str, size_bytes: int, created_at: datetime
    ) -> str:
        """Return one durable catalog record for a raw model output digest."""
        async with self._session_factory.begin() as session:
            existing = await session.execute(
                text("SELECT id FROM artifacts WHERE sha256 = :sha256 AND kind = 'raw_output'"),
                {"sha256": sha256},
            )
            artifact_id = cast(str | None, existing.scalar_one_or_none())
            if artifact_id is not None:
                return str(artifact_id)
            artifact_id = str(uuid4())
            await session.execute(
                text(
                    """INSERT INTO artifacts (id, kind, relative_path, sha256, size_bytes,
                    media_type, created_at, retention)
                    VALUES (:id, 'raw_output', :relative_path, :sha256, :size_bytes,
                    'application/json', :created_at, 'keep')"""
                ),
                {
                    "id": artifact_id,
                    "relative_path": relative_path,
                    "sha256": sha256,
                    "size_bytes": size_bytes,
                    "created_at": created_at,
                },
            )
        return artifact_id

    async def create(
        self,
        *,
        kind: str,
        sha256: str,
        relative_path: str,
        size_bytes: int,
        media_type: str,
        created_at: datetime,
        retention: str = "keep",
    ) -> str:
        """Create or reuse a content-addressed artifact of an allowed catalog kind."""
        if kind not in {
            "raw_output",
            "retrieval_snapshot",
            "model",
            "adapter",
            "checkpoint",
            "report",
            "config",
            "log",
        }:
            raise ValueError("unsupported artifact kind")
        async with self._session_factory.begin() as session:
            existing = await session.execute(
                text("SELECT id FROM artifacts WHERE sha256 = :sha256 AND kind = :kind"),
                {"sha256": sha256, "kind": kind},
            )
            artifact_id = cast(str | None, existing.scalar_one_or_none())
            if artifact_id is not None:
                return str(artifact_id)
            artifact_id = str(uuid4())
            await session.execute(
                text(
                    """INSERT INTO artifacts (
                    id, kind, relative_path, sha256, size_bytes, media_type,
                    created_at, retention
                    ) VALUES (
                    :id, :kind, :relative_path, :sha256, :size_bytes, :media_type,
                    :created_at, :retention
                    )"""
                ),
                {
                    "id": artifact_id,
                    "kind": kind,
                    "relative_path": relative_path,
                    "sha256": sha256,
                    "size_bytes": size_bytes,
                    "media_type": media_type,
                    "created_at": created_at,
                    "retention": retention,
                },
            )
        return artifact_id

    async def reference(
        self, artifact_id: str | UUID, owner_type: str, owner_id: str | UUID
    ) -> None:
        async with self._session_factory.begin() as session:
            await session.execute(
                text(
                    """INSERT OR IGNORE INTO artifact_references
                    (artifact_id, owner_type, owner_id, created_at)
                    VALUES (:artifact_id, :owner_type, :owner_id, CURRENT_TIMESTAMP)"""
                ),
                {
                    "artifact_id": str(artifact_id),
                    "owner_type": owner_type,
                    "owner_id": str(owner_id),
                },
            )

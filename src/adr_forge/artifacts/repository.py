"""Minimal SQL catalog for content-addressed artifact ownership."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


@dataclass(frozen=True, slots=True)
class CatalogArtifact:
    id: str
    kind: str
    relative_path: str
    sha256: str
    size_bytes: int
    retention: str
    created_at: datetime
    reference_count: int


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

    async def list_catalog(self) -> list[CatalogArtifact]:
        """Return a deterministic, read-only artifact catalog view."""
        async with self._session_factory() as session:
            result = await session.execute(
                text(
                    """SELECT a.id, a.kind, a.relative_path, a.sha256, a.size_bytes, a.retention,
                    a.created_at, COUNT(r.artifact_id) AS reference_count
                    FROM artifacts a LEFT JOIN artifact_references r ON r.artifact_id = a.id
                    GROUP BY a.id ORDER BY a.created_at ASC, a.id ASC"""
                )
            )
            return [self._catalog_artifact(row) for row in result]

    @staticmethod
    def _catalog_artifact(row: object) -> CatalogArtifact:
        created_at = row.created_at  # type: ignore[attr-defined]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at).replace(tzinfo=UTC)
        return CatalogArtifact(
            id=str(row.id),  # type: ignore[attr-defined]
            kind=str(row.kind),  # type: ignore[attr-defined]
            relative_path=str(row.relative_path),  # type: ignore[attr-defined]
            sha256=str(row.sha256),  # type: ignore[attr-defined]
            size_bytes=int(row.size_bytes),  # type: ignore[attr-defined]
            retention=str(row.retention),  # type: ignore[attr-defined]
            created_at=created_at,
            reference_count=int(row.reference_count),  # type: ignore[attr-defined]
        )

    async def record_prune(
        self,
        artifact: CatalogArtifact,
        *,
        operation_id: str,
        reason: str,
        reclaimed_bytes: int,
        pruned_at: datetime,
    ) -> None:
        """Remove a catalog record and write its successful cleanup audit atomically."""
        async with self._session_factory.begin() as session:
            references = await session.scalar(
                text("SELECT COUNT(*) FROM artifact_references WHERE artifact_id = :id"),
                {"id": artifact.id},
            )
            if references != 0:
                raise ValueError("artifact became referenced during prune")
            await session.execute(text("DELETE FROM artifacts WHERE id = :id"), {"id": artifact.id})
            await session.execute(
                text(
                    """INSERT INTO artifact_prune_audits
                    (id, operation_id, artifact_id, artifact_kind, relative_path, sha256, reason,
                    reclaimed_bytes, pruned_at)
                    VALUES (:id, :operation_id, :artifact_id, :artifact_kind, :relative_path,
                    :sha256, :reason, :reclaimed_bytes, :pruned_at)"""
                ),
                {
                    "id": str(uuid4()),
                    "operation_id": operation_id,
                    "artifact_id": artifact.id,
                    "artifact_kind": artifact.kind,
                    "relative_path": artifact.relative_path,
                    "sha256": artifact.sha256,
                    "reason": reason,
                    "reclaimed_bytes": reclaimed_bytes,
                    "pruned_at": pruned_at,
                },
            )

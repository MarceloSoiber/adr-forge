"""SQLite repository for immutable retrieval snapshot metadata."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from adr_forge.retrieval.models import RetrievalSnapshot


class RetrievalSnapshotRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_by_hash(self, content_hash: str) -> RetrievalSnapshot | None:
        async with self._session_factory() as session:
            row = (await session.execute(text("SELECT * FROM retrieval_snapshots WHERE content_hash = :hash"), {"hash": content_hash})).mappings().one_or_none()
        return self._from_row(dict(row)) if row is not None else None

    async def get(self, snapshot_id: str) -> RetrievalSnapshot | None:
        async with self._session_factory() as session:
            row = (await session.execute(text("SELECT * FROM retrieval_snapshots WHERE id = :id"), {"id": snapshot_id})).mappings().one_or_none()
        return self._from_row(dict(row)) if row is not None else None

    async def add(self, snapshot: RetrievalSnapshot) -> RetrievalSnapshot:
        existing = await self.get_by_hash(snapshot.content_hash or "")
        if existing is not None:
            if existing.canonical_json_bytes() != snapshot.canonical_json_bytes():
                raise ValueError("retrieval snapshot hash collision with different content")
            return existing
        if snapshot.artifact_id is None:
            raise ValueError("persisted retrieval snapshot requires an artifact")
        async with self._session_factory.begin() as session:
            await session.execute(text("""INSERT INTO retrieval_snapshots
                (id, schema_version, provider, provider_version, embedding_model, embedding_version,
                 query, filters_json, chunks_json, content_hash, artifact_id, created_at)
                VALUES (:id, :schema_version, :provider, :provider_version, :embedding_model,
                 :embedding_version, :query, :filters_json, :chunks_json, :content_hash, :artifact_id, :created_at)"""), {
                "id": str(snapshot.id), "schema_version": snapshot.schema_version,
                "provider": snapshot.provider, "provider_version": snapshot.provider_version,
                "embedding_model": snapshot.embedding.model, "embedding_version": snapshot.embedding.version,
                "query": snapshot.query, "filters_json": json.dumps(snapshot.filters.model_dump(mode="json")),
                "chunks_json": json.dumps([chunk.model_dump(mode="json") for chunk in snapshot.chunks]),
                "content_hash": snapshot.content_hash, "artifact_id": str(snapshot.artifact_id),
                "created_at": snapshot.created_at,
            })
        return snapshot

    @staticmethod
    def _from_row(row: dict[str, Any]) -> RetrievalSnapshot:
        return RetrievalSnapshot.model_validate({
            "id": row["id"], "schema_version": row["schema_version"], "provider": row["provider"],
            "provider_version": row["provider_version"],
            "embedding_model": row["embedding_model"],
            "embedding_version": row["embedding_version"],
            "query": row["query"], "filters": json.loads(row["filters_json"]),
            "chunks": json.loads(row["chunks_json"]),
            "content_hash": row["content_hash"], "artifact_id": row["artifact_id"], "created_at": row["created_at"],
        })

"""Snapshot creation that freezes provider evidence before comparable runs."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from adr_forge.artifacts.repository import ArtifactRepository
from adr_forge.artifacts.store import ArtifactStore
from adr_forge.retrieval.models import RetrievalSnapshot
from adr_forge.retrieval.repository import RetrievalSnapshotRepository


class RetrievalService:
    def __init__(
        self,
        repository: RetrievalSnapshotRepository,
        artifacts: ArtifactRepository,
        store: ArtifactStore,
    ) -> None:
        self._repository = repository
        self._artifacts = artifacts
        self._store = store

    async def freeze(self, snapshot: RetrievalSnapshot) -> RetrievalSnapshot:
        existing = await self._repository.get_by_hash(snapshot.content_hash or "")
        if existing is not None:
            return existing
        data = snapshot.canonical_json_bytes()
        sha256, size, path = await self._store.put_bytes(data)
        artifact_id = await self._artifacts.create(
            kind="retrieval_snapshot",
            sha256=sha256,
            relative_path=path,
            size_bytes=size,
            media_type="application/json",
            created_at=datetime.now(UTC),
            retention="keep",
        )
        persisted = snapshot.model_copy(update={"artifact_id": UUID(artifact_id)})
        try:
            stored = await self._repository.add(persisted)
        except IntegrityError:
            # Another writer published the same canonical snapshot first.  The
            # content-addressed object may remain unreferenced for reconciliation,
            # but callers must converge on the already committed identity.
            stored = await self._repository.get_by_hash(snapshot.content_hash or "")
            if stored is None:
                raise
        if stored.artifact_id is None:
            raise ValueError("persisted retrieval snapshot requires an artifact")
        await self._artifacts.reference(stored.artifact_id, "retrieval_snapshot", stored.id)
        return stored

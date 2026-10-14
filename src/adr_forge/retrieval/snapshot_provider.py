"""Replay retrieval from an immutable stored snapshot or reviewed fixture file."""

from __future__ import annotations

from pathlib import Path

from adr_forge.retrieval.models import RetrievalSnapshot


class SnapshotRetrievalProvider:
    def __init__(self, snapshot: RetrievalSnapshot) -> None:
        self._snapshot = snapshot

    async def retrieve(self, query: str, **_: object) -> RetrievalSnapshot:
        if query != self._snapshot.query:
            raise ValueError("snapshot provider only serves its frozen query")
        return self._snapshot

    @classmethod
    def from_file(cls, path: Path) -> SnapshotRetrievalProvider:
        """Load only a previously canonicalized snapshot, never an arbitrary query result."""
        return cls(RetrievalSnapshot.from_canonical_json(path.read_bytes()))

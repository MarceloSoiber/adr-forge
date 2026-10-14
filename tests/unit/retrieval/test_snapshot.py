"""Canonical retrieval snapshots retain every comparison-relevant variable."""

from __future__ import annotations

from itertools import permutations

import pytest

from adr_forge.retrieval.models import RetrievalChunk, RetrievalFilters, RetrievalSnapshot


def _snapshot(
    *, chunks: list[RetrievalChunk] | None = None, **changes: object
) -> RetrievalSnapshot:
    values: dict[str, object] = {
        "provider": "fixture",
        "provider_version": "fixture-v1",
        "query": "avaliar processamento assíncrono",
        "filters": RetrievalFilters(limit=8, category_ids=[1]),
        "embedding_model": "embedder",
        "embedding_version": "revision-1",
        "chunks": chunks
        or [
            RetrievalChunk(
                source_id="source-a",
                chunk_id="42",
                title="Referência",
                uri="local://reference",
                location={"page": 7, "section": "Trade-offs", "chunk_index": 3},
                content="Texto exato recuperado.",
                score=0.82,
                match_reasons=["vector", "text"],
                rank=1,
            ),
            RetrievalChunk(
                source_id="source-b",
                chunk_id="43",
                title="Segunda referência",
                uri="local://second",
                location={"page": 9, "section": "Operação", "chunk_index": 1},
                content="Outro texto exato.",
                score=0.71,
                match_reasons=["text"],
                rank=2,
            ),
        ],
    }
    values.update(changes)
    return RetrievalSnapshot(**values)


def test_canonical_snapshot_is_key_order_independent_but_provider_order_significant() -> None:
    original = _snapshot()
    reordered_location = _snapshot(
        chunks=[
            original.chunks[0].model_copy(
                update={"location": {"chunk_index": 3, "section": "Trade-offs", "page": 7}}
            ),
            original.chunks[1],
        ]
    )
    assert reordered_location.content_hash == original.content_hash

    for ordered_chunks in permutations(original.chunks):
        candidate = _snapshot(chunks=list(ordered_chunks))
        if list(ordered_chunks) == original.chunks:
            assert candidate.content_hash == original.content_hash
        else:
            assert candidate.content_hash != original.content_hash


@pytest.mark.parametrize(
    "change",
    [
        {"query": "uma consulta diferente"},
        {"filters": RetrievalFilters(limit=4, category_ids=[1])},
        {"provider": "knowledge_hub"},
        {"provider_version": "fixture-v2"},
        {"embedding_model": "another-embedder"},
        {"embedding_version": "revision-2"},
    ],
)
def test_snapshot_hash_includes_request_provider_and_embedding_identity(
    change: dict[str, object],
) -> None:
    assert _snapshot(**change).content_hash != _snapshot().content_hash


@pytest.mark.parametrize(
    "chunk_change",
    [
        {"content": "Texto alterado."},
        {"score": 0.81},
        {"match_reasons": ["text", "vector"]},
        {"rank": 3},
    ],
)
def test_snapshot_hash_includes_each_exact_chunk_field(chunk_change: dict[str, object]) -> None:
    original = _snapshot()
    changed = _snapshot(
        chunks=[original.chunks[0].model_copy(update=chunk_change), original.chunks[1]]
    )
    assert changed.content_hash != original.content_hash


def test_reuse_never_mutates_stored_snapshot_or_canonical_artifact_bytes() -> None:
    snapshot = _snapshot()
    canonical_bytes = snapshot.canonical_json_bytes()
    reused = RetrievalSnapshot.from_canonical_json(canonical_bytes)

    assert reused.content_hash == snapshot.content_hash
    assert reused.canonical_json_bytes() == canonical_bytes
    assert snapshot.chunks[0].content == "Texto exato recuperado."


def test_snapshot_rejects_non_finite_scores_duplicate_ranks_and_missing_required_evidence() -> None:
    original = _snapshot()
    with pytest.raises(ValueError):
        _snapshot(chunks=[original.chunks[0].model_copy(update={"score": float("nan")})])
    with pytest.raises(ValueError):
        _snapshot(chunks=[original.chunks[0], original.chunks[1].model_copy(update={"rank": 1})])
    with pytest.raises(ValueError):
        _snapshot(chunks=[original.chunks[0].model_copy(update={"content": ""})])

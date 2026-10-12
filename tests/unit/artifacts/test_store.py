from pathlib import Path

import pytest

from adr_forge.artifacts.store import ArtifactStore, ArtifactStoreError


@pytest.mark.asyncio
async def test_store_is_content_addressed_and_reconciles_partials(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    first = await store.put_bytes(b"stable")
    second = await store.put_bytes(b"stable")
    assert first == second
    assert await store.read_bytes(first[2]) == b"stable"
    temporary = tmp_path / ".tmp"
    temporary.mkdir(exist_ok=True)
    (temporary / "abandoned.part").write_bytes(b"partial")
    assert await store.reconcile_temporary() == 1


def test_store_rejects_traversal(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    with pytest.raises(ArtifactStoreError):
        store.normalize_relative_path("../secret")

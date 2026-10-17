"""Adversarial path checks for the artifact-store trust boundary."""

from __future__ import annotations

from pathlib import Path

import pytest

from adr_forge.artifacts.store import ArtifactStore, ArtifactStoreError


def test_artifact_paths_reject_absolute_traversal_and_ambiguous_separators(tmp_path: Path) -> None:
    candidates = [
        (tmp_path.parent / "outside-artifact").resolve().as_posix(),
        "../outside-artifact",
        "nested/../../outside-artifact",
        r"..\outside-artifact",
        r"nested\..\..\outside-artifact",
        ".",
        "",
    ]
    store = ArtifactStore(tmp_path / "artifacts")
    for candidate in candidates:
        with pytest.raises(ArtifactStoreError):
            store.normalize_relative_path(candidate)


@pytest.mark.asyncio
async def test_artifact_store_rejects_symlink_escape_on_read_and_remove(tmp_path: Path) -> None:
    root = tmp_path / "artifacts"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    secret = outside / "secret.txt"
    secret.write_text("must stay outside")
    (root / "linked").symlink_to(outside, target_is_directory=True)
    store = ArtifactStore(root)

    with pytest.raises(ArtifactStoreError):
        await store.read_bytes("linked/secret.txt")
    with pytest.raises(ArtifactStoreError):
        await store.remove("linked/secret.txt")
    assert secret.read_text() == "must stay outside"

"""Strategy discovery must not expose mutable Qwen identities."""

from __future__ import annotations

import pytest

from adr_forge.strategies.qwen_runtime import QwenRuntime
from adr_forge.strategies.registry import default_registry

_REVISION = "cdbee75f17c01a7cc42f958dc650907174af0554"


@pytest.mark.parametrize("revision", [None, "", "main", "MAIN", "a" * 39])
def test_registry_rejects_missing_or_mutable_qwen_revision(revision: str | None) -> None:
    with pytest.raises(ValueError, match="model_revision"):
        default_registry(model_revision=revision)


def test_registry_exposes_the_exact_immutable_qwen_revision() -> None:
    registry = default_registry(model_revision=_REVISION)

    assert registry.get("qwen3-4b-baseline", "1").model_revision == _REVISION  # type: ignore[union-attr]


@pytest.mark.parametrize("revision", ["main", "", "a" * 39])
def test_qwen_runtime_rejects_non_immutable_revision_before_ml_import(revision: str) -> None:
    with pytest.raises(ValueError, match="model_revision"):
        QwenRuntime(revision=revision)

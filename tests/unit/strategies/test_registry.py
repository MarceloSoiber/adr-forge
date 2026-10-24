"""Strategy discovery must not expose mutable Qwen identities."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from adr_forge.shared.hashing import canonical_json
from adr_forge.strategies.qwen_runtime import QwenRuntime
from adr_forge.strategies.registry import default_registry

_REVISION = "cdbee75f17c01a7cc42f958dc650907174af0554"


def _adapter_manifest(tmp_path: Path) -> Path:
    adapter = tmp_path / "adapter"
    adapter.mkdir()
    payload = b"adapter"
    (adapter / "adapter_model.safetensors").write_bytes(payload)
    files = [
        {
            "path": "adapter_model.safetensors",
            "size": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
    ]
    manifest = {
        "model": {"id": "Qwen/Qwen3-4B-Instruct-2507", "revision": _REVISION},
        "adapter": {
            "files": files,
            "sha256": hashlib.sha256(canonical_json(files).encode()).hexdigest(),
        },
    }
    path = tmp_path / "adapter-manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


@pytest.mark.parametrize("revision", [None, "", "main", "MAIN", "a" * 39])
def test_registry_rejects_missing_or_mutable_qwen_revision(revision: str | None) -> None:
    with pytest.raises(ValueError, match="model_revision"):
        default_registry(model_revision=revision)


def test_registry_exposes_the_exact_immutable_qwen_revision() -> None:
    registry = default_registry(model_revision=_REVISION)

    assert registry.get("qwen3-4b-baseline", "1").model_revision == _REVISION  # type: ignore[union-attr]


def test_registry_activates_qwen_baseline_only_with_lm_studio_configuration() -> None:
    registry = default_registry(
        model_revision=_REVISION,
        lm_studio_base_url="http://192.168.15.111:1234",
        lm_studio_model_id="qwen_qwen3-4b-instruct-2507",
    )

    strategy = registry.get("qwen3-4b-baseline", "1")
    assert strategy is not None
    assert strategy.model_id == "qwen_qwen3-4b-instruct-2507"
    assert strategy.runtime_kind == "openai_compatible"
    assert strategy.availability.available is True


def test_registry_activates_verified_adapter_with_available_runtime(tmp_path: Path) -> None:
    manifest = _adapter_manifest(tmp_path)

    registry = default_registry(
        model_revision=_REVISION,
        adapter_manifest_path=manifest,
        adapter_runtime_available=True,
    )

    strategy = registry.get("fine-tuned", "1")
    assert strategy is not None
    assert strategy.availability.available is True
    assert strategy.adapter_path == manifest.parent / "adapter"


@pytest.mark.parametrize("revision", ["main", "", "a" * 39])
def test_qwen_runtime_rejects_non_immutable_revision_before_ml_import(revision: str) -> None:
    with pytest.raises(ValueError, match="model_revision"):
        QwenRuntime(revision=revision)

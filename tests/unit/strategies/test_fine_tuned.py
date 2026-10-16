from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from adr_forge.shared.hashing import canonical_json
from adr_forge.strategies.fine_tuned import AdapterVerificationError, verify_adapter_manifest


def _manifest(tmp_path: Path) -> Path:
    adapter = tmp_path / "adapter"
    adapter.mkdir()
    payload = b"adapter"
    (adapter / "model.safetensors").write_bytes(payload)
    files = [
        {
            "path": "model.safetensors",
            "size": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
    ]
    data = {
        "model": {"id": "Qwen/Qwen3-4B-Instruct-2507", "revision": "pinned"},
        "adapter": {
            "files": files,
            "sha256": hashlib.sha256(canonical_json(files).encode()).hexdigest(),
        },
    }
    path = tmp_path / "adapter-manifest.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_verified_adapter_requires_every_file_and_exact_base_identity(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    verified = verify_adapter_manifest(
        manifest, expected_model_id="Qwen/Qwen3-4B-Instruct-2507", expected_model_revision="pinned"
    )
    assert verified.aggregate_sha256
    with pytest.raises(AdapterVerificationError, match="revision"):
        verify_adapter_manifest(
            manifest,
            expected_model_id="Qwen/Qwen3-4B-Instruct-2507",
            expected_model_revision="other",
        )
    (tmp_path / "adapter" / "model.safetensors").write_bytes(b"changed")
    with pytest.raises(AdapterVerificationError, match="tampered"):
        verify_adapter_manifest(
            manifest,
            expected_model_id="Qwen/Qwen3-4B-Instruct-2507",
            expected_model_revision="pinned",
        )

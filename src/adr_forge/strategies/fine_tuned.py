"""Verification boundary for locally published QLoRA adapters."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from adr_forge.shared.hashing import canonical_json


@dataclass(frozen=True, slots=True)
class VerifiedAdapter:
    model_id: str
    model_revision: str
    aggregate_sha256: str
    manifest_path: Path


class AdapterVerificationError(ValueError):
    """A manifest or its declared adapter bytes are not safe to activate."""


def verify_adapter_manifest(
    manifest_path: Path, *, expected_model_id: str, expected_model_revision: str
) -> VerifiedAdapter:
    """Verify every declared relative file before exposing adapter identity."""
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        model = manifest["model"]
        adapter = manifest["adapter"]
        files = adapter["files"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise AdapterVerificationError("adapter_manifest_malformed") from exc
    if not isinstance(model, dict) or model.get("id") != expected_model_id:
        raise AdapterVerificationError("adapter_model_mismatch")
    if model.get("revision") != expected_model_revision:
        raise AdapterVerificationError("adapter_revision_mismatch")
    if not isinstance(files, list) or not files:
        raise AdapterVerificationError("adapter_manifest_incomplete")
    root = manifest_path.parent / "adapter"
    declared: list[dict[str, object]] = []
    for item in files:
        if not isinstance(item, dict):
            raise AdapterVerificationError("adapter_manifest_malformed")
        relative, expected_hash, expected_size = (
            item.get("path"),
            item.get("sha256"),
            item.get("size"),
        )
        if (
            not isinstance(relative, str)
            or not isinstance(expected_hash, str)
            or not isinstance(expected_size, int)
        ):
            raise AdapterVerificationError("adapter_manifest_malformed")
        relative_path = Path(relative)
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise AdapterVerificationError("adapter_path_unsafe")
        candidate = root / relative_path
        try:
            candidate.resolve().relative_to(root.resolve())
            payload = candidate.read_bytes()
        except (OSError, ValueError) as exc:
            raise AdapterVerificationError("adapter_file_missing") from exc
        if len(payload) != expected_size or hashlib.sha256(payload).hexdigest() != expected_hash:
            raise AdapterVerificationError("adapter_file_tampered")
        declared.append({"path": relative, "size": expected_size, "sha256": expected_hash})
    aggregate = hashlib.sha256(canonical_json(declared).encode("utf-8")).hexdigest()
    if adapter.get("sha256") != aggregate:
        raise AdapterVerificationError("adapter_aggregate_hash_mismatch")
    return VerifiedAdapter(expected_model_id, expected_model_revision, aggregate, manifest_path)

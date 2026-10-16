"""Canonical, policy-aware construction of completion-only SFT datasets."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from adr_forge.datasets.governance import validate_example
from adr_forge.datasets.models import DatasetExample
from adr_forge.shared.hashing import canonical_json


@dataclass(frozen=True, slots=True)
class DatasetFinding:
    code: str
    example_id: str
    detail: str
    blocking: bool = True


@dataclass(frozen=True, slots=True)
class DatasetValidation:
    source_bytes: bytes
    records: tuple[dict[str, Any], ...]
    examples: tuple[DatasetExample, ...]
    findings: tuple[DatasetFinding, ...]

    @property
    def valid(self) -> bool:
        return not any(finding.blocking for finding in self.findings)


def load_and_validate_manifest(path: Path) -> DatasetValidation:
    """Load a portable manifest and return all deterministic policy findings."""
    raw = path.read_bytes()
    document = json.loads(raw)
    if not isinstance(document, dict) or document.get("schema_version") != "v1":
        raise ValueError("manifest must be a v1 JSON object")
    records = document.get("examples")
    if records is None and isinstance(document.get("sources"), list):
        records = []
        public_root = path.parent.parent / "public"
        for source_name in document["sources"]:
            if not isinstance(source_name, str) or Path(source_name).name != source_name:
                raise ValueError("manifest source must be a public filename")
            source = public_root / source_name
            try:
                records.extend(
                    json.loads(line) for line in source.read_text(encoding="utf-8").splitlines()
                )
            except (OSError, json.JSONDecodeError) as exc:
                raise ValueError(f"cannot load manifest source: {source_name}") from exc
    if not isinstance(records, list) or not all(isinstance(record, dict) for record in records):
        raise ValueError("manifest must contain an examples list")

    examples: list[DatasetExample] = []
    findings: list[DatasetFinding] = []
    for record in records:
        record_id = str(record.get("id", "unknown"))
        try:
            example = _to_example(record)
        except (ValidationError, ValueError) as exc:
            findings.append(DatasetFinding("invalid_example", record_id, str(exc)))
            continue
        examples.append(example)
        findings.extend(
            DatasetFinding(str(finding.code), str(example.id), finding.detail, finding.blocking)
            for finding in validate_example(example)
        )

    return DatasetValidation(
        source_bytes=raw,
        records=tuple(records),
        examples=tuple(examples),
        findings=tuple(
            sorted(findings, key=lambda item: (item.example_id, item.code, item.detail))
        ),
    )


def build_training_dataset(validation: DatasetValidation, output: Path) -> dict[str, object]:
    """Atomically create canonical JSONL without overwriting an existing artifact."""
    if output.exists():
        raise FileExistsError(f"refusing to overwrite immutable artifact: {output}")
    if not validation.valid:
        raise ValueError("dataset has blocking findings")

    rows = [
        _training_row(example)
        for example in sorted(validation.examples, key=lambda item: str(item.id))
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as artifact:
            for row in rows:
                artifact.write(canonical_json(row))
                artifact.write("\n")
            artifact.flush()
            os.fsync(artifact.fileno())
        temporary.replace(output)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise

    payload = output.read_bytes()
    source_hash = hashlib.sha256(validation.source_bytes).hexdigest()
    output_hash = hashlib.sha256(payload).hexdigest()
    return {
        "status": "built",
        "manifest_hash": source_hash,
        "output_hash": output_hash,
        "included": [
            str(example.id)
            for example in sorted(validation.examples, key=lambda item: str(item.id))
        ],
        "exclusions": [],
        "row_count": len(rows),
    }


def validation_report(validation: DatasetValidation) -> dict[str, object]:
    excluded = {finding.example_id for finding in validation.findings}
    return {
        "status": "valid" if validation.valid else "invalid",
        "findings": [asdict(finding) for finding in validation.findings],
        "included": [
            record for record in validation.records if str(record.get("id")) not in excluded
        ],
        "exclusions": [asdict(finding) for finding in validation.findings],
    }


def _to_example(record: dict[str, Any]) -> DatasetExample:
    source = dict(record)
    target = source.pop("target", {})
    content = source.pop("content", None)
    prompt = source.pop("prompt", content if content is not None else "")
    completion = source.pop("completion", json.dumps(target, ensure_ascii=False, sort_keys=True))
    return DatasetExample.model_validate({**source, "prompt": prompt, "completion": completion})


def _training_row(example: DatasetExample) -> dict[str, object]:
    return {
        "schema_version": "v1",
        "example_id": str(example.id),
        "lineage_parent_ids": [str(parent) for parent in example.lineage_parent_ids],
        "prompt": example.prompt,
        "completion": example.completion,
        "loss_scope": "completion_only",
    }

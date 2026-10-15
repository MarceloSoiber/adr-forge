"""Black-box contracts for governed dataset validation and builds."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from typer.testing import CliRunner

from adr_forge.cli.main import app


def _example(
    *, source_type: str = "authored", review_status: str = "approved"
) -> dict[str, object]:
    return {
        "id": str(uuid4()),
        "scenario_revision_id": str(uuid4()),
        "source_type": source_type,
        "source_uri": None,
        "license": "CC-BY-4.0",
        "language": "pt-BR",
        "categories": ["sql_vs_nosql"],
        "lineage_parent_ids": [],
        "review_status": review_status,
        "reviewed_by": "reviewer@example.test" if review_status == "approved" else None,
        "reviewed_at": "2026-10-15T12:00:00Z" if review_status == "approved" else None,
        "content": "Uma aplicação precisa registrar pedidos e preservar rastreabilidade.",
        "target": {"decision": "Usar PostgreSQL para as transações."},
    }


def _manifest(examples: list[dict[str, object]]) -> dict[str, object]:
    return {"schema_version": "v1", "version": "v0.1.0", "examples": examples}


def _write_manifest(path: Path, examples: list[dict[str, object]]) -> bytes:
    path.write_text(json.dumps(_manifest(examples), ensure_ascii=False, indent=2), encoding="utf-8")
    return path.read_bytes()


def test_dataset_validate_reports_machine_readable_findings_exclusions_and_exit_code(
    tmp_path: Path,
) -> None:
    manifest = tmp_path / "candidate-manifest.json"
    _write_manifest(manifest, [_example(source_type="synthetic", review_status="under_review")])

    result = CliRunner().invoke(app, ["dataset", "validate", "--manifest", str(manifest), "--json"])

    assert result.exit_code == 1, result.output
    report = json.loads(result.stdout)
    assert report["status"] == "invalid"
    assert report["included"] == []
    assert len(report["exclusions"]) == 1
    assert report["exclusions"][0]["code"] == "unreviewed_synthetic"
    assert report["findings"][0]["code"] == "unreviewed_synthetic"


def test_dataset_validate_returns_zero_for_an_approved_authorized_manifest(tmp_path: Path) -> None:
    manifest = tmp_path / "approved-manifest.json"
    _write_manifest(manifest, [_example()])

    result = CliRunner().invoke(app, ["dataset", "validate", "--manifest", str(manifest), "--json"])

    assert result.exit_code == 0, result.output
    report = json.loads(result.stdout)
    assert report["status"] == "valid"
    assert report["findings"] == []
    assert len(report["included"]) == 1
    assert report["exclusions"] == []


def test_dataset_build_writes_output_without_changing_the_immutable_input_manifest(
    tmp_path: Path,
) -> None:
    manifest = tmp_path / "approved-manifest.json"
    original_bytes = _write_manifest(manifest, [_example()])
    output = tmp_path / "training.jsonl"

    result = CliRunner().invoke(
        app,
        ["dataset", "build", "--manifest", str(manifest), "--output", str(output), "--json"],
    )

    assert result.exit_code == 0, result.output
    report = json.loads(result.stdout)
    assert report["status"] == "built"
    assert report["manifest_hash"]
    assert report["included"]
    assert report["exclusions"] == []
    assert output.is_file()
    assert manifest.read_bytes() == original_bytes


def test_dataset_build_rejects_an_existing_output_to_preserve_immutable_artifacts(
    tmp_path: Path,
) -> None:
    manifest = tmp_path / "approved-manifest.json"
    _write_manifest(manifest, [_example()])
    output = tmp_path / "training.jsonl"
    output.write_text('{"preserve": true}\n', encoding="utf-8")
    original_output = output.read_bytes()

    result = CliRunner().invoke(
        app,
        ["dataset", "build", "--manifest", str(manifest), "--output", str(output), "--json"],
    )

    assert result.exit_code == 3, result.output
    assert output.read_bytes() == original_output
    assert result.stderr

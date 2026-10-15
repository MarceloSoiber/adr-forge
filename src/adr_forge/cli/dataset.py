"""Governed dataset validation and immutable artifact builds."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import typer
from pydantic import ValidationError

from adr_forge.datasets.governance import validate_example
from adr_forge.datasets.models import DatasetExample


def _emit(payload: dict[str, object], *, json_output: bool) -> None:
    if json_output:
        typer.echo(json.dumps(payload, ensure_ascii=False, default=str))
    else:
        typer.echo(str(payload))


def _load_manifest(path: Path) -> tuple[bytes, list[dict[str, Any]]]:
    raw = path.read_bytes()
    document = json.loads(raw)
    examples = document.get("examples")
    if not isinstance(examples, list) or not all(isinstance(item, dict) for item in examples):
        raise ValueError("manifest must contain an examples list")
    return raw, examples


def _to_example(record: dict[str, Any]) -> DatasetExample:
    """Translate the portable manifest representation into the domain model."""
    target = record.pop("target", {})
    content = record.pop("content", None)
    if content is None:
        content = record.pop("prompt", "")
    completion = record.pop("completion", json.dumps(target, ensure_ascii=False, sort_keys=True))
    return DatasetExample.model_validate({**record, "prompt": content, "completion": completion})


def _validate(path: Path) -> tuple[bytes, list[dict[str, Any]], list[dict[str, object]]]:
    raw, records = _load_manifest(path)
    findings: list[dict[str, object]] = []
    for record in records:
        try:
            example = _to_example(dict(record))
        except (ValidationError, ValueError) as exc:
            findings.append(
                {
                    "code": "invalid_example",
                    "example_id": str(record.get("id", "unknown")),
                    "detail": str(exc),
                }
            )
            continue
        for finding in validate_example(example):
            code = str(finding.code)
            # Preserve the public CLI vocabulary while retaining compatibility with
            # the original domain validator name.
            if code == "synthetic_unreviewed":
                code = "unreviewed_synthetic"
            findings.append(
                {
                    "code": code,
                    "example_id": str(example.id),
                    "detail": finding.detail,
                }
            )
    return raw, records, findings


def dataset_validate(
    manifest: Path = typer.Option(..., exists=True, readable=True),  # noqa: B008
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Validate a dataset manifest without modifying it."""
    try:
        _, records, findings = _validate(manifest)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        _emit(
            {"status": "invalid", "findings": [{"code": "invalid_manifest", "detail": str(exc)}]},
            json_output=json_output,
        )
        raise typer.Exit(code=1) from exc

    excluded_ids = {str(finding["example_id"]) for finding in findings}
    included = [record for record in records if str(record.get("id")) not in excluded_ids]
    exclusions = [finding for finding in findings]
    _emit(
        {
            "status": "valid" if not findings else "invalid",
            "findings": findings,
            "included": included,
            "exclusions": exclusions,
        },
        json_output=json_output,
    )
    if findings:
        raise typer.Exit(code=1)


def dataset_build(
    manifest: Path = typer.Option(..., exists=True, readable=True),  # noqa: B008
    output: Path = typer.Option(...),  # noqa: B008
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Build a JSONL artifact from a valid manifest without mutating the manifest."""
    if output.exists():
        typer.echo(f"refusing to overwrite immutable artifact: {output}", err=True)
        raise typer.Exit(code=3)

    try:
        raw, records, findings = _validate(manifest)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        _emit(
            {"status": "invalid", "findings": [{"code": "invalid_manifest", "detail": str(exc)}]},
            json_output=json_output,
        )
        raise typer.Exit(code=1) from exc
    if findings:
        excluded_ids = {str(finding["example_id"]) for finding in findings}
        _emit(
            {
                "status": "invalid",
                "findings": findings,
                "included": [
                    record for record in records if str(record.get("id")) not in excluded_ids
                ],
                "exclusions": findings,
            },
            json_output=json_output,
        )
        raise typer.Exit(code=1)

    with output.open("x", encoding="utf-8") as artifact:
        for record in records:
            artifact.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
            artifact.write("\n")
    _emit(
        {
            "status": "built",
            "manifest_hash": hashlib.sha256(raw).hexdigest(),
            "included": records,
            "exclusions": [],
        },
        json_output=json_output,
    )

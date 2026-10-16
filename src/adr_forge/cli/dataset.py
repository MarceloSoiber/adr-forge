"""Thin Typer adapter for the shared dataset validation and build pipeline."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from adr_forge.datasets.builder import (
    build_training_dataset,
    load_and_validate_manifest,
    validation_report,
)


def _emit(payload: dict[str, object], *, json_output: bool) -> None:
    typer.echo(
        json.dumps(payload, ensure_ascii=False, default=str) if json_output else str(payload)
    )


def dataset_validate(
    manifest: Path = typer.Option(..., exists=True, readable=True),  # noqa: B008
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Validate a dataset manifest without modifying it."""
    try:
        report = validation_report(load_and_validate_manifest(manifest))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        _emit(
            {"status": "invalid", "findings": [{"code": "invalid_manifest", "detail": str(exc)}]},
            json_output=json_output,
        )
        raise typer.Exit(code=2) from exc
    _emit(report, json_output=json_output)
    if report["status"] != "valid":
        raise typer.Exit(code=3)


def dataset_build(
    manifest: Path = typer.Option(..., exists=True, readable=True),  # noqa: B008
    output: Path = typer.Option(...),  # noqa: B008
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Build a canonical completion-only JSONL artifact from a valid manifest."""
    try:
        validation = load_and_validate_manifest(manifest)
        if not validation.valid:
            _emit(validation_report(validation), json_output=json_output)
            raise typer.Exit(code=3)
        report = build_training_dataset(validation, output)
    except FileExistsError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc
    except typer.Exit:
        raise
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        _emit(
            {"status": "invalid", "findings": [{"code": "invalid_manifest", "detail": str(exc)}]},
            json_output=json_output,
        )
        raise typer.Exit(code=2) from exc
    _emit(report, json_output=json_output)

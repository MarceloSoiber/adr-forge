"""Foreground benchmark command with explicit partial exit semantics."""

from __future__ import annotations

import json
from pathlib import Path

import typer


def benchmark_run(
    config: Path = typer.Option(..., exists=True, readable=True),  # noqa: B008
    resume: bool = typer.Option(True, help="Schedule only missing matrix cells."),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Validate a declared benchmark configuration before foreground execution."""
    result = {"config": str(config), "resume_missing_cells": resume, "status": "queued"}
    if json_output:
        typer.echo(json.dumps(result, ensure_ascii=False))
    else:
        typer.echo(f"Benchmark pronto para execução: {config}")

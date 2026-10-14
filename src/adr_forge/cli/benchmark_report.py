"""Benchmark report command adapter."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

import typer


def benchmark_report(
    experiment: UUID = typer.Option(...),  # noqa: B008
    output: Path = typer.Option(...),  # noqa: B008
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Reserve a deliberate output destination for an immutable report."""
    result = {
        "experiment_id": str(experiment),
        "output": str(output),
        "format": "json" if json_output else "markdown",
    }
    typer.echo(
        json.dumps(result, ensure_ascii=False) if json_output else f"Relatório solicitado: {output}"
    )

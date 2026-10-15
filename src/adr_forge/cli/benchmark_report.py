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
    """Render an immutable local benchmark result as JSON or Markdown."""
    source = Path("var/benchmarks") / f"{experiment}.json"
    if not source.is_file():
        typer.echo(f"experiment {experiment} was not found in the local benchmark store", err=True)
        raise typer.Exit(code=3)
    result = json.loads(source.read_text(encoding="utf-8"))
    output.parent.mkdir(parents=True, exist_ok=True)
    if json_output:
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        typer.echo(json.dumps({"output": str(output), "format": "json"}, ensure_ascii=False))
        return
    accounting = result["accounting"]
    output.write_text(
        "\n".join(
            [
                f"# Benchmark {result['experiment_id']}",
                "",
                f"Status: {result['status']}",
                f"Completed: {accounting['completed']}",
                f"Failed: {accounting['failed']}",
                f"Excluded: {accounting['excluded']}",
                f"Missing: {accounting['missing']}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    typer.echo(f"Relatório criado: {output}")

"""Foreground benchmark command with explicit partial exit semantics."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import typer
import yaml

from adr_forge.experiments.models import Experiment, FrozenMatrixCell, MatrixOutcome
from adr_forge.experiments.runner import BenchmarkRunner
from adr_forge.shared.hashing import canonical_sha256


def benchmark_run(
    config: Path = typer.Option(..., exists=True, readable=True),  # noqa: B008
    resume: bool = typer.Option(True, help="Schedule only missing matrix cells."),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Run a local fake benchmark matrix and emit progress on stderr."""
    try:
        document = yaml.safe_load(config.read_text(encoding="utf-8"))
        if not isinstance(document, dict):
            raise ValueError("benchmark configuration must be a mapping")
        scenarios = document["scenarios"]
        strategies = document["strategies"]
        if not isinstance(scenarios, list) or not isinstance(strategies, list):
            raise ValueError("benchmark requires scenarios and strategies")
    except (OSError, ValueError, yaml.YAMLError, KeyError) as error:
        typer.echo(f"invalid benchmark config: {error}", err=True)
        raise typer.Exit(code=2) from error

    matrix = []
    for scenario in scenarios:
        if not isinstance(scenario, dict):
            continue
        scenario_id = uuid5(NAMESPACE_URL, f"{config.resolve()}#{scenario['id']}")
        scenario_hash = canonical_sha256(scenario)
        for strategy in strategies:
            if not isinstance(strategy, dict):
                continue
            identity = f"{strategy['id']}@{strategy['version']}"
            generation_hash = canonical_sha256(document.get("generation", {}))
            matrix.append(
                FrozenMatrixCell(
                    scenario_revision_id=scenario_id,
                    scenario_content_hash=scenario_hash,
                    strategy_id=strategy["id"],
                    strategy_version=str(strategy["version"]),
                    strategy_configuration_hash=canonical_sha256(strategy),
                    generation_config_hash=generation_hash,
                )
            )
            typer.echo(
                json.dumps(
                    {"stage": "scheduled", "scenario": scenario["id"], "strategy": identity},
                    ensure_ascii=False,
                ),
                err=True,
            )
    if not matrix:
        typer.echo("invalid benchmark config: matrix is empty", err=True)
        raise typer.Exit(code=2)
    experiment = Experiment(
        name=str(document.get("name", config.stem)),
        rubric_version_id=uuid5(NAMESPACE_URL, str(document.get("rubric", {}))),
        code_revision="local-config",
        matrix=matrix,
        expected_run_count=len(matrix),
    )
    runner = BenchmarkRunner()

    async def execute(_cell: FrozenMatrixCell) -> MatrixOutcome:
        return MatrixOutcome.COMPLETED

    import asyncio

    accounting = asyncio.run(runner.run(experiment, execute))
    result = {
        "experiment_id": str(experiment.id),
        "config": str(config),
        "resume_missing_cells": resume,
        "status": accounting.status,
        "accounting": {
            key: value for key, value in accounting.model_dump().items() if key != "status"
        },
    }
    store = Path("var/benchmarks")
    store.mkdir(parents=True, exist_ok=True)
    (store / f"{experiment.id}.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    typer.echo(json.dumps({"stage": accounting.status}, ensure_ascii=False), err=True)
    typer.echo(
        json.dumps(result, ensure_ascii=False) if json_output else json.dumps(result, indent=2)
    )
    raise typer.Exit(code=0 if accounting.status == "completed" else 1)

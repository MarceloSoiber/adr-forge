"""Foreground benchmark command with explicit partial exit semantics."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

import typer
import yaml

from adr_forge.evaluation.deterministic import evaluate_adr
from adr_forge.experiments.models import Experiment, FrozenMatrixCell, MatrixOutcome
from adr_forge.experiments.runner import BenchmarkRunner
from adr_forge.scenarios.models import DecisionCategory, ScenarioRevision
from adr_forge.shared.hashing import canonical_sha256
from adr_forge.strategies.fine_tuned import verify_adapter_manifest
from adr_forge.strategies.qwen_runtime import QWEN_MODEL_ID, QwenRuntime
from adr_forge.system.progress import CancellationToken


def _string_list(value: object, field: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"scenario {field} must be a list of strings")
    return value


def _scenario_from_config(config: Path, value: dict[str, object]) -> ScenarioRevision:
    """Turn the immutable benchmark fixture into the runtime scenario contract."""
    scenario_id = uuid5(NAMESPACE_URL, f"{config.resolve()}#{value['id']}")
    return ScenarioRevision(
        scenario_id=scenario_id,
        revision_number=1,
        problem=str(value["problem"]),
        facts=_string_list(value.get("facts", []), "facts"),
        constraints=_string_list(value.get("constraints", []), "constraints"),
        desired_qualities=_string_list(value.get("desired_qualities", []), "desired_qualities"),
        candidate_alternatives=_string_list(
            value.get("candidate_alternatives", []), "candidate_alternatives"
        ),
        categories=[
            DecisionCategory(item) for item in _string_list(value["categories"], "categories")
        ],
    )


def _parse_json_output(raw_output: str) -> dict[str, object]:
    """Accept plain JSON and the common Markdown fenced representation only."""
    candidate = raw_output.strip()
    if candidate.startswith("```"):
        lines = candidate.splitlines()
        if len(lines) < 3 or not lines[-1].strip().startswith("```"):
            raise ValueError("generated_json_fence_unclosed")
        candidate = "\n".join(lines[1:-1]).strip()
    parsed = json.loads(candidate)
    if not isinstance(parsed, dict):
        raise ValueError("generated_json_not_an_object")
    return parsed


def _telemetry_payload(result: Any) -> dict[str, int | None]:
    telemetry = result.telemetry
    return {
        "input_tokens": telemetry.input_tokens,
        "output_tokens": telemetry.output_tokens,
        "latency_ms": telemetry.latency_ms,
        "peak_vram_mb": telemetry.peak_vram_mb,
    }


def _local_runtime_config(
    config: Path, document: dict[str, object]
) -> tuple[str, Path, dict[str, Path | None]]:
    execution = document.get("execution")
    if not isinstance(execution, dict):
        raise ValueError("transformers benchmark requires an execution mapping")
    revision = execution.get("model_revision")
    manifest = execution.get("adapter_manifest")
    if not isinstance(revision, str) or not isinstance(manifest, str):
        raise ValueError("transformers benchmark requires model_revision and adapter_manifest")
    manifest_path = (config.parent / manifest).resolve()
    verified = verify_adapter_manifest(
        manifest_path, expected_model_id=QWEN_MODEL_ID, expected_model_revision=revision
    )
    strategies = document.get("strategies")
    if not isinstance(strategies, list):
        raise ValueError("benchmark requires strategies")
    paths: dict[str, Path | None] = {}
    for strategy in strategies:
        if not isinstance(strategy, dict):
            raise ValueError("strategy must be a mapping")
        identifier, mode = strategy.get("id"), strategy.get("mode")
        if not isinstance(identifier, str) or mode not in {"baseline", "adapter"}:
            raise ValueError("transformers strategies require id and mode (baseline or adapter)")
        if identifier in paths:
            raise ValueError("strategy ids must be unique")
        paths[identifier] = (
            None if mode == "baseline" else verified.manifest_path.parent / "adapter"
        )
    if set(paths.values()) != {None, verified.manifest_path.parent / "adapter"}:
        raise ValueError("transformers benchmark requires one baseline and one adapter strategy")
    return revision, manifest_path, paths


def benchmark_run(
    config: Path = typer.Option(..., exists=True, readable=True),  # noqa: B008
    resume: bool = typer.Option(True, help="Schedule only missing matrix cells."),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Run a local benchmark matrix and emit progress on stderr."""
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
    execution = document.get("execution", {})
    runtime = execution.get("runtime") if isinstance(execution, dict) else None
    records: dict[str, dict[str, object]] = {}
    execute: Callable[[FrozenMatrixCell], Awaitable[MatrixOutcome]]

    if runtime == "fake":

        async def fake_execute(_cell: FrozenMatrixCell) -> MatrixOutcome:
            return MatrixOutcome.COMPLETED

        execute = fake_execute

    elif runtime == "transformers":
        try:
            revision, manifest_path, adapter_paths = _local_runtime_config(config, document)
            scenarios_by_id = {
                uuid5(NAMESPACE_URL, f"{config.resolve()}#{scenario['id']}"): _scenario_from_config(
                    config, scenario
                )
                for scenario in scenarios
                if isinstance(scenario, dict)
            }
        except (KeyError, TypeError, ValueError) as error:
            typer.echo(f"invalid benchmark config: {error}", err=True)
            raise typer.Exit(code=2) from error

        async def transformers_execute(cell: FrozenMatrixCell) -> MatrixOutcome:
            scenario = scenarios_by_id[cell.scenario_revision_id]
            record_key = f"{cell.scenario_revision_id}:{cell.strategy_id}:{cell.strategy_version}"
            record: dict[str, object] = {
                "scenario_id": str(cell.scenario_revision_id),
                "strategy_id": cell.strategy_id,
                "adapter_manifest": str(manifest_path) if adapter_paths[cell.strategy_id] else None,
            }
            try:
                result = await QwenRuntime(
                    revision=revision,
                    max_new_tokens=int(document.get("generation", {}).get("max_new_tokens", 256)),
                    adapter_path=adapter_paths[cell.strategy_id],
                ).generate(scenario, cancellation=CancellationToken())
                record["raw_output"] = result.raw_output
                record["telemetry"] = _telemetry_payload(result)
                evaluation = evaluate_adr(_parse_json_output(result.raw_output), scenario)
                record["evaluation"] = evaluation.model_dump(mode="json")
                records[record_key] = record
                return MatrixOutcome.COMPLETED if evaluation.passed else MatrixOutcome.FAILED
            except Exception as error:
                record["error"] = f"{type(error).__name__}: {error}"
                records[record_key] = record
                return MatrixOutcome.FAILED

        execute = transformers_execute

    else:
        typer.echo(
            "invalid benchmark config: execution.runtime must be fake or transformers", err=True
        )
        raise typer.Exit(code=2)

    import asyncio

    accounting = asyncio.run(runner.run(experiment, execute))
    completed_without_failures = accounting.missing == 0 and accounting.failed == 0
    status = "completed" if completed_without_failures else "partial"
    result = {
        "experiment_id": str(experiment.id),
        "config": str(config),
        "resume_missing_cells": resume,
        "runtime": runtime,
        "status": status,
        "accounting": {
            key: value for key, value in accounting.model_dump().items() if key != "status"
        },
        "executions": records,
    }
    store = Path("data/benchmarks")
    store.mkdir(parents=True, exist_ok=True)
    (store / f"{experiment.id}.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    typer.echo(json.dumps({"stage": status}, ensure_ascii=False), err=True)
    typer.echo(
        json.dumps(result, ensure_ascii=False) if json_output else json.dumps(result, indent=2)
    )
    raise typer.Exit(code=0 if status == "completed" else 1)

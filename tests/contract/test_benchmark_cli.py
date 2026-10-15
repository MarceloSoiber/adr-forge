"""Black-box contracts for the foreground benchmark CLI."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

from typer.testing import CliRunner

from adr_forge.cli.main import app
from adr_forge.experiments.runner import BenchmarkRunner

ROOT = Path(__file__).resolve().parents[2]
SMOKE_CONFIG = ROOT / "configs" / "evaluation" / "smoke.yaml"


def _json_lines(value: str) -> list[dict[str, object]]:
    return [json.loads(line) for line in value.splitlines() if line.strip()]


def test_benchmark_run_json_emits_progress_then_a_completed_final_result() -> None:
    """Automation gets NDJSON progress on stderr and exactly one final JSON value."""
    result = CliRunner().invoke(app, ["benchmark", "run", "--config", str(SMOKE_CONFIG), "--json"])

    assert result.exit_code == 0, result.output
    final = json.loads(result.stdout)
    assert final["status"] == "completed"
    assert final["accounting"] == {
        "completed": 4,
        "failed": 0,
        "excluded": 0,
        "missing": 0,
    }
    UUID(final["experiment_id"])

    progress = _json_lines(result.stderr)
    assert progress
    assert all("stage" in event for event in progress)
    assert progress[-1]["stage"] == "completed"


def test_benchmark_run_rejects_an_invalid_configuration_with_input_exit_code(
    tmp_path: Path,
) -> None:
    invalid_config = tmp_path / "invalid.yaml"
    invalid_config.write_text("name: only-a-name\n", encoding="utf-8")

    result = CliRunner().invoke(
        app,
        ["benchmark", "run", "--config", str(invalid_config), "--json"],
    )

    assert result.exit_code == 2
    assert result.stdout == ""
    assert result.stderr


def test_benchmark_run_returns_partial_exit_code_when_cells_remain_missing(
    monkeypatch,
) -> None:
    """An interrupted matrix must never be represented as a successful completion."""
    monkeypatch.setattr(BenchmarkRunner, "missing_cells", lambda _runner, _experiment: [])

    result = CliRunner().invoke(app, ["benchmark", "run", "--config", str(SMOKE_CONFIG), "--json"])

    assert result.exit_code == 1, result.output
    final = json.loads(result.stdout)
    assert final["status"] == "partial"
    assert final["accounting"]["missing"] == 4
    assert _json_lines(result.stderr)[-1]["stage"] == "partial"


def test_benchmark_report_outputs_requested_json_and_fails_for_unknown_experiment(
    tmp_path: Path,
) -> None:
    output = tmp_path / "unknown-experiment.json"

    result = CliRunner().invoke(
        app,
        [
            "benchmark",
            "report",
            "--experiment",
            "00000000-0000-0000-0000-000000000000",
            "--output",
            str(output),
            "--json",
        ],
    )

    assert result.exit_code == 3
    assert not output.exists()
    assert result.stderr

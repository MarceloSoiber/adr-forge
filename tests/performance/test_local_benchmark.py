"""CPU-only regression instrumentation for local application overhead.

This is deliberately a fake benchmark: it measures local orchestration, SQLite,
report, and artifact work only.  It does not measure model latency, capacity, or
throughput.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import platform
import sqlite3
import sys
from pathlib import Path
from time import perf_counter

import yaml
from typer.testing import CliRunner

from adr_forge.artifacts.store import ArtifactStore
from adr_forge.cli.main import app
from adr_forge.shared.hashing import canonical_sha256

SCENARIO_COUNT = 100
# These ceilings are regression/deadlock guards for shared CI, not performance claims.
TOTAL_CEILING_SECONDS = 30.0
STAGE_CEILING_SECONDS = 20.0


def _fake_config() -> dict[str, object]:
    return {
        "schema_version": "benchmark-v1",
        "name": "local-overhead-100-scenarios",
        "rubric": {"name": "fake", "version": "1"},
        "generation": {"temperature": 0, "max_new_tokens": 1},
        "strategies": [{"id": "fake-baseline", "version": "1"}],
        "scenarios": [
            {
                "id": f"fake-{index:03d}",
                "title": f"Fake scenario {index}",
                "problem": "Deterministic local orchestration fixture.",
            }
            for index in range(SCENARIO_COUNT)
        ],
    }


def _elapsed(started: float) -> float:
    return perf_counter() - started


def test_local_fake_benchmark_accounts_for_100_scenarios_with_temporary_storage(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Capture CPU-only orchestration overhead without making model performance claims."""
    monkeypatch.chdir(tmp_path)
    config_path = tmp_path / "fake-100.yaml"
    config_path.write_text(yaml.safe_dump(_fake_config(), sort_keys=True), encoding="utf-8")
    environment = {
        "execution_mode": "cpu-only-fake",
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "code_identity": canonical_sha256(
            (Path(__file__).parents[2] / "src/adr_forge/cli/benchmark_run.py").read_text(
                encoding="utf-8"
            )
        ),
        "sqlite_mode": "WAL",
        "artifact_root_type": "temporary-directory",
        "warm_cold_rule": "single cold process; no model warm-up",
    }
    timings: dict[str, float] = {}
    runner = CliRunner()

    total_started = perf_counter()
    progress_started = perf_counter()
    run_result = runner.invoke(app, ["benchmark", "run", "--config", str(config_path), "--json"])
    timings["progress_and_accounting_seconds"] = _elapsed(progress_started)

    assert run_result.exit_code == 0, run_result.output
    result = json.loads(run_result.stdout)
    assert result["status"] == "completed"
    assert result["accounting"] == {
        "completed": SCENARIO_COUNT,
        "failed": 0,
        "excluded": 0,
        "missing": 0,
    }
    progress = [json.loads(line) for line in run_result.stderr.splitlines() if line.strip()]
    assert sum(event["stage"] == "scheduled" for event in progress) == SCENARIO_COUNT
    assert progress[-1] == {"stage": "completed"}

    report_path = tmp_path / "reports" / "fake-100.md"
    report_started = perf_counter()
    report_result = runner.invoke(
        app,
        [
            "benchmark",
            "report",
            "--experiment",
            result["experiment_id"],
            "--output",
            str(report_path),
        ],
    )
    timings["report_seconds"] = _elapsed(report_started)
    assert report_result.exit_code == 0, report_result.output
    report_bytes = report_path.read_bytes()
    assert b"Completed: 100" in report_bytes

    database_path = tmp_path / "instrumentation.sqlite3"
    sqlite_started = perf_counter()
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
        connection.execute(
            "CREATE TABLE measurements (name TEXT PRIMARY KEY, seconds REAL NOT NULL)"
        )
        connection.executemany(
            "INSERT INTO measurements VALUES (?, ?)",
            list(timings.items()),
        )
        assert connection.execute("SELECT COUNT(*) FROM measurements").fetchone() == (2,)
    timings["sqlite_seconds"] = _elapsed(sqlite_started)

    artifact_root = tmp_path / "artifacts"
    artifact_started = perf_counter()
    digest, artifact_bytes, relative_path = asyncio.run(
        ArtifactStore(artifact_root).put_bytes(report_bytes)
    )
    timings["artifact_seconds"] = _elapsed(artifact_started)
    assert artifact_bytes == len(report_bytes)
    assert (artifact_root / relative_path).is_file()
    assert digest == hashlib.sha256(report_bytes).hexdigest()
    assert not list((artifact_root / ".tmp").glob("*.part"))

    timings["total_seconds"] = _elapsed(total_started)
    instrumentation = {
        "environment": environment,
        "scenario_count": SCENARIO_COUNT,
        "accounting": result["accounting"],
        "stage_latencies_seconds": timings,
        "report_bytes": len(report_bytes),
        "artifact_bytes": artifact_bytes,
        "failures": [],
        "cleanup_state": "temporary pytest directory",
    }
    (tmp_path / "instrumentation.json").write_text(
        json.dumps(instrumentation, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    assert timings["total_seconds"] < TOTAL_CEILING_SECONDS
    assert all(duration < STAGE_CEILING_SECONDS for duration in timings.values())

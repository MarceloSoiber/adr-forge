"""Integration coverage for transparent benchmark report evidence."""

from __future__ import annotations

from uuid import UUID, uuid4

from adr_forge.experiments.models import Experiment, FrozenMatrixCell, MatrixOutcome
from adr_forge.experiments.reporting import aggregate_report


def _cell(*, scenario_id: UUID, strategy_id: str, strategy_version: str) -> FrozenMatrixCell:
    return FrozenMatrixCell(
        scenario_revision_id=scenario_id,
        scenario_content_hash="a" * 64,
        strategy_id=strategy_id,
        strategy_version=strategy_version,
        strategy_configuration_hash="b" * 64,
        generation_config_hash="c" * 64,
    )


def test_report_exposes_outcomes_telemetry_and_all_reproducibility_identities() -> None:
    failed_cell = _cell(scenario_id=uuid4(), strategy_id="baseline-model", strategy_version="2.1.0")
    excluded_cell = _cell(scenario_id=uuid4(), strategy_id="tuned-model", strategy_version="0.3.0")
    dataset_id = uuid4()
    rubric_id = uuid4()
    configuration_id = uuid4()
    experiment = Experiment(
        name="Transparent benchmark report",
        dataset_version_id=dataset_id,
        rubric_version_id=rubric_id,
        code_revision="a1b2c3d",
        configuration_artifact_id=configuration_id,
        matrix=[failed_cell, excluded_cell],
    )
    outcomes = {
        (failed_cell.scenario_revision_id, failed_cell.strategy_id, failed_cell.strategy_version): (
            MatrixOutcome.FAILED
        ),
        (
            excluded_cell.scenario_revision_id,
            excluded_cell.strategy_id,
            excluded_cell.strategy_version,
        ): MatrixOutcome.EXCLUDED,
    }
    telemetry = {
        (failed_cell.scenario_revision_id, failed_cell.strategy_id, failed_cell.strategy_version): {
            "latency_ms": 1_250,
            "peak_vram_mb": 6_144,
            "failure_code": "model_unavailable",
        },
        (
            excluded_cell.scenario_revision_id,
            excluded_cell.strategy_id,
            excluded_cell.strategy_version,
        ): {
            "exclusion_reason": "strategy_not_available",
        },
    }

    report = aggregate_report(experiment, outcomes, telemetry)

    assert report["accounting"] == {
        "completed": 0,
        "failed": 1,
        "excluded": 1,
        "missing": 0,
        "status": "completed",
    }
    assert report["runs"] == [
        {
            **failed_cell.model_dump(mode="json"),
            "outcome": "failed",
            "latency_ms": 1_250,
            "peak_vram_mb": 6_144,
            "failure_code": "model_unavailable",
        },
        {
            **excluded_cell.model_dump(mode="json"),
            "outcome": "excluded",
            "exclusion_reason": "strategy_not_available",
        },
    ]
    assert report["sc_009"] == "not_decidable_without_a_tuned_and_a_baseline_result"
    assert report["reproducibility_manifest"] == {
        "experiment_id": str(experiment.id),
        "code_revision": "a1b2c3d",
        "dataset_version_id": str(dataset_id),
        "rubric_version_id": str(rubric_id),
        "configuration_artifact_id": str(configuration_id),
        "matrix": [
            failed_cell.model_dump(mode="json"),
            excluded_cell.model_dump(mode="json"),
        ],
    }

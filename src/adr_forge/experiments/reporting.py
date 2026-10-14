"""Honest, reproducible benchmark report construction."""

from __future__ import annotations

from adr_forge.experiments.models import Experiment, MatrixOutcome


def reproducibility_manifest(experiment: Experiment) -> dict[str, object]:
    return {
        "experiment_id": str(experiment.id),
        "code_revision": experiment.code_revision,
        "dataset_version_id": str(experiment.dataset_version_id)
        if experiment.dataset_version_id
        else None,
        "rubric_version_id": str(experiment.rubric_version_id),
        "configuration_artifact_id": str(experiment.configuration_artifact_id)
        if experiment.configuration_artifact_id
        else None,
        "matrix": [cell.model_dump(mode="json") for cell in experiment.matrix],
    }


def aggregate_report(
    experiment: Experiment,
    outcomes: dict[tuple[object, str, str], MatrixOutcome | str],
    telemetry: dict[tuple[object, str, str], dict[str, object]] | None = None,
) -> dict[str, object]:
    normalized = {key: MatrixOutcome(value) for key, value in outcomes.items()}
    accounting = experiment.accounting(list(normalized.values()))
    rows = []
    for cell in experiment.matrix:
        key = (cell.scenario_revision_id, cell.strategy_id, cell.strategy_version)
        rows.append(
            {
                **cell.model_dump(mode="json"),
                "outcome": normalized.get(key, "missing"),
                **(telemetry or {}).get(key, {}),
            }
        )
    return {
        "experiment": {
            "id": str(experiment.id),
            "name": experiment.name,
            "status": accounting.status,
        },
        "accounting": accounting.model_dump(mode="json"),
        "runs": rows,
        "reproducibility_manifest": reproducibility_manifest(experiment),
        "sc_009": "not_decidable_without_a_tuned_and_a_baseline_result",
    }

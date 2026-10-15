"""Lifecycle and terminal accounting contracts for benchmark experiments."""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from adr_forge.experiments.models import Experiment, ExperimentStatus


def _experiment(
    *, name: str = "Baseline architecture benchmark", expected_run_count: int = 4
) -> Experiment:
    return Experiment(
        name=name,
        dataset_version_id=uuid4(),
        rubric_version_id=uuid4(),
        code_revision="4d2c0c5",
        configuration_artifact_id=uuid4(),
        expected_run_count=expected_run_count,
    )


def test_experiment_freezes_reproducibility_identities_and_has_a_draft_lifecycle() -> None:
    experiment = _experiment()

    assert experiment.status is ExperimentStatus.DRAFT
    assert experiment.started_at is None
    assert experiment.finished_at is None
    assert experiment.expected_run_count == 4

    running = experiment.transition(ExperimentStatus.RUNNING)

    assert running.status is ExperimentStatus.RUNNING
    assert running.started_at is not None
    assert running.dataset_version_id == experiment.dataset_version_id
    assert running.rubric_version_id == experiment.rubric_version_id
    assert running.code_revision == "4d2c0c5"
    assert running.configuration_artifact_id == experiment.configuration_artifact_id
    assert experiment.status is ExperimentStatus.DRAFT


def test_experiment_rejects_invalid_name_and_non_positive_matrix_size() -> None:
    with pytest.raises(ValidationError):
        _experiment(name="x")

    with pytest.raises(ValidationError):
        _experiment(expected_run_count=0)


def test_terminal_accounting_is_complete_only_when_every_expected_cell_is_accounted_for() -> None:
    running = _experiment(expected_run_count=4).transition(ExperimentStatus.RUNNING)

    accounting = running.accounting(["completed", "completed", "completed", "excluded"])
    completed = running.transition(accounting["status"])

    assert accounting.status is ExperimentStatus.COMPLETED
    assert accounting.completed == 3
    assert accounting.failed == 0
    assert accounting.excluded == 1
    assert accounting.missing == 0
    assert completed.finished_at is not None


def test_terminal_accounting_marks_incomplete_matrix_as_partial_and_exposes_missing_cells() -> None:
    running = _experiment(expected_run_count=4).transition(ExperimentStatus.RUNNING)
    accounting = running.accounting(["completed", "failed"])
    partial = running.transition(accounting["status"])

    assert accounting.status is ExperimentStatus.PARTIAL
    assert accounting.completed == 1
    assert accounting.failed == 1
    assert accounting.excluded == 0
    assert accounting.missing == 2
    assert partial.finished_at is not None


def test_terminal_experiment_cannot_be_restarted() -> None:
    running = _experiment(expected_run_count=1).transition(ExperimentStatus.RUNNING)
    completed = running.transition(running.accounting(["completed"])["status"])

    with pytest.raises(ValueError, match="terminal"):
        completed.transition(ExperimentStatus.RUNNING)

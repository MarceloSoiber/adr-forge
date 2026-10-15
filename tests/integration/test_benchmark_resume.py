"""Integration coverage for resuming an interrupted benchmark matrix."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from adr_forge.experiments.models import Experiment, FrozenMatrixCell, MatrixOutcome
from adr_forge.experiments.runner import BenchmarkRunner


def _cell(*, scenario_id: UUID, strategy_id: str) -> FrozenMatrixCell:
    return FrozenMatrixCell(
        scenario_revision_id=scenario_id,
        scenario_content_hash="a" * 64,
        strategy_id=strategy_id,
        strategy_version="1.0.0",
        strategy_configuration_hash="b" * 64,
        generation_config_hash="c" * 64,
    )


@pytest.mark.asyncio
async def test_resume_preserves_completed_cells_and_schedules_only_missing_matrix_cells() -> None:
    completed_cell = _cell(scenario_id=uuid4(), strategy_id="baseline")
    missing_cell = _cell(scenario_id=uuid4(), strategy_id="baseline")
    experiment = Experiment(
        name="Interrupted baseline benchmark",
        rubric_version_id=uuid4(),
        code_revision="a1b2c3d",
        matrix=[completed_cell, missing_cell],
    )
    runner = BenchmarkRunner()
    runner.outcomes[runner.key(completed_cell)] = MatrixOutcome.COMPLETED
    scheduled: list[FrozenMatrixCell] = []

    async def execute(cell: FrozenMatrixCell) -> MatrixOutcome:
        scheduled.append(cell)
        return MatrixOutcome.EXCLUDED

    accounting = await runner.run(experiment, execute)

    assert scheduled == [missing_cell]
    assert runner.outcomes[runner.key(completed_cell)] is MatrixOutcome.COMPLETED
    assert runner.outcomes[runner.key(missing_cell)] is MatrixOutcome.EXCLUDED
    assert accounting.completed == 1
    assert accounting.excluded == 1
    assert accounting.missing == 0

    await runner.run(experiment, execute)

    assert scheduled == [missing_cell]

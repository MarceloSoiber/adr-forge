"""Matrix runner with append-only completed cells and explicit failures/exclusions."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from adr_forge.experiments.models import (
    Experiment,
    ExperimentAccounting,
    FrozenMatrixCell,
    MatrixOutcome,
)


class BenchmarkRunner:
    def __init__(self) -> None:
        self.outcomes: dict[tuple[object, str, str], MatrixOutcome] = {}

    @staticmethod
    def key(cell: FrozenMatrixCell) -> tuple[object, str, str]:
        return (cell.scenario_revision_id, cell.strategy_id, cell.strategy_version)

    def missing_cells(self, experiment: Experiment) -> list[FrozenMatrixCell]:
        return [cell for cell in experiment.matrix if self.key(cell) not in self.outcomes]

    async def run(
        self,
        experiment: Experiment,
        execute: Callable[[FrozenMatrixCell], Awaitable[MatrixOutcome | str]],
    ) -> ExperimentAccounting:
        for cell in self.missing_cells(experiment):
            try:
                outcome = MatrixOutcome(await execute(cell))
            except Exception:
                outcome = MatrixOutcome.FAILED
            self.outcomes[self.key(cell)] = outcome
        return experiment.accounting(list(self.outcomes.values()))

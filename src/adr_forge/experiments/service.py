"""Creation of benchmark experiments freezes all reproducibility inputs."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from adr_forge.evaluation.models import RubricVersion
from adr_forge.experiments.models import Experiment, FrozenMatrixCell
from adr_forge.scenarios.models import ScenarioRevision
from adr_forge.shared.hashing import canonical_sha256
from adr_forge.strategies.models import AnalysisStrategy


def create_experiment(
    *,
    name: str,
    scenario_revisions: Sequence[ScenarioRevision],
    strategies: list[AnalysisStrategy],
    rubric: RubricVersion,
    code_revision: str,
    configuration: dict[str, object],
    retrieval_snapshot_ids: dict[UUID, UUID | None] | None = None,
    dataset_version_id: UUID | None = None,
    configuration_artifact_id: UUID | None = None,
) -> Experiment:
    """Freeze a cartesian scenario/strategy matrix without retaining mutable objects."""
    snapshots = retrieval_snapshot_ids or {}
    cells: list[FrozenMatrixCell] = []
    for scenario in scenario_revisions:
        scenario_id = scenario.id
        scenario_hash = scenario.content_hash
        for strategy in strategies:
            snapshot = snapshots.get(scenario_id)
            if strategy.requires_retrieval and snapshot is None:
                raise ValueError("retrieval strategy requires a frozen snapshot for every scenario")
            if not strategy.requires_retrieval:
                snapshot = None
            cells.append(
                FrozenMatrixCell(
                    scenario_revision_id=scenario_id,
                    scenario_content_hash=scenario_hash,
                    strategy_id=strategy.id,
                    strategy_version=strategy.version,
                    strategy_configuration_hash=canonical_sha256(strategy.model_dump(mode="json")),
                    generation_config_hash=strategy.generation_config_hash,
                    retrieval_snapshot_id=snapshot,
                )
            )
    return Experiment(
        name=name,
        dataset_version_id=dataset_version_id,
        rubric_version_id=rubric.id,
        code_revision=code_revision,
        configuration_artifact_id=configuration_artifact_id,
        matrix=cells,
        expected_run_count=len(cells),
    )

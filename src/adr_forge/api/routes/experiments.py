"""Read-only-safe HTTP projections for benchmark experiments."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field

from adr_forge.api.routes.analysis import PROBLEM, AnalysisRun, _run_repository, _run_response
from adr_forge.evaluation.models import RubricVersion
from adr_forge.experiments.models import Experiment as DomainExperiment
from adr_forge.experiments.models import ExperimentStatus
from adr_forge.experiments.reporting import aggregate_report
from adr_forge.experiments.repository import ExperimentRepository
from adr_forge.experiments.service import create_experiment
from adr_forge.scenarios.repository import ScenarioRepository
from adr_forge.shared.errors import NotFoundError
from adr_forge.shared.errors import ValidationError as DomainValidationError
from adr_forge.strategies.configuration import configured_registry

router = APIRouter(prefix="/api/v1")


class StrategyRef(BaseModel):
    id: str = Field(min_length=1)
    version: str = Field(min_length=1)


class CreateExperimentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=3, max_length=200)
    scenario_revision_ids: list[UUID] = Field(min_length=1)
    strategy_refs: list[StrategyRef] = Field(min_length=2)
    dataset_version_id: UUID | None = None
    rubric_version_id: UUID
    code_revision: str = Field(min_length=7)


class Experiment(BaseModel):
    id: UUID
    name: str
    status: ExperimentStatus
    rubric_version_id: UUID
    code_revision: str
    expected_run_count: int = Field(ge=1)
    completed_run_count: int = Field(ge=0)
    failed_run_count: int = Field(ge=0)
    excluded_run_count: int = Field(ge=0)


def _repository(request: Request) -> ExperimentRepository:
    return ExperimentRepository(request.app.state.session_factory)


def _response(experiment: DomainExperiment) -> Experiment:
    accounting = experiment.accounting()
    return Experiment(
        id=experiment.id,
        name=experiment.name,
        status=experiment.status,
        rubric_version_id=experiment.rubric_version_id,
        code_revision=experiment.code_revision,
        expected_run_count=experiment.run_count,
        completed_run_count=accounting.completed,
        failed_run_count=accounting.failed,
        excluded_run_count=accounting.excluded,
    )


@router.post(
    "/experiments",
    status_code=201,
    operation_id="createExperiment",
    response_model=Experiment,
    responses={422: PROBLEM},
)
async def create_experiment_route(command: CreateExperimentRequest, request: Request) -> Experiment:
    experiments = _repository(request)
    rubric: RubricVersion | None = await experiments.get_rubric(command.rubric_version_id)
    if rubric is None:
        raise DomainValidationError("Rubric version not found.")
    scenarios = ScenarioRepository(request.app.state.session_factory)
    revisions = []
    for identity in command.scenario_revision_ids:
        revision = await scenarios.get_revision(str(identity))
        if revision is None:
            raise DomainValidationError("Scenario revision not found.")
        revisions.append(revision)
    settings = request.app.state.settings
    registry = configured_registry(settings)
    strategies = []
    for reference in command.strategy_refs:
        strategy = registry.get(reference.id, reference.version)
        if strategy is None:
            raise DomainValidationError("Strategy version not found.")
        if strategy.requires_retrieval:
            raise DomainValidationError(
                "A frozen retrieval snapshot is required for this strategy."
            )
        strategies.append(strategy)
    experiment = create_experiment(
        name=command.name,
        scenario_revisions=revisions,
        strategies=strategies,
        rubric=rubric,
        code_revision=command.code_revision,
        configuration={"source": "api"},
        dataset_version_id=command.dataset_version_id,
    )
    await experiments.add(experiment)
    return _response(experiment)


@router.get(
    "/experiments/{experimentId}",
    operation_id="getExperiment",
    response_model=Experiment,
    responses={404: PROBLEM},
)
async def get_experiment(experimentId: UUID, request: Request) -> Experiment:
    experiment = await _repository(request).get(experimentId)
    if experiment is None:
        raise NotFoundError("Experiment not found.")
    return _response(experiment)


@router.get(
    "/experiments/{experimentId}/runs",
    operation_id="listExperimentRuns",
    response_model=list[AnalysisRun],
)
async def get_experiment_runs(experimentId: UUID, request: Request) -> list[dict[str, object]]:
    experiment = await _repository(request).get(experimentId)
    if experiment is None:
        raise NotFoundError("Experiment not found.")
    return [
        _run_response(run)
        for run in await (await _run_repository(request)).list_by_experiment(str(experimentId))
    ]


@router.get(
    "/experiments/{experimentId}/report",
    operation_id="getExperimentReport",
    responses={409: PROBLEM},
)
async def get_experiment_report(experimentId: UUID, request: Request) -> dict[str, object]:
    experiment = await _repository(request).get(experimentId)
    if experiment is None:
        raise NotFoundError("Experiment not found.")
    return aggregate_report(experiment, {})

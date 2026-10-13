"""Phase 3 HTTP contract surface for scenario analysis."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field


class Problem(BaseModel):
    type: str
    title: str
    status: int
    detail: str | None = None
    code: str | None = None
    request_id: str | None = None


PROBLEM = {"model": Problem}


class CreateScenarioRequest(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    language: str = Field(json_schema_extra={"const": "pt-BR"})
    problem: str = Field(min_length=20, max_length=20_000)
    facts: list[str] = Field(default_factory=list, max_length=50)
    constraints: list[str] = Field(default_factory=list, max_length=50)
    desired_qualities: list[str] = Field(default_factory=list, max_length=20)
    candidate_alternatives: list[str] = Field(default_factory=list, max_length=20)


class ScenarioRevision(BaseModel):
    id: UUID
    scenario_id: UUID
    revision_number: int = Field(ge=1)
    problem: str
    facts: list[str]
    constraints: list[str]
    desired_qualities: list[str]
    candidate_alternatives: list[str]
    categories: list[str]
    content_hash: str
    created_at: datetime


class ScenarioResponse(BaseModel):
    id: UUID
    title: str
    language: str
    current_revision: ScenarioRevision


class CreateAnalysisRunRequest(BaseModel):
    scenario_revision_id: UUID
    strategy_id: str
    strategy_version: str
    retrieval_snapshot_id: UUID | None = None
    experiment_id: UUID | None = None


class AnalysisRun(BaseModel):
    id: UUID
    scenario_revision_id: UUID
    strategy_id: str
    strategy_version: str
    status: str
    stage: str
    progress_percent: int | None = Field(default=None, ge=0, le=100)
    progress_sequence: int = Field(ge=0)
    validation_attempts: list[dict[str, Any]]
    created_at: datetime
    updated_at: datetime


class ProgressEvent(BaseModel):
    run_id: UUID
    status: str
    stage: str
    progress_percent: int | None = Field(default=None, ge=0, le=100)
    progress_sequence: int = Field(ge=0)
    updated_at: datetime


class AdrDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    analysis_run_id: UUID
    schema_version: str
    title: str
    status: str
    context: list[str]
    facts: list[str]
    assumptions: list[dict[str, Any]]
    unresolved_questions: list[dict[str, Any]]
    constraints: list[str]
    alternatives: list[dict[str, Any]]
    decision: str | None
    rationale: list[dict[str, Any]]
    positive_consequences: list[str]
    negative_consequences: list[str]
    risks: list[dict[str, Any]]
    review_triggers: list[dict[str, Any]]
    confidence: float
    reference_ids: list[str]
    created_at: datetime


router = APIRouter(prefix="/api/v1")


@router.post(
    "/scenarios",
    response_model=ScenarioResponse,
    status_code=201,
    operation_id="createScenario",
    responses={422: PROBLEM},
)
async def create_scenario(_: CreateScenarioRequest) -> ScenarioResponse:
    raise NotImplementedError


@router.get(
    "/scenarios/{scenarioId}",
    response_model=ScenarioResponse,
    operation_id="getScenario",
    responses={404: PROBLEM},
)
async def get_scenario(scenarioId: UUID) -> ScenarioResponse:
    raise NotImplementedError


@router.post(
    "/analysis-runs",
    response_model=AnalysisRun,
    status_code=202,
    operation_id="createAnalysisRun",
    responses={409: PROBLEM, 422: PROBLEM},
)
async def create_analysis_run(_: CreateAnalysisRunRequest) -> AnalysisRun:
    raise NotImplementedError


@router.get(
    "/analysis-runs/{runId}",
    response_model=AnalysisRun,
    operation_id="getAnalysisRun",
    responses={404: PROBLEM},
)
async def get_analysis_run(runId: UUID) -> AnalysisRun:
    raise NotImplementedError


@router.get(
    "/analysis-runs/{runId}/events",
    operation_id="streamAnalysisRunEvents",
    responses={
        200: {"content": {"text/event-stream": {"schema": {"type": "string"}}}},
        404: PROBLEM,
    },
)
async def stream_analysis_run_events(runId: UUID) -> None:
    raise NotImplementedError


@router.post(
    "/analysis-runs/{runId}/cancel",
    response_model=AnalysisRun,
    status_code=202,
    operation_id="cancelAnalysisRun",
    responses={404: PROBLEM, 409: PROBLEM},
)
async def cancel_analysis_run(runId: UUID) -> AnalysisRun:
    raise NotImplementedError


@router.get(
    "/analysis-runs/{runId}/adr",
    response_model=AdrDraft,
    operation_id="getRunAdr",
    responses={404: PROBLEM, 409: PROBLEM},
)
async def get_run_adr(runId: UUID) -> AdrDraft:
    raise NotImplementedError


@router.get(
    "/analysis-runs/{runId}/export",
    operation_id="exportRunAdr",
    responses={
        200: {
            "content": {
                "text/markdown": {"schema": {"type": "string"}},
                        "application/json": {"schema": {"$ref": "#/components/schemas/AdrDraft"}},
            }
        },
        404: PROBLEM,
        409: PROBLEM,
    },
)
async def export_run_adr(runId: UUID, format: str = "markdown") -> None:
    raise NotImplementedError

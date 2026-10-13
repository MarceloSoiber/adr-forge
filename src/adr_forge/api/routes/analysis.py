"""Phase 3 HTTP contract surface for scenario analysis."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
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
async def create_scenario(command: CreateScenarioRequest, request: Request) -> dict[str, Any]:
    from hashlib import sha256
    from uuid import uuid4

    scenario_id, revision_id = uuid4(), uuid4()
    now = datetime.now(UTC)
    combined_text = f"{command.problem} {' '.join(command.candidate_alternatives)}".lower()
    categories = ["sql_vs_nosql"] if any(token in combined_text for token in ("sql", "mongo")) else ["unsupported"]
    revision = {
        "id": revision_id,
        "scenario_id": scenario_id,
        "revision_number": 1,
        "problem": command.problem,
        "facts": command.facts,
        "constraints": command.constraints,
        "desired_qualities": command.desired_qualities,
        "candidate_alternatives": command.candidate_alternatives,
        "categories": categories,
        "content_hash": sha256(command.problem.encode()).hexdigest(),
        "created_at": now,
    }
    result = {
        "id": scenario_id,
        "title": command.title,
        "language": command.language,
        "current_revision": revision,
    }
    request.app.state.analysis_store["scenarios"][str(scenario_id)] = result
    request.app.state.analysis_store["revisions"][str(revision_id)] = revision
    return result


@router.get(
    "/scenarios/{scenarioId}",
    response_model=ScenarioResponse,
    operation_id="getScenario",
    responses={404: PROBLEM},
)
async def get_scenario(scenarioId: UUID, request: Request) -> dict[str, Any]:
    found = request.app.state.analysis_store["scenarios"].get(str(scenarioId))
    if found is None:
        raise HTTPException(404, "Scenario not found")
    return found


@router.post(
    "/analysis-runs",
    response_model=AnalysisRun,
    status_code=202,
    operation_id="createAnalysisRun",
    responses={409: PROBLEM, 422: PROBLEM},
)
async def create_analysis_run(
    command: CreateAnalysisRunRequest, request: Request
) -> dict[str, Any]:
    from uuid import uuid4

    revision = request.app.state.analysis_store["revisions"].get(str(command.scenario_revision_id))
    if revision is None:
        raise HTTPException(409, "Scenario revision not found")
    run_id, adr_id, now = uuid4(), uuid4(), datetime.now(UTC)
    choice = (revision["candidate_alternatives"] or ["Alternativa A"])[0]
    adr = {
        "id": adr_id,
        "analysis_run_id": run_id,
        "schema_version": "adr-v1",
        "title": f"Decisão: {choice}",
        "status": "proposed",
        "context": [revision["problem"]],
        "facts": revision["facts"],
        "assumptions": [],
        "unresolved_questions": [],
        "constraints": revision["constraints"] or ["Operação local"],
        "alternatives": [],
        "decision": choice,
        "rationale": [],
        "positive_consequences": ["Decisão explícita."],
        "negative_consequences": ["Exige revisão humana."],
        "risks": [],
        "review_triggers": [
            {"metric": "latencia_p95", "operator": "gt", "threshold": 500, "unit": "ms"}
        ],
        "confidence": 0.5,
        "reference_ids": [],
        "created_at": now,
    }
    run = {
        "id": run_id,
        "scenario_revision_id": command.scenario_revision_id,
        "strategy_id": command.strategy_id,
        "strategy_version": command.strategy_version,
        "status": "completed",
        "stage": "concluído",
        "progress_percent": 100,
        "progress_sequence": 2,
        "validation_attempts": [
            {
                "attempt": "original",
                "artifact_id": str(uuid4()),
                "parse_succeeded": True,
                "findings": [],
            }
        ],
        "created_at": now,
        "updated_at": now,
    }
    request.app.state.analysis_store["runs"][str(run_id)] = run
    request.app.state.analysis_store["adrs"][str(run_id)] = adr
    return run


@router.get(
    "/analysis-runs/{runId}",
    response_model=AnalysisRun,
    operation_id="getAnalysisRun",
    responses={404: PROBLEM},
)
async def get_analysis_run(runId: UUID, request: Request) -> dict[str, Any]:
    found = request.app.state.analysis_store["runs"].get(str(runId))
    if found is None:
        raise HTTPException(404, "Run not found")
    return found


@router.get(
    "/analysis-runs/{runId}/events",
    operation_id="streamAnalysisRunEvents",
    responses={
        200: {"content": {"text/event-stream": {"schema": {"type": "string"}}}},
        404: PROBLEM,
    },
)
async def stream_analysis_run_events(runId: UUID, request: Request) -> Response:
    run = await get_analysis_run(runId, request)
    payload = {
        "run_id": str(runId),
        "status": run["status"],
        "stage": run["stage"],
        "progress_percent": run["progress_percent"],
        "progress_sequence": run["progress_sequence"],
        "updated_at": run["updated_at"].isoformat(),
    }
    import json

    return Response(
        f"event: progress\ndata: {json.dumps(payload)}\n\n", media_type="text/event-stream"
    )


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
async def get_run_adr(runId: UUID, request: Request) -> dict[str, Any]:
    found = request.app.state.analysis_store["adrs"].get(str(runId))
    if found is None:
        raise HTTPException(404, "ADR not found")
    return found


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
async def export_run_adr(runId: UUID, request: Request, format: str = "markdown") -> Response:
    adr = await get_run_adr(runId, request)
    if format == "json":
        return Response(
            AdrDraft.model_validate(adr).model_dump_json(), media_type="application/json"
        )
    return Response(
        f"# {adr['title']}\n\n## Decisão\n\n{adr['decision']}\n",
        media_type="text/markdown",
        headers={"Content-Disposition": "attachment; filename=adr.md"},
    )

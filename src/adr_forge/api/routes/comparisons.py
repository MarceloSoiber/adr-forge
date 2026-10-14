"""HTTP adapter for blind comparisons; pre-reveal DTOs never expose identities."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from adr_forge.api.routes.analysis import _run_repository
from adr_forge.evaluation.models import CandidateRun, RubricDimension, RubricVersion
from adr_forge.evaluation.service import (
    BlindComparisonService,
    EvaluationConflict,
    EvaluationRequired,
)
from adr_forge.shared.errors import ConflictError, NotFoundError, ValidationError

router = APIRouter(prefix="/api/v1")

class CreateComparisonRequest(BaseModel):
    run_ids: list[UUID] = Field(min_length=2)
    rubric_version_id: UUID
class SubmitEvaluationRequest(BaseModel):
    evaluator_id: str = Field(min_length=1, max_length=200)
    evaluator_type: str = "human"
    scores: dict[str, dict[str, int]]
    preference: str
    notes: str | None = Field(default=None, max_length=5000)
    supersedes_evaluation_id: UUID | None = None

def _store(request: Request) -> dict[UUID, object]:
    if not hasattr(request.app.state, "comparisons"):
        request.app.state.comparisons = {}
    return request.app.state.comparisons

@router.post("/comparisons", status_code=201)
async def create_comparison(command: CreateComparisonRequest, request: Request) -> dict[str, object]:
    runs = await _run_repository(request)
    candidates: list[CandidateRun] = []
    for run_id in command.run_ids:
        run = await runs.get(str(run_id)); adr = await runs.get_adr(str(run_id))
        if run is None or adr is None: raise NotFoundError("Completed run and ADR are required.")
        candidates.append(CandidateRun(run_id=run_id, scenario_revision_id=run["scenario_revision_id"], status=run["status"], adr={key: value for key, value in adr.items() if key not in {"id", "analysis_run_id", "created_at"}}, strategy_id=run["strategy_id"], strategy_version=run["strategy_version"], generation_config_hash="0" * 64))
    rubric = RubricVersion(id=command.rubric_version_id, name="local", version="1", dimensions=[RubricDimension(key="quality", description="Qualidade", minimum=1, maximum=5, anchors={"1": "fraca", "5": "forte"})])
    comparison = BlindComparisonService().create(candidates=candidates, rubric=rubric)
    _store(request)[comparison.id] = comparison
    return _blinded(comparison)

@router.get("/comparisons/{comparison_id}")
async def get_comparison(comparison_id: UUID, request: Request) -> dict[str, object]: return _blinded(_comparison(comparison_id, request))

@router.post("/comparisons/{comparison_id}/evaluation", status_code=201)
async def submit_evaluation(comparison_id: UUID, command: SubmitEvaluationRequest, request: Request) -> dict[str, object]:
    try: result = _comparison(comparison_id, request).submit(**command.model_dump())
    except EvaluationConflict as error: raise ConflictError(str(error)) from error
    except ValueError as error: raise ValidationError(str(error)) from error
    return result.model_dump(mode="json")

@router.get("/comparisons/{comparison_id}/reveal")
async def reveal(comparison_id: UUID, request: Request) -> dict[str, object]:
    try: value = _comparison(comparison_id, request).reveal()
    except EvaluationRequired as error: raise ConflictError(str(error)) from error
    return {"comparison_id": comparison_id, "evaluation_id": value.evaluation_id, "candidates": [{"label": chr(65 + index), "run_id": candidate.run_id, "strategy_id": candidate.strategy_id, "strategy_version": candidate.strategy_version, "retrieval_snapshot_id": candidate.retrieval_snapshot_id, "generation_config_hash": candidate.generation_config_hash} for index, candidate in enumerate(value.candidates)]}

def _comparison(identity: UUID, request: Request):
    value = _store(request).get(identity)
    if value is None: raise NotFoundError("Comparison not found.")
    return value
def _blinded(comparison) -> dict[str, object]:
    value = comparison.blinded()
    return {"id": comparison.id, "candidates": [{"label": item.label, "adr": item.adr} for item in value.candidates], "rubric": comparison.rubric.model_dump(mode="json"), "evaluated": value.evaluated, "current_evaluation_id": comparison.history()[-1].id if comparison.history() else None}

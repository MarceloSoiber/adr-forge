"""HTTP adapter for blind comparisons; pre-reveal DTOs never expose identities."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field

from adr_forge.api.routes.analysis import _run_repository
from adr_forge.decisions.schemas import (
    ADRStatus,
    Alternative,
    Assumption,
    RationaleLink,
    ReviewTrigger,
    Risk,
    UnresolvedQuestion,
)
from adr_forge.evaluation.models import CandidateRun, RubricDimension, RubricVersion
from adr_forge.evaluation.repository import EvaluationRepository
from adr_forge.evaluation.service import (
    BlindComparisonService,
    Comparison,
    EvaluationConflict,
    EvaluationRequired,
)
from adr_forge.shared.errors import ConflictError, NotFoundError, ValidationError

router = APIRouter(prefix="/api/v1")


class CreateComparisonRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_ids: list[UUID] = Field(min_length=2)
    rubric_version_id: UUID


class SubmitEvaluationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evaluator_id: str = Field(min_length=1, max_length=200)
    evaluator_type: Literal["human", "llm_assisted", "deterministic"] = "human"
    scores: dict[str, dict[str, int]]
    preference: str
    notes: str | None = Field(default=None, max_length=5000)
    supersedes_evaluation_id: UUID | None = None


class BlindedAdrDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    title: str = Field(min_length=3, max_length=200)
    status: ADRStatus
    context: list[str] = Field(min_length=1)
    facts: list[str]
    assumptions: list[Assumption]
    unresolved_questions: list[UnresolvedQuestion] = Field(max_length=3)
    constraints: list[str]
    alternatives: list[Alternative]
    decision: str | None
    rationale: list[RationaleLink]
    positive_consequences: list[str]
    negative_consequences: list[str]
    risks: list[Risk]
    review_triggers: list[ReviewTrigger]
    confidence: float = Field(ge=0, le=1)
    reference_ids: list[str]


class BlindedCandidateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(pattern=r"^[A-Z][A-Z0-9]{0,7}$")
    adr: BlindedAdrDraft


class BlindComparisonResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    candidates: list[BlindedCandidateResponse] = Field(min_length=2)
    rubric: dict[str, object]
    evaluated: bool
    current_evaluation_id: UUID | None


def _repository(request: Request) -> EvaluationRepository:
    return EvaluationRepository(request.app.state.session_factory)


@router.post(
    "/comparisons",
    status_code=201,
    operation_id="createBlindComparison",
    response_model=BlindComparisonResponse,
)
async def create_comparison(
    command: CreateComparisonRequest, request: Request
) -> BlindComparisonResponse:
    runs = await _run_repository(request)
    candidates: list[CandidateRun] = []
    for run_id in command.run_ids:
        run = await runs.get(str(run_id))
        adr = await runs.get_adr(str(run_id))
        if run is None or adr is None:
            raise NotFoundError("Completed run and ADR are required.")
        candidates.append(
            CandidateRun(
                run_id=run_id,
                scenario_revision_id=run["scenario_revision_id"],
                status=run["status"],
                adr={
                    key: value
                    for key, value in adr.items()
                    if key not in {"id", "analysis_run_id", "created_at"}
                },
                strategy_id=run["strategy_id"],
                strategy_version=run["strategy_version"],
                generation_config_hash="0" * 64,
            )
        )
    rubric = RubricVersion(
        id=command.rubric_version_id,
        name="local",
        version="1",
        dimensions=[
            RubricDimension(
                key="quality",
                description="Qualidade",
                minimum=1,
                maximum=5,
                anchors={"1": "fraca", "5": "forte"},
            )
        ],
    )
    comparison = BlindComparisonService().create(candidates=candidates, rubric=rubric)
    await _repository(request).save_comparison(comparison)
    return _blinded(comparison)


@router.get(
    "/comparisons/{comparisonId}",
    operation_id="getBlindComparison",
    response_model=BlindComparisonResponse,
)
async def get_comparison(comparisonId: UUID, request: Request) -> BlindComparisonResponse:
    return _blinded(await _comparison(comparisonId, request))


@router.post(
    "/comparisons/{comparisonId}/evaluation",
    status_code=201,
    operation_id="submitBlindEvaluation",
)
async def submit_evaluation(
    comparisonId: UUID, command: SubmitEvaluationRequest, request: Request
) -> dict[str, object]:
    try:
        comparison = await _comparison(comparisonId, request)
        result = comparison.submit(**command.model_dump())
        await _repository(request).append_evaluation(result)
    except EvaluationConflict as error:
        raise ConflictError(str(error)) from error
    except ValueError as error:
        raise ValidationError(str(error)) from error
    return cast(dict[str, object], result.model_dump(mode="json"))


@router.get("/comparisons/{comparisonId}/reveal", operation_id="revealComparisonIdentities")
async def reveal(comparisonId: UUID, request: Request) -> dict[str, object]:
    try:
        value = (await _comparison(comparisonId, request)).reveal()
    except EvaluationRequired as error:
        raise ConflictError(str(error)) from error
    return {
        "comparison_id": comparisonId,
        "evaluation_id": value.evaluation_id,
        "candidates": [
            {
                "label": revealed.label,
                "run_id": revealed.candidate.run_id,
                "strategy_id": revealed.candidate.strategy_id,
                "strategy_version": revealed.candidate.strategy_version,
                "retrieval_snapshot_id": revealed.candidate.retrieval_snapshot_id,
                "generation_config_hash": revealed.candidate.generation_config_hash,
            }
            for revealed in value.candidates
        ],
    }


async def _comparison(identity: UUID, request: Request) -> Comparison:
    value = await _repository(request).get_comparison(identity)
    if value is None:
        raise NotFoundError("Comparison not found.")
    return value


def _blinded(comparison: Comparison) -> BlindComparisonResponse:
    value = comparison.blinded()
    return BlindComparisonResponse(
        id=comparison.id,
        candidates=[{"label": item.label, "adr": item.adr} for item in value.candidates],
        rubric=comparison.rubric.model_dump(mode="json"),
        evaluated=value.evaluated,
        current_evaluation_id=comparison.history()[-1].id if comparison.history() else None,
    )

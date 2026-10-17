"""HTTP adapter for blind comparisons; pre-reveal DTOs never expose identities."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator

from adr_forge.api.routes.analysis import PROBLEM, _run_repository
from adr_forge.decisions.schemas import (
    ADRDraft,
    ADRStatus,
    Alternative,
    Assumption,
    RationaleLink,
    ReviewTrigger,
    Risk,
    UnresolvedQuestion,
)
from adr_forge.evaluation.models import (
    CandidateRun,
    EvaluationResult,
    RubricDefinition,
    RubricDimension,
    RubricVersion,
)
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

    @model_validator(mode="after")
    def run_ids_are_unique(self) -> CreateComparisonRequest:
        if len(set(self.run_ids)) != len(self.run_ids):
            raise ValueError("run_ids must be unique")
        return self


class SubmitEvaluationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evaluator_id: str = Field(min_length=1, max_length=200)
    evaluator_type: Literal["human", "llm_assisted", "deterministic"]
    judge_model_identity: dict[str, str] | None = None
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


class BlindedCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(pattern=r"^[A-Z][A-Z0-9]{0,7}$")
    adr: BlindedAdrDraft


class BlindComparison(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    candidates: list[BlindedCandidate] = Field(min_length=2)
    rubric: RubricDefinition
    evaluated: bool
    current_evaluation_id: UUID | None


class RevealedCandidateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    run_id: UUID
    strategy_id: str
    strategy_version: str
    retrieval_snapshot_id: UUID | None
    generation_config_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class ComparisonReveal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    comparison_id: UUID
    evaluation_id: UUID
    candidates: list[RevealedCandidateResponse] = Field(min_length=2)


def _repository(request: Request) -> EvaluationRepository:
    return EvaluationRepository(request.app.state.session_factory)


@router.post(
    "/comparisons",
    status_code=201,
    operation_id="createBlindComparison",
    response_model=BlindComparison,
    responses={404: PROBLEM, 409: PROBLEM, 422: PROBLEM},
)
async def create_comparison(
    command: CreateComparisonRequest, request: Request
) -> BlindComparison:
    runs = await _run_repository(request)
    candidates: list[CandidateRun] = []
    for run_id in command.run_ids:
        run = await runs.get(str(run_id))
        adr = await runs.get_adr(str(run_id))
        if run is None or adr is None:
            raise NotFoundError("Completed run and ADR are required.")
        try:
            validated_adr = ADRDraft.model_validate(adr)
        except ValueError as error:
            raise ValidationError("Completed run has no valid ADR.") from error
        candidates.append(
            CandidateRun(
                run_id=run_id,
                scenario_revision_id=run["scenario_revision_id"],
                status=run["status"],
                adr=validated_adr.model_dump(
                    mode="json", exclude={"id", "analysis_run_id", "created_at"}
                ),
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
    response_model=BlindComparison,
    responses={404: PROBLEM},
)
async def get_comparison(comparisonId: UUID, request: Request) -> BlindComparison:
    return _blinded(await _comparison(comparisonId, request))


@router.post(
    "/comparisons/{comparisonId}/evaluation",
    status_code=201,
    operation_id="submitBlindEvaluation",
    response_model=EvaluationResult,
    responses={404: PROBLEM, 409: PROBLEM, 422: PROBLEM},
)
async def submit_evaluation(
    comparisonId: UUID, command: SubmitEvaluationRequest, request: Request
) -> EvaluationResult:
    try:
        comparison = await _comparison(comparisonId, request)
        result = comparison.submit(**command.model_dump())
        await _repository(request).append_evaluation(result)
    except EvaluationConflict as error:
        raise ConflictError(str(error)) from error
    except ValueError as error:
        raise ValidationError(str(error)) from error
    return result


@router.get(
    "/comparisons/{comparisonId}/reveal",
    operation_id="revealComparisonIdentities",
    response_model=ComparisonReveal,
    responses={404: PROBLEM, 409: PROBLEM},
)
async def reveal(comparisonId: UUID, request: Request) -> ComparisonReveal:
    try:
        value = (await _comparison(comparisonId, request)).reveal()
    except EvaluationRequired as error:
        raise ConflictError(str(error)) from error
    return ComparisonReveal(
        comparison_id=comparisonId,
        evaluation_id=value.evaluation_id,
        candidates=[
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
    )


async def _comparison(identity: UUID, request: Request) -> Comparison:
    value = await _repository(request).get_comparison(identity)
    if value is None:
        raise NotFoundError("Comparison not found.")
    return value


def _blinded(comparison: Comparison) -> BlindComparison:
    value = comparison.blinded()
    return BlindComparison(
        id=comparison.id,
        candidates=[{"label": item.label, "adr": item.adr} for item in value.candidates],
        rubric=comparison.rubric.model_dump(mode="json", exclude={"published_at"}),
        evaluated=value.evaluated,
        current_evaluation_id=comparison.history()[-1].id if comparison.history() else None,
    )

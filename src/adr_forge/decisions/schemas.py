"""Closed, versioned schemas for generated architecture decision records."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class _Schema(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ADRStatus(StrEnum):
    PROVISIONAL = "provisional"
    PROPOSED = "proposed"


class EvidenceKind(StrEnum):
    FACT = "fact"
    ASSUMPTION = "assumption"
    REFERENCE = "reference"


class ReviewOperator(StrEnum):
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    EQ = "eq"


class Assumption(_Schema):
    id: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    impact: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)


class UnresolvedQuestion(_Schema):
    id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    impact: str = Field(min_length=1)


class Alternative(_Schema):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    viable: bool
    rejection_reason: str | None = None
    benefits: list[str] = Field(default_factory=list)
    drawbacks: list[str] = Field(default_factory=list)
    constraint_ids: list[str] = Field(default_factory=list)


class RationaleLink(_Schema):
    claim: str = Field(min_length=1)
    evidence_kind: EvidenceKind
    evidence_id: str = Field(min_length=1)


class Risk(_Schema):
    description: str = Field(min_length=1)
    likelihood: Literal["low", "medium", "high"]
    impact: Literal["low", "medium", "high"]
    mitigation: str = Field(min_length=1)


class ReviewTrigger(_Schema):
    metric: str = Field(min_length=1)
    operator: ReviewOperator
    threshold: float
    unit: str = Field(min_length=1)


class ADRDraft(_Schema):
    id: UUID = Field(default_factory=uuid4)
    analysis_run_id: UUID
    schema_version: str = Field(min_length=1)
    title: str = Field(min_length=3, max_length=200)
    status: ADRStatus
    context: list[str] = Field(min_length=1)
    facts: list[str] = Field(default_factory=list)
    assumptions: list[Assumption] = Field(default_factory=list)
    unresolved_questions: list[UnresolvedQuestion] = Field(default_factory=list, max_length=3)
    constraints: list[str] = Field(default_factory=list)
    alternatives: list[Alternative] = Field(default_factory=list)
    decision: str | None = None
    rationale: list[RationaleLink] = Field(default_factory=list)
    positive_consequences: list[str] = Field(default_factory=list)
    negative_consequences: list[str] = Field(default_factory=list)
    risks: list[Risk] = Field(default_factory=list)
    review_triggers: list[ReviewTrigger] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    reference_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

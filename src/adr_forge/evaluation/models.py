"""Domain models that keep strategy identity hidden until evaluation is immutable."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EvaluatorType(StrEnum):
    HUMAN = "human"
    LLM_ASSISTED = "llm_assisted"
    DETERMINISTIC = "deterministic"


class RubricDimension(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    key: str = Field(min_length=1)
    description: str = Field(min_length=1)
    minimum: int
    maximum: int
    anchors: dict[str, str]

    @model_validator(mode="after")
    def valid_bounds(self) -> RubricDimension:
        if self.minimum > self.maximum:
            raise ValueError("rubric minimum must not exceed maximum")
        return self


class RubricDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: UUID
    name: str
    version: str
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    dimensions: list[RubricDimension] = Field(min_length=1)


class RubricVersion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: UUID = Field(default_factory=uuid4)
    name: str
    version: str
    dimensions: list[RubricDimension] = Field(min_length=1)


class CandidateRun(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    run_id: UUID
    scenario_revision_id: UUID
    status: str
    adr: dict[str, object]
    strategy_id: str
    strategy_version: str
    generation_config_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    retrieval_snapshot_id: UUID | None = None


class ComparisonCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    label: str = Field(pattern=r"^[A-Z][A-Z0-9]{0,7}$")
    run_id: UUID
    adr: dict[str, object]
    strategy_id: str
    strategy_version: str
    generation_config_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    retrieval_snapshot_id: UUID | None = None


class BlindComparison(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: UUID = Field(default_factory=uuid4)
    rubric: RubricDefinition
    candidates: list[ComparisonCandidate] = Field(min_length=2)
    current_evaluation_id: UUID | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def distinct_candidates(self) -> BlindComparison:
        if len({candidate.run_id for candidate in self.candidates}) != len(self.candidates):
            raise ValueError("comparison candidates must have distinct runs")
        if len({candidate.label for candidate in self.candidates}) != len(self.candidates):
            raise ValueError("comparison labels must be unique")
        return self

    @staticmethod
    def random_label(existing: set[str]) -> str:
        while True:
            label = "C" + secrets.token_hex(3).upper()
            if label not in existing:
                return label

    def blinded_projection(self) -> dict[str, object]:
        return {
            "id": self.id,
            "candidates": [{"label": item.label, "adr": item.adr} for item in self.candidates],
            "rubric": self.rubric.model_dump(mode="json"),
            "evaluated": self.current_evaluation_id is not None,
            "current_evaluation_id": self.current_evaluation_id,
        }


class EvaluationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: UUID = Field(default_factory=uuid4)
    comparison_id: UUID
    rubric_version_id: UUID
    evaluator_id: str = Field(min_length=1, max_length=200)
    evaluator_type: EvaluatorType
    judge_model_identity: dict[str, str] | None = None
    scores: dict[str, dict[str, int]]
    preference: str
    notes: str | None = Field(default=None, max_length=5000)
    supersedes_evaluation_id: UUID | None = None
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

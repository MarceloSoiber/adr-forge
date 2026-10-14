"""Immutable, validated scenario entities for decision analysis."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, cast
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

from adr_forge.scenarios.clarification import ClarificationAnswer
from adr_forge.shared.hashing import canonical_sha256


class DecisionCategory(StrEnum):
    SQL_VS_NOSQL = "sql_vs_nosql"
    SYNC_VS_ASYNC = "sync_vs_async"
    MODULAR_MONOLITH_VS_MICROSERVICES = "modular_monolith_vs_microservices"
    CONTAINERS_VS_SERVERLESS_VS_TRADITIONAL = "containers_vs_serverless_vs_traditional"
    UNSUPPORTED = "unsupported"


_CATEGORY_ORDER = {category: position for position, category in enumerate(DecisionCategory)}
ShortText = Annotated[str, Field(min_length=1, max_length=500)]
LongText = Annotated[str, Field(min_length=1, max_length=2000)]


def classify_categories(categories: list[DecisionCategory]) -> list[DecisionCategory]:
    """Return categories in public enum order, or the sole unsupported category."""
    supported = sorted(
        {category for category in categories if category != DecisionCategory.UNSUPPORTED},
        key=_CATEGORY_ORDER.__getitem__,
    )
    return cast(list[DecisionCategory], supported or [DecisionCategory.UNSUPPORTED])


class DecisionScenario(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    title: str = Field(min_length=3, max_length=200)
    language: str = "pt-BR"
    current_revision_number: int = Field(default=1, ge=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("language")
    @classmethod
    def require_initial_portuguese(cls, value: str) -> str:
        if value != "pt-BR":
            raise ValueError("initial scenario language must be pt-BR")
        return value


class ScenarioRevision(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    scenario_id: UUID
    revision_number: int = Field(ge=1)
    problem: str = Field(min_length=20, max_length=20_000)
    facts: list[LongText] = Field(default_factory=list, max_length=50)
    constraints: list[LongText] = Field(default_factory=list, max_length=50)
    desired_qualities: list[ShortText] = Field(default_factory=list, max_length=20)
    candidate_alternatives: list[ShortText] = Field(default_factory=list, max_length=20)
    clarification_answers: list[ClarificationAnswer] = Field(default_factory=list)
    categories: list[DecisionCategory] = Field(min_length=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator(
        "problem",
        "facts",
        "constraints",
        "desired_qualities",
        "candidate_alternatives",
        mode="before",
    )
    @classmethod
    def trim_strings(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, list):
            return [item.strip() if isinstance(item, str) else item for item in value]
        return value

    @model_validator(mode="after")
    def validate_categories(self) -> ScenarioRevision:
        normalized = classify_categories(self.categories)
        if self.categories != normalized:
            raise ValueError(
                "categories must be unique, enum ordered, and unsupported only when alone"
            )
        return self

    @computed_field(return_type=str)  # type: ignore[prop-decorator]
    @property
    def content_hash(self) -> str:
        return canonical_sha256(
            {
                "problem": self.problem,
                "facts": self.facts,
                "constraints": self.constraints,
                "desired_qualities": self.desired_qualities,
                "candidate_alternatives": self.candidate_alternatives,
                "clarification_answers": [
                    answer.model_dump(mode="json") for answer in self.clarification_answers
                ],
                "categories": self.categories,
            }
        )

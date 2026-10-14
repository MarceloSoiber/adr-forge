"""Immutable clarification answer value objects."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ClarificationAnswerReference(BaseModel):
    """Client input; the server resolves question prose and impact from the ADR."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    question_id: str = Field(min_length=1)
    answer: str = Field(min_length=1, max_length=5_000)
    source_run_id: UUID

    @field_validator("question_id", "answer")
    @classmethod
    def require_non_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be blank")
        return value


class ClarificationAnswer(ClarificationAnswerReference):
    """Authoritative answer snapshot persisted in a scenario revision."""

    question: str = Field(min_length=1, max_length=2_000)
    impact: str = Field(min_length=1, max_length=2_000)

    @field_validator("question", "impact")
    @classmethod
    def require_snapshot_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("snapshot text must not be blank")
        return value

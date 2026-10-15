"""Immutable, reviewed training-example metadata."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from adr_forge.scenarios.models import DecisionCategory
from adr_forge.shared.hashing import canonical_sha256


class SourceType(StrEnum):
    AUTHORED = "authored"
    SYNTHETIC = "synthetic"
    PUBLIC_SOURCE_DERIVED = "public_source_derived"


class ReviewStatus(StrEnum):
    DRAFT = "draft"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class DatasetExample(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID = Field(default_factory=uuid4)
    scenario_revision_id: UUID
    target_adr_artifact_id: UUID | None = None
    source_type: SourceType
    source_uri: str | None = None
    license: str = Field(min_length=1, max_length=500)
    language: str = "pt-BR"
    categories: list[DecisionCategory] = Field(min_length=1)
    lineage_parent_ids: list[UUID] = Field(default_factory=list)
    review_status: ReviewStatus = ReviewStatus.DRAFT
    reviewed_by: str | None = Field(default=None, min_length=1, max_length=200)
    reviewed_at: datetime | None = None
    prompt: str = Field(min_length=1, max_length=20_000)
    completion: str = Field(min_length=1, max_length=40_000)

    @model_validator(mode="after")
    def governed_fields(self) -> DatasetExample:
        if self.language != "pt-BR":
            raise ValueError("dataset examples must use pt-BR")
        if self.source_type == SourceType.PUBLIC_SOURCE_DERIVED and not self.source_uri:
            raise ValueError("public-source-derived examples require source_uri")
        terminal = {ReviewStatus.APPROVED, ReviewStatus.REJECTED}
        if self.review_status in terminal and (not self.reviewed_by or not self.reviewed_at):
            raise ValueError("terminal review status requires reviewer and timestamp")
        if self.review_status not in terminal and (self.reviewed_by or self.reviewed_at):
            raise ValueError("only terminal review status may contain reviewer metadata")
        if len(set(self.lineage_parent_ids)) != len(self.lineage_parent_ids):
            raise ValueError("lineage parents must be unique")
        return self

    @property
    def content_hash(self) -> str:
        return canonical_sha256(
            {"prompt": self.prompt, "completion": self.completion, "categories": self.categories}
        )

    def transition_review(
        self, status: ReviewStatus, *, reviewed_by: str | None = None
    ) -> DatasetExample:
        allowed = {
            ReviewStatus.DRAFT: {ReviewStatus.UNDER_REVIEW},
            ReviewStatus.UNDER_REVIEW: {ReviewStatus.APPROVED, ReviewStatus.REJECTED},
        }
        if status not in allowed.get(self.review_status, set()):
            raise ValueError("illegal dataset review transition")
        values = {
            "review_status": status,
            "reviewed_by": reviewed_by,
            "reviewed_at": datetime.now(UTC)
            if status in {ReviewStatus.APPROVED, ReviewStatus.REJECTED}
            else None,
        }
        return self.model_copy(update=values)

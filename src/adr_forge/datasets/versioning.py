"""Immutable dataset release and partition membership model."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DatasetVersionStatus(StrEnum):
    BUILDING = "building"
    VALIDATING = "validating"
    PUBLISHED = "published"
    REJECTED = "rejected"


class DatasetSplit(StrEnum):
    TRAIN = "train"
    VALIDATION = "validation"
    EVALUATION = "evaluation"


class DatasetMembership(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    dataset_version_id: UUID
    example_id: UUID
    split: DatasetSplit
    lineage_group_id: str = Field(min_length=1, max_length=200)


class DatasetVersion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=3, max_length=200)
    status: DatasetVersionStatus = DatasetVersionStatus.BUILDING
    manifest_hash: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    memberships: list[DatasetMembership] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    published_at: datetime | None = None

    @model_validator(mode="after")
    def membership_integrity(self) -> DatasetVersion:
        keys = {member.example_id for member in self.memberships}
        if len(keys) != len(self.memberships):
            raise ValueError("an example can belong to exactly one split")
        if self.status == DatasetVersionStatus.PUBLISHED and (
            not self.manifest_hash or not self.published_at
        ):
            raise ValueError("published dataset requires immutable manifest hash and timestamp")
        return self

    def transition(
        self, status: DatasetVersionStatus, *, manifest_hash: str | None = None
    ) -> DatasetVersion:
        allowed = {
            DatasetVersionStatus.BUILDING: {
                DatasetVersionStatus.VALIDATING,
                DatasetVersionStatus.REJECTED,
            },
            DatasetVersionStatus.VALIDATING: {
                DatasetVersionStatus.PUBLISHED,
                DatasetVersionStatus.REJECTED,
            },
        }
        if status not in allowed.get(self.status, set()):
            raise ValueError("illegal dataset version transition")
        return self.model_copy(
            update={
                "status": status,
                "manifest_hash": manifest_hash,
                "published_at": datetime.now(UTC)
                if status == DatasetVersionStatus.PUBLISHED
                else None,
            }
        )

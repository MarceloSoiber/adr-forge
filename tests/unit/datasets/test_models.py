"""Dataset example and version lifecycle contracts."""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from adr_forge.datasets.models import DatasetExample, ReviewStatus, SourceType
from adr_forge.datasets.versioning import (
    DatasetMembership,
    DatasetSplit,
    DatasetVersion,
    DatasetVersionStatus,
)
from adr_forge.scenarios.models import DecisionCategory


def _example(**changes: object) -> DatasetExample:
    payload: dict[str, object] = {
        "scenario_revision_id": uuid4(),
        "source_type": SourceType.AUTHORED,
        "license": "CC-BY-4.0",
        "language": "pt-BR",
        "categories": [DecisionCategory.SQL_VS_NOSQL],
        "lineage_parent_ids": [],
        "prompt": "Precisamos escolher entre SQL e NoSQL para o catálogo.",
        "completion": "Escolha SQL para as transações do catálogo.",
    }
    payload.update(changes)
    return DatasetExample(**payload)


def test_dataset_example_requires_governed_metadata_and_a_portuguese_category() -> None:
    example = _example()

    assert example.review_status is ReviewStatus.DRAFT
    assert example.content_hash
    assert len(example.content_hash) == 64

    for invalid in (
        {"license": ""},
        {"language": "en-US"},
        {"categories": []},
        {"source_type": SourceType.PUBLIC_SOURCE_DERIVED, "source_uri": None},
    ):
        with pytest.raises(ValidationError):
            _example(**invalid)


def test_terminal_review_requires_reviewer_and_timestamp_and_does_not_mutate_example() -> None:
    example = _example()
    under_review = example.transition_review(ReviewStatus.UNDER_REVIEW)

    with pytest.raises(ValueError, match="reviewed"):
        under_review.transition_review(ReviewStatus.APPROVED)

    approved = under_review.transition_review(ReviewStatus.APPROVED, reviewed_by="marcela")

    assert approved.review_status is ReviewStatus.APPROVED
    assert approved.reviewed_by == "marcela"
    assert approved.reviewed_at is not None
    assert example.review_status is ReviewStatus.DRAFT
    with pytest.raises(ValueError, match="terminal"):
        approved.transition_review(ReviewStatus.REJECTED, reviewed_by="marcela")


def test_dataset_version_publishing_freezes_manifest_and_membership() -> None:
    version = DatasetVersion(name="adr-decisions")
    membership = DatasetMembership(
        dataset_version_id=version.id,
        example_id=uuid4(),
        split=DatasetSplit.TRAIN,
        lineage_group_id="family-1",
    )
    validating = version.model_copy(update={"memberships": [membership]})
    published = validating.transition(DatasetVersionStatus.VALIDATING).transition(
        DatasetVersionStatus.PUBLISHED,
        manifest_hash="a" * 64,
    )

    assert published.status is DatasetVersionStatus.PUBLISHED
    assert published.manifest_hash == "a" * 64
    assert published.memberships == [membership]
    assert version.status is DatasetVersionStatus.BUILDING
    with pytest.raises(ValueError, match="published|immutable"):
        published.transition(DatasetVersionStatus.REJECTED)


def test_membership_assigns_an_example_to_exactly_one_valid_partition() -> None:
    version_id = uuid4()
    example_id = uuid4()

    membership = DatasetMembership(
        dataset_version_id=version_id,
        example_id=example_id,
        split=DatasetSplit.EVALUATION,
        lineage_group_id="family-1",
    )
    assert membership.split is DatasetSplit.EVALUATION

    with pytest.raises(ValidationError):
        DatasetMembership(
            dataset_version_id=version_id,
            example_id=example_id,
            split=[DatasetSplit.TRAIN, DatasetSplit.EVALUATION],
            lineage_group_id="family-2",
        )

"""Governance findings make dataset publication decisions auditable."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from adr_forge.datasets.governance import FindingCode, validate_governance
from adr_forge.datasets.models import DatasetExample, ReviewStatus, SourceType


def _example(
    *,
    source_type: SourceType = SourceType.AUTHORED,
    source_uri: str | None = None,
    license: str = "CC-BY-4.0",
    review_status: ReviewStatus = ReviewStatus.APPROVED,
    content: str = "Uma API interna precisa guardar pedidos e manter auditoria.",
) -> DatasetExample:
    example = DatasetExample(
        scenario_revision_id=uuid4(),
        source_type=source_type,
        source_uri=source_uri,
        license=license,
        language="pt-BR",
        categories=["sql_vs_nosql"],
        lineage_parent_ids=[],
        content=content,
    )
    if review_status is ReviewStatus.APPROVED:
        return example.transition_review(
            ReviewStatus.APPROVED,
            reviewed_by="reviewer@example.test",
            reviewed_at=datetime(2026, 10, 15, 12, tzinfo=UTC),
        )
    return example.transition_review(review_status)


def _codes(examples: list[DatasetExample]) -> set[FindingCode]:
    return {finding.code for finding in validate_governance(examples)}


def test_governance_accepts_complete_authorized_provenance() -> None:
    assert validate_governance([_example()]) == []


@pytest.mark.parametrize(
    ("candidate", "expected_code"),
    [
        (
            lambda: _example(source_type=SourceType.PUBLIC_SOURCE_DERIVED),
            FindingCode.MISSING_PROVENANCE,
        ),
        (lambda: _example(license=""), FindingCode.MISSING_LICENSE),
        (lambda: _example(license="LicenseRef-unauthorized"), FindingCode.UNAUTHORIZED_SOURCE),
        (
            lambda: _example(
                source_type=SourceType.SYNTHETIC,
                review_status=ReviewStatus.UNDER_REVIEW,
            ),
            FindingCode.UNREVIEWED_SYNTHETIC,
        ),
    ],
)
def test_governance_reports_blocking_provenance_license_and_review_findings(
    candidate: Callable[[], DatasetExample], expected_code: FindingCode
) -> None:
    assert expected_code in _codes([candidate()])


def test_governance_flags_suspected_sensitive_content_for_human_review() -> None:
    candidate = _example(content="Use o cartão 4111 1111 1111 1111 para pagamento.")

    findings = validate_governance([candidate])

    sensitive = [finding for finding in findings if finding.code is FindingCode.SUSPECTED_SENSITIVE]
    assert len(sensitive) == 1
    assert sensitive[0].example_id == candidate.id
    assert sensitive[0].requires_human_review is True


def test_governance_does_not_mutate_candidate_records_while_producing_findings() -> None:
    candidate = _example(license="")
    original_hash = candidate.content_hash
    original_status = candidate.review_status

    validate_governance([candidate])

    assert candidate.content_hash == original_hash
    assert candidate.review_status is original_status

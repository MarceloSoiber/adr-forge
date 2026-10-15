"""Dataset provenance and privacy gates."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from adr_forge.datasets.models import DatasetExample, ReviewStatus, SourceType

_SENSITIVE_PATTERNS = (
    re.compile(r"\b(?:\d{3}[.-]?\d{3}[.-]?\d{3}[.-]?\d{2})\b"),
    re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
    re.compile(r"\b(?:senha|password|token|api[_ -]?key)\b", re.IGNORECASE),
)


class FindingCode(StrEnum):
    MISSING_PROVENANCE = "missing_provenance"
    MISSING_LICENSE = "missing_license"
    UNAUTHORIZED_SOURCE = "unauthorized_source"
    UNREVIEWED_SYNTHETIC = "unreviewed_synthetic"
    SUSPECTED_SENSITIVE = "suspected_sensitive"


@dataclass(frozen=True)
class GovernanceFinding:
    code: FindingCode
    example_id: UUID
    blocking: bool
    requires_human_review: bool
    detail: str


def validate_example(example: DatasetExample) -> list[GovernanceFinding]:
    findings: list[GovernanceFinding] = []
    if not example.license.strip():
        findings.append(
            GovernanceFinding(
                FindingCode.MISSING_LICENSE, example.id, True, False, "A license is required."
            )
        )
    if example.source_type == SourceType.PUBLIC_SOURCE_DERIVED and not example.source_uri:
        findings.append(
            GovernanceFinding(
                FindingCode.MISSING_PROVENANCE,
                example.id,
                True,
                False,
                "Public source requires URI.",
            )
        )
    if example.license.casefold().startswith("licenseref-"):
        findings.append(
            GovernanceFinding(
                FindingCode.UNAUTHORIZED_SOURCE,
                example.id,
                True,
                False,
                "The source license is not authorized for training.",
            )
        )
    if (
        example.source_type == SourceType.SYNTHETIC
        and example.review_status != ReviewStatus.APPROVED
    ):
        findings.append(
            GovernanceFinding(
                FindingCode.UNREVIEWED_SYNTHETIC,
                example.id,
                True,
                False,
                "Synthetic content requires approval.",
            )
        )
    content = "\n".join(filter(None, (example.content, example.prompt, example.completion)))
    if any(pattern.search(content) for pattern in _SENSITIVE_PATTERNS):
        findings.append(
            GovernanceFinding(
                FindingCode.SUSPECTED_SENSITIVE,
                example.id,
                True,
                True,
                "Potential sensitive data.",
            )
        )
    return findings


def validate_governance(examples: list[DatasetExample]) -> list[GovernanceFinding]:
    """Return immutable, auditable governance findings for candidate examples."""

    return [finding for example in examples for finding in validate_example(example)]

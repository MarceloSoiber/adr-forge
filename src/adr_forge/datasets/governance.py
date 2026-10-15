"""Dataset provenance and privacy gates."""

from __future__ import annotations

import re
from dataclasses import dataclass

from adr_forge.datasets.models import DatasetExample, ReviewStatus, SourceType

_SENSITIVE_PATTERNS = (
    re.compile(r"\b(?:\d{3}[.-]?\d{3}[.-]?\d{3}[.-]?\d{2})\b"),
    re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
    re.compile(r"\b(?:senha|password|token|api[_ -]?key)\b", re.IGNORECASE),
)


@dataclass(frozen=True)
class GovernanceFinding:
    code: str
    blocking: bool
    detail: str


def validate_example(example: DatasetExample) -> list[GovernanceFinding]:
    findings: list[GovernanceFinding] = []
    if not example.license.strip():
        findings.append(GovernanceFinding("license_missing", True, "A license is required."))
    if example.source_type == SourceType.PUBLIC_SOURCE_DERIVED and not example.source_uri:
        findings.append(
            GovernanceFinding("source_uri_missing", True, "Public source requires URI.")
        )
    if (
        example.source_type == SourceType.SYNTHETIC
        and example.review_status != ReviewStatus.APPROVED
    ):
        findings.append(
            GovernanceFinding("synthetic_unreviewed", True, "Synthetic content requires approval.")
        )
    content = f"{example.prompt}\n{example.completion}"
    if any(pattern.search(content) for pattern in _SENSITIVE_PATTERNS):
        findings.append(
            GovernanceFinding("sensitive_content_suspected", True, "Potential sensitive data.")
        )
    return findings

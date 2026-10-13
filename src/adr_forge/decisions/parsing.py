"""Structured ADR parsing with at most one caller-supplied repair attempt."""

from __future__ import annotations

import json
from dataclasses import dataclass
from uuid import UUID

from pydantic import ValidationError as PydanticValidationError

from adr_forge.decisions.schemas import ADRDraft
from adr_forge.decisions.validation import ValidationFinding, validate_adr_draft


@dataclass(frozen=True, slots=True)
class ParseResult:
    draft: ADRDraft | None
    findings: list[ValidationFinding]
    parse_succeeded: bool


def parse_adr_output(raw_output: str, analysis_run_id: UUID) -> ParseResult:
    """Parse a model response without altering its content or inventing fields."""
    try:
        payload = json.loads(raw_output)
    except json.JSONDecodeError as error:
        return ParseResult(
            draft=None,
            parse_succeeded=False,
            findings=[
                ValidationFinding(
                    code="output.invalid_json",
                    path="/",
                    severity="error",
                    message=f"Model output is not JSON: {error.msg}",
                )
            ],
        )
    if not isinstance(payload, dict):
        return ParseResult(
            draft=None,
            parse_succeeded=False,
            findings=[
                ValidationFinding(
                    code="output.invalid_type",
                    path="/",
                    severity="error",
                    message="Model output must be a JSON object.",
                )
            ],
        )
    payload["analysis_run_id"] = str(analysis_run_id)
    try:
        draft = ADRDraft.model_validate(payload)
    except PydanticValidationError as error:
        return ParseResult(
            draft=None,
            parse_succeeded=False,
            findings=[
                ValidationFinding(
                    code="output.schema_invalid",
                    path="/",
                    severity="error",
                    message=item["msg"],
                )
                for item in error.errors()
            ],
        )
    findings = validate_adr_draft(draft)
    return ParseResult(draft=draft, findings=findings, parse_succeeded=True)

"""Strict structured ADR parsing."""

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


def parse_adr_output(
    raw_output: str, analysis_run_id: UUID, *, answered_questions: list[str] | None = None
) -> ParseResult:
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
                    path=_json_pointer(item["loc"]),
                    severity="error",
                    message=_validation_message(item),
                )
                for item in error.errors()
            ],
        )
    findings = validate_adr_draft(draft, answered_questions=answered_questions)
    return ParseResult(draft=draft, findings=findings, parse_succeeded=True)


def _json_pointer(location: object) -> str:
    if not isinstance(location, tuple) or not location:
        return "/"
    escaped = (str(part).replace("~", "~0").replace("/", "~1") for part in location)
    return "/" + "/".join(escaped)


def _validation_message(error: object) -> str:
    if not isinstance(error, dict):
        return "Valor inválido."
    error_type = error.get("type")
    if error_type == "missing":
        return "Campo obrigatório ausente."
    if error_type == "extra_forbidden":
        return f"Campo não permitido. Valor recebido: {_input_preview(error.get('input'))}."
    message = error.get("msg", "Valor inválido.")
    return f"{message} Valor recebido: {_input_preview(error.get('input'))}."


def _input_preview(value: object) -> str:
    rendered = json.dumps(value, ensure_ascii=False, default=str)
    return rendered if len(rendered) <= 160 else f"{rendered[:157]}..."

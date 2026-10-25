"""Strict structured ADR parsing."""

from __future__ import annotations

import json
import re
import unicodedata
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
    raw_output: str,
    analysis_run_id: UUID,
    *,
    answered_questions: list[str] | None = None,
    source_context: str | None = None,
) -> ParseResult:
    """Parse a model response while preserving its original captured content."""
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
    normalization_findings = _normalize_model_equivalents(
        payload,
        answered_questions=answered_questions or [],
        source_context=source_context,
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
    findings = [
        *normalization_findings,
        *validate_adr_draft(draft, answered_questions=answered_questions),
    ]
    return ParseResult(draft=draft, findings=findings, parse_succeeded=True)


def _normalize_model_equivalents(
    payload: dict[str, object], *, answered_questions: list[str], source_context: str | None
) -> list[ValidationFinding]:
    """Canonicalize a few unambiguous model representations at the parsing boundary."""
    findings: list[ValidationFinding] = []
    context = payload.get("context")
    if isinstance(context, list) and not context and source_context and source_context.strip():
        payload["context"] = [source_context.strip()]
        findings.append(
            _normalized_finding(
                "/context",
                "Empty context was restored from the source scenario.",
            )
        )

    constraints = payload.get("constraints")
    if isinstance(constraints, list):
        normalized_constraints: list[object] = []
        for index, constraint in enumerate(constraints):
            if isinstance(constraint, dict):
                text = constraint.get("text")
                if isinstance(text, str) and text.strip():
                    normalized_constraints.append(text.strip())
                    findings.append(
                        _normalized_finding(
                            f"/constraints/{index}",
                            "Constraint object was converted to its text value.",
                        )
                    )
                    continue
            normalized_constraints.append(constraint)
        payload["constraints"] = normalized_constraints

    confidence_aliases = {"low": 0.25, "medium": 0.5, "high": 0.75}
    assumptions = payload.get("assumptions")
    if isinstance(assumptions, list):
        for index, assumption in enumerate(assumptions):
            if not isinstance(assumption, dict):
                continue
            confidence = assumption.get("confidence")
            if isinstance(confidence, str) and confidence.casefold() in confidence_aliases:
                assumption["confidence"] = confidence_aliases[confidence.casefold()]
                findings.append(
                    _normalized_finding(
                        f"/assumptions/{index}/confidence",
                        "Qualitative confidence was converted to a numeric score.",
                    )
                )

    risks = payload.get("risks")
    if isinstance(risks, list):
        for index, risk in enumerate(risks):
            if not isinstance(risk, dict):
                continue
            for field in ("likelihood", "impact"):
                value = risk.get(field)
                if (
                    isinstance(value, (int, float))
                    and not isinstance(value, bool)
                    and 0 <= value <= 1
                ):
                    probability = float(value)
                    risk[field] = (
                        "low"
                        if probability < 1 / 3
                        else "medium"
                        if probability < 2 / 3
                        else "high"
                    )
                    findings.append(
                        _normalized_finding(
                            f"/risks/{index}/{field}",
                            f"Numeric {field} was converted to the ADR risk scale.",
                        )
                    )

    operator_aliases = {">": "gt", ">=": "gte", "<": "lt", "<=": "lte", "=": "eq", "==": "eq"}
    triggers = payload.get("review_triggers")
    if isinstance(triggers, list):
        for index, trigger in enumerate(triggers):
            if not isinstance(trigger, dict):
                continue
            operator = trigger.get("operator")
            if isinstance(operator, str) and operator in operator_aliases:
                trigger["operator"] = operator_aliases[operator]
                findings.append(
                    _normalized_finding(
                        f"/review_triggers/{index}/operator",
                        "Symbolic operator was converted to the ADR operator name.",
                    )
                )

    rationale = payload.get("rationale")
    if isinstance(rationale, list):
        for index, link in enumerate(rationale):
            if not isinstance(link, dict) or link.get("evidence_kind") != "fact":
                continue
            evidence_id = link.get("evidence_id")
            if isinstance(evidence_id, int) and not isinstance(evidence_id, bool):
                evidence_id = str(evidence_id)
            if isinstance(evidence_id, str) and evidence_id.isdigit():
                link["evidence_id"] = f"fact:{evidence_id}"
                findings.append(
                    _normalized_finding(
                        f"/rationale/{index}/evidence_id",
                        "Numeric fact ID was converted to the canonical fact reference.",
                    )
                )

    questions = payload.get("unresolved_questions", [])
    if payload.get("status") == "provisional" and isinstance(questions, list):
        answered = {_normalized_text(question) for question in answered_questions}
        remaining_questions: list[object] = []
        for index, question in enumerate(questions):
            text = question.get("question") if isinstance(question, dict) else None
            if isinstance(text, str) and _normalized_text(text) in answered:
                findings.append(
                    _normalized_finding(
                        f"/unresolved_questions/{index}",
                        "Question already answered by the user was removed.",
                    )
                )
            else:
                remaining_questions.append(question)

        if not remaining_questions:
            if isinstance(assumptions, list):
                for index, assumption in enumerate(assumptions[:3]):
                    if not isinstance(assumption, dict):
                        continue
                    statement = assumption.get("statement")
                    impact = assumption.get("impact")
                    if not isinstance(statement, str) or not statement.strip():
                        continue
                    if not isinstance(impact, str) or not impact.strip():
                        continue
                    assumption_id = str(assumption.get("id") or index)
                    confirmation = f"A premissa a seguir está correta? {statement}"
                    if _normalized_text(confirmation) in answered:
                        continue
                    remaining_questions.append(
                        {
                            "id": f"confirm-assumption-{assumption_id}",
                            "question": confirmation,
                            "impact": impact,
                        }
                    )
                    findings.append(
                        _normalized_finding(
                            f"/unresolved_questions/{len(remaining_questions) - 1}",
                            "Provisional assumption was converted to a confirmation question.",
                        )
                    )
                    break
            if not remaining_questions:
                candidates = (
                    (
                        "missing-alternatives",
                        "Quais alternativas técnicas devem ser comparadas antes da decisão?",
                        "As alternativas definem o espaço real de decisão.",
                    ),
                    (
                        "missing-review-criteria",
                        "Quais métricas objetivas devem determinar a revisão desta decisão?",
                        "Critérios mensuráveis permitem validar a decisão após o lançamento.",
                    ),
                    (
                        "missing-operational-risk",
                        "Qual risco operacional ainda precisa ser considerado nesta decisão?",
                        "Riscos pendentes podem alterar a recomendação e suas salvaguardas.",
                    ),
                )
                for question_id, question_text, impact in candidates:
                    if _normalized_text(question_text) in answered:
                        continue
                    remaining_questions.append(
                        {"id": question_id, "question": question_text, "impact": impact}
                    )
                    findings.append(
                        _normalized_finding(
                            "/unresolved_questions/0",
                            "A new decision gap replaced questions already answered.",
                        )
                    )
                    break
        payload["unresolved_questions"] = remaining_questions
    return findings


def _normalized_finding(path: str, message: str) -> ValidationFinding:
    return ValidationFinding(
        code="output.normalized", path=path, severity="warning", message=message
    )


def _normalized_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    without_accents = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", "", without_accents)


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

"""Shared deterministic validation for generated ADR drafts."""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

from adr_forge.decisions.schemas import ADRDraft, ADRStatus, EvidenceKind
from adr_forge.scenarios.models import ScenarioRevision


@dataclass(frozen=True, slots=True)
class ValidationFinding:
    code: str
    path: str
    severity: Literal["error", "warning"]
    message: str


def _error(code: str, path: str, message: str) -> ValidationFinding:
    return ValidationFinding(code=code, path=path, severity="error", message=message)


def validate_adr_draft(
    draft: ADRDraft, *, answered_questions: list[str] | None = None
) -> list[ValidationFinding]:
    """Return stable findings without changing the supplied immutable draft."""
    findings: list[ValidationFinding] = []
    viable_alternatives = sum(alternative.viable for alternative in draft.alternatives)
    constraint_ids = {f"constraint:{index}" for index, _ in enumerate(draft.constraints)}
    assumption_ids = {assumption.id for assumption in draft.assumptions}

    if draft.status == ADRStatus.PROPOSED:
        if not draft.decision:
            findings.append(
                _error("decision.required", "/decision", "A proposed ADR requires a decision.")
            )
        if not draft.constraints:
            findings.append(
                _error(
                    "constraints.required", "/constraints", "A proposed ADR requires a constraint."
                )
            )
        if viable_alternatives < 2:
            findings.append(
                _error(
                    "alternatives.minimum_viable",
                    "/alternatives",
                    "A proposed ADR requires at least two viable alternatives.",
                )
            )
        if not draft.rationale:
            findings.append(
                _error(
                    "rationale.required", "/rationale", "A proposed ADR requires rationale links."
                )
            )
        if not draft.positive_consequences:
            findings.append(
                _error(
                    "positive_consequences.required",
                    "/positive_consequences",
                    "A proposed ADR requires a positive consequence.",
                )
            )
        if not draft.negative_consequences:
            findings.append(
                _error(
                    "negative_consequences.required",
                    "/negative_consequences",
                    "A proposed ADR requires a negative consequence.",
                )
            )
        if not draft.review_triggers:
            findings.append(
                _error(
                    "review_triggers.required",
                    "/review_triggers",
                    "A proposed ADR requires a measurable review trigger.",
                )
            )
    if draft.status == ADRStatus.PROVISIONAL:
        if not draft.assumptions:
            findings.append(
                _error(
                    "assumptions.required",
                    "/assumptions",
                    "A provisional ADR requires assumptions.",
                )
            )
        if draft.confidence > 0.60:
            findings.append(
                _error(
                    "confidence.provisional_too_high",
                    "/confidence",
                    "A provisional ADR must not exceed 0.60 confidence.",
                )
            )
        question_ids = [question.id for question in draft.unresolved_questions]
        if len(question_ids) != len(set(question_ids)):
            findings.append(
                _error(
                    "questions.duplicate_id",
                    "/unresolved_questions",
                    "A provisional ADR must use unique question IDs.",
                )
            )
        if not 1 <= len(draft.unresolved_questions) <= 3:
            findings.append(
                _error(
                    "unresolved_questions.required",
                    "/unresolved_questions",
                    "A provisional ADR requires one to three unresolved questions.",
                )
            )
        resolved = {_normalized_question(question) for question in answered_questions or []}
        for index, question in enumerate(draft.unresolved_questions):
            if _normalized_question(question.question) in resolved:
                findings.append(
                    _error(
                        "unresolved_questions.already_answered",
                        f"/unresolved_questions/{index}/question",
                        "A clarification question must not repeat a question already answered.",
                    )
                )

    for index, alternative in enumerate(draft.alternatives):
        if not alternative.viable and not alternative.rejection_reason:
            findings.append(
                _error(
                    "alternatives.rejection_reason_required",
                    f"/alternatives/{index}/rejection_reason",
                    "A non-viable alternative requires a rejection reason.",
                )
            )
        for constraint_id in alternative.constraint_ids:
            if constraint_id not in constraint_ids:
                findings.append(
                    _error(
                        "alternatives.constraint_unknown",
                        f"/alternatives/{index}/constraint_ids",
                        "Alternative links an unknown constraint.",
                    )
                )
    for index, link in enumerate(draft.rationale):
        valid = (
            (
                link.evidence_kind == EvidenceKind.FACT
                and link.evidence_id
                in {f"fact:{position}" for position, _ in enumerate(draft.facts)}
            )
            or (
                link.evidence_kind == EvidenceKind.ASSUMPTION and link.evidence_id in assumption_ids
            )
            or (
                link.evidence_kind == EvidenceKind.CONSTRAINT and link.evidence_id in constraint_ids
            )
            or (
                link.evidence_kind == EvidenceKind.REFERENCE
                and link.evidence_id in draft.reference_ids
            )
        )
        if not valid:
            findings.append(
                _error(
                    "rationale.evidence_unknown",
                    f"/rationale/{index}/evidence_id",
                    "Rationale links unknown evidence.",
                )
            )
    for index, trigger in enumerate(draft.review_triggers):
        if not math.isfinite(trigger.threshold):
            findings.append(
                _error(
                    "review_triggers.threshold_finite",
                    f"/review_triggers/{index}/threshold",
                    "Review trigger threshold must be finite.",
                )
            )
    return findings


def _normalized_question(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    without_accents = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", "", without_accents)


def classify_context(scenario: ScenarioRevision) -> list[ValidationFinding]:
    """Identify context that requires an explicitly provisional analysis."""
    findings: list[ValidationFinding] = []
    if not scenario.facts or not scenario.constraints:
        findings.append(
            _error(
                "context.missing_critical",
                "/",
                "Critical facts or constraints are missing for a conclusive recommendation.",
            )
        )
    joined = " ".join([scenario.problem, *scenario.constraints]).casefold()
    if ("baixo custo" in joined or "sem custo" in joined) and (
        "alta disponibilidade" in joined or "disponibilidade 24" in joined
    ):
        findings.append(
            _error(
                "context.contradictory_constraints",
                "/constraints",
                "Cost and availability constraints require clarification.",
            )
        )
    if any(token in joined for token in ("obrigatoriamente usar", "deve usar", "forçado")):
        findings.append(
            ValidationFinding(
                code="context.forced_preference",
                path="/",
                severity="warning",
                message="A stated technology preference is evidence to challenge, not a decision.",
            )
        )
    return findings

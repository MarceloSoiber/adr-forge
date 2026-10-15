"""Stable, explainable quality checks for generated ADRs."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from adr_forge.decisions.schemas import ADRDraft
from adr_forge.decisions.validation import classify_context, validate_adr_draft
from adr_forge.scenarios.models import ScenarioRevision


class DeterministicFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    path: str
    severity: str
    message: str


class DeterministicEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    passed: bool
    findings: list[DeterministicFinding]

    def __iter__(self):  # type: ignore[no-untyped-def]
        return iter(self.findings)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, list):
            return self.findings == other
        return super().__eq__(other)


def _evaluate_mapping(adr: dict[str, object]) -> list[DeterministicFinding]:
    findings: list[DeterministicFinding] = []

    def require_list(key: str, code: str, message: str, minimum: int = 1) -> list[object]:
        value = adr.get(key)
        if not isinstance(value, list) or len(value) < minimum:
            findings.append(
                DeterministicFinding(code=code, path=f"/{key}", severity="error", message=message)
            )
            return []
        return value

    status = adr.get("status")
    require_list("context", "structure.context_missing", "ADR must describe its context.")
    alternatives = require_list(
        "alternatives", "alternatives.missing", "ADR must contain viable alternatives.", 2
    )
    if (
        alternatives
        and sum(isinstance(item, dict) and item.get("viable") is True for item in alternatives) < 2
    ):
        findings.append(
            DeterministicFinding(
                code="alternatives.viable_count",
                path="/alternatives",
                severity="error",
                message="ADR must contain at least two viable alternatives.",
            )
        )
    require_list(
        "negative_consequences",
        "consequences.negative_missing",
        "ADR must state negative consequences.",
    )
    require_list(
        "review_triggers", "review_triggers.missing", "ADR must define a measurable review trigger."
    )
    assumptions = adr.get("assumptions", [])
    if not isinstance(assumptions, list) or any(
        not isinstance(item, dict) or not item.get("id") for item in assumptions
    ):
        findings.append(
            DeterministicFinding(
                code="assumptions.unlabeled",
                path="/assumptions",
                severity="error",
                message="Assumptions must be explicitly labeled.",
            )
        )
    references = adr.get("reference_ids", [])
    if references is not None and not isinstance(references, list):
        findings.append(
            DeterministicFinding(
                code="references.invalid",
                path="/reference_ids",
                severity="error",
                message="References must be a list.",
            )
        )
    if status == "proposed":
        if not adr.get("decision"):
            findings.append(
                DeterministicFinding(
                    code="structure.decision_missing",
                    path="/decision",
                    severity="error",
                    message="A proposed ADR requires a decision.",
                )
            )
        if not isinstance(adr.get("constraints"), list) or not adr["constraints"]:
            findings.append(
                DeterministicFinding(
                    code="context.constraints_missing",
                    path="/constraints",
                    severity="error",
                    message="A conclusive ADR requires constraints.",
                )
            )
    if status == "provisional" and not adr.get("unresolved_questions"):
        findings.append(
            DeterministicFinding(
                code="context.questions_missing",
                path="/unresolved_questions",
                severity="error",
                message="A provisional ADR must request missing context.",
            )
        )
    return findings


def evaluate_adr(
    adr: ADRDraft | dict[str, object], scenario: ScenarioRevision | None = None
) -> DeterministicEvaluation:
    """Apply the same structural checks used by application validation."""
    if isinstance(adr, ADRDraft):
        source = validate_adr_draft(adr)
        if scenario is not None:
            source = [*classify_context(scenario), *source]
        findings = [
            DeterministicFinding(
                code=item.code, path=item.path, severity=item.severity, message=item.message
            )
            for item in source
        ]
    else:
        findings = _evaluate_mapping(adr)
    return DeterministicEvaluation(
        passed=not any(item.severity == "error" for item in findings), findings=findings
    )


def aggregate_findings(
    findings: list[DeterministicFinding] | DeterministicEvaluation,
) -> DeterministicEvaluation:
    if isinstance(findings, DeterministicEvaluation):
        return findings
    return DeterministicEvaluation(
        passed=not any(item.severity == "error" for item in findings), findings=findings
    )

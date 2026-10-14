"""Contracts for deterministic ADR evaluation shared by application and benchmarks."""

from __future__ import annotations

from uuid import uuid4

from adr_forge.decisions.schemas import (
    ADRDraft,
    ADRStatus,
    Alternative,
    Assumption,
    EvidenceKind,
    RationaleLink,
    ReviewOperator,
    ReviewTrigger,
    UnresolvedQuestion,
)
from adr_forge.evaluation.deterministic import aggregate_findings, evaluate_adr
from adr_forge.scenarios.models import DecisionCategory, DecisionScenario, ScenarioRevision


def _draft(**changes: object) -> ADRDraft:
    values: dict[str, object] = {
        "analysis_run_id": uuid4(),
        "schema_version": "adr-v1",
        "title": "Persistencia relacional para o catalogo",
        "status": ADRStatus.PROPOSED,
        "context": ["O catalogo e parte central do produto."],
        "facts": ["O catalogo possui dados relacionais."],
        "constraints": ["Operacao deve ser auditavel."],
        "alternatives": [
            Alternative(
                id="postgres",
                name="PostgreSQL",
                summary="Banco relacional gerenciado.",
                viable=True,
                benefits=["Transacoes"],
                drawbacks=["Administracao"],
                constraint_ids=["constraint:0"],
            ),
            Alternative(
                id="document",
                name="Banco de documentos",
                summary="Armazenamento orientado a documentos.",
                viable=True,
                benefits=["Esquema flexivel"],
                drawbacks=["Consistencia adicional"],
                constraint_ids=["constraint:0"],
            ),
        ],
        "decision": "Adotar PostgreSQL gerenciado.",
        "rationale": [
            RationaleLink(
                claim="A integridade relacional atende a auditoria.",
                evidence_kind=EvidenceKind.FACT,
                evidence_id="fact:0",
            )
        ],
        "positive_consequences": ["Transacoes consistentes."],
        "negative_consequences": ["Havera custo operacional."],
        "review_triggers": [
            ReviewTrigger(
                metric="latencia_p95",
                operator=ReviewOperator.GT,
                threshold=200,
                unit="ms",
            )
        ],
        "confidence": 0.8,
    }
    values.update(changes)
    return ADRDraft(**values)


def _incomplete_scenario() -> ScenarioRevision:
    scenario = DecisionScenario(title="Decisao de persistencia")
    return ScenarioRevision(
        scenario_id=scenario.id,
        revision_number=1,
        problem="Precisamos escolher a persistencia do catalogo.",
        categories=[DecisionCategory.SQL_VS_NOSQL],
    )


def _codes(result: object) -> set[str]:
    return {finding.code for finding in result.findings}  # type: ignore[union-attr]


def test_valid_conclusive_adr_has_no_deterministic_findings_and_is_reproducible() -> None:
    draft = _draft()
    first = evaluate_adr(draft)
    second = evaluate_adr(draft)

    assert first.passed is True
    assert first.findings == []
    assert second == first
    assert aggregate_findings(first).passed is True
    assert aggregate_findings(first).findings == []


def test_evaluator_reports_required_structure_and_required_adr_sections() -> None:
    findings = evaluate_adr(
        _draft(
            decision=None,
            constraints=[],
            alternatives=[],
            rationale=[],
            positive_consequences=[],
            negative_consequences=[],
            review_triggers=[],
        ),
    )

    assert findings.passed is False
    assert _codes(findings) >= {
        "decision.required",
        "constraints.required",
        "alternatives.minimum_viable",
        "rationale.required",
        "positive_consequences.required",
        "negative_consequences.required",
        "review_triggers.required",
    }


def test_evaluator_requires_assumption_labels_and_questions_for_missing_context() -> None:
    provisional = _draft(
        status=ADRStatus.PROVISIONAL,
        decision=None,
        assumptions=[],
        unresolved_questions=[],
        confidence=0.7,
    )

    findings = evaluate_adr(provisional, _incomplete_scenario())

    assert findings.passed is False
    assert _codes(findings) >= {
        "context.missing_critical",
        "assumptions.required",
        "unresolved_questions.required",
        "confidence.provisional_too_high",
    }


def test_evaluator_accepts_provisional_adr_with_explicit_assumption_and_question() -> None:
    provisional = _draft(
        status=ADRStatus.PROVISIONAL,
        decision=None,
        assumptions=[
            Assumption(
                id="assumption:traffic",
                statement="O volume inicial sera moderado.",
                impact="Dimensionamento inicial.",
                confidence=0.4,
            )
        ],
        unresolved_questions=[
            UnresolvedQuestion(
                id="question:volume",
                question="Qual e o volume esperado?",
                impact="Define capacidade e custo.",
            )
        ],
        confidence=0.6,
    )

    findings = evaluate_adr(provisional)

    assert "assumptions.required" not in _codes(findings)
    assert "unresolved_questions.required" not in _codes(findings)
    assert "confidence.provisional_too_high" not in _codes(findings)


def test_evaluator_validates_assumption_and_reference_evidence_links() -> None:
    draft = _draft(
        assumptions=[
            Assumption(
                id="assumption:load",
                statement="A carga inicial sera previsivel.",
                impact="Permite iniciar com capacidade menor.",
                confidence=0.5,
            )
        ],
        reference_ids=["ref:managed-postgres"],
        rationale=[
            RationaleLink(
                claim="A carga previsivel reduz o risco inicial.",
                evidence_kind=EvidenceKind.ASSUMPTION,
                evidence_id="assumption:load",
            ),
            RationaleLink(
                claim="O servico gerenciado suporta a opcao.",
                evidence_kind=EvidenceKind.REFERENCE,
                evidence_id="ref:managed-postgres",
            ),
            RationaleLink(
                claim="Esta afirmacao nao tem evidencia valida.",
                evidence_kind=EvidenceKind.REFERENCE,
                evidence_id="ref:absent",
            ),
        ],
    )

    findings = evaluate_adr(draft)

    evidence_findings = [
        finding for finding in findings.findings if finding.code == "rationale.evidence_unknown"
    ]
    assert len(evidence_findings) == 1
    assert evidence_findings[0].path == "/rationale/2/evidence_id"

from __future__ import annotations

from math import inf, nan
from uuid import uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from adr_forge.decisions.schemas import (
    ADRDraft,
    Alternative,
    Assumption,
    RationaleLink,
    ReviewTrigger,
    UnresolvedQuestion,
)
from adr_forge.decisions.validation import validate_adr_draft


def _proposed_draft() -> ADRDraft:
    return ADRDraft(
        id=uuid4(),
        analysis_run_id=uuid4(),
        schema_version="adr-v1",
        title="Persistir eventos de pedidos",
        status="proposed",
        context=["O serviço precisa processar pedidos com rastreabilidade."],
        facts=["A equipe mantém PostgreSQL."],
        assumptions=[],
        unresolved_questions=[],
        constraints=["O orçamento operacional é limitado."],
        alternatives=[
            Alternative(
                id="postgres",
                name="PostgreSQL",
                summary="Persistir eventos transacionais no banco relacional existente.",
                viable=True,
                benefits=["A equipe já opera a tecnologia."],
                drawbacks=["Exige particionamento ao crescer."],
                constraint_ids=["constraint:0"],
            ),
            Alternative(
                id="kafka",
                name="Kafka",
                summary="Usar um log distribuído para os eventos.",
                viable=True,
                benefits=["Oferece retenção e desacoplamento."],
                drawbacks=["Aumenta a complexidade operacional."],
                constraint_ids=["constraint:0"],
            ),
        ],
        decision="Usar PostgreSQL inicialmente.",
        rationale=[
            RationaleLink(
                claim="A opção reduz o custo operacional inicial.",
                evidence_kind="fact",
                evidence_id="fact:0",
            )
        ],
        positive_consequences=["Menor curva operacional inicial."],
        negative_consequences=["O particionamento exigirá revisão futura."],
        risks=[],
        review_triggers=[
            ReviewTrigger(
                metric="eventos_por_dia", operator="gte", threshold=1_000_000, unit="eventos/dia"
            )
        ],
        confidence=0.8,
        reference_ids=[],
    )


def _finding_codes(draft: ADRDraft) -> set[str]:
    return {finding.code for finding in validate_adr_draft(draft)}


def _validated_copy(draft: ADRDraft, **updates: object) -> ADRDraft:
    values = draft.model_dump(mode="python")
    values.update(updates)
    return ADRDraft.model_validate(values)


def test_proposed_adr_requires_two_viable_alternatives() -> None:
    original = _proposed_draft()
    draft = original.model_copy(update={"alternatives": [original.alternatives[0]]})

    assert "alternatives.minimum_viable" in _finding_codes(draft)


def test_rationale_accepts_an_existing_constraint_as_evidence() -> None:
    draft = _validated_copy(
        _proposed_draft(),
        rationale=[
            RationaleLink(
                claim="A opção respeita o orçamento operacional.",
                evidence_kind="constraint",
                evidence_id="constraint:0",
            )
        ],
    )

    assert "rationale.evidence_unknown" not in _finding_codes(draft)


def test_rationale_rejects_an_unknown_constraint_as_evidence() -> None:
    draft = _validated_copy(
        _proposed_draft(),
        rationale=[
            RationaleLink(
                claim="A opção respeita uma restrição inexistente.",
                evidence_kind="constraint",
                evidence_id="constraint:99",
            )
        ],
    )

    assert "rationale.evidence_unknown" in _finding_codes(draft)


def test_provisional_adr_rejects_a_question_already_answered() -> None:
    question = UnresolvedQuestion(
        id="integrity",
        question="Como garantir a integridade dos dados financeiros?",
        impact="Define os controles transacionais.",
    )
    draft = _validated_copy(
        _proposed_draft(),
        status="provisional",
        decision=None,
        assumptions=[
            Assumption(
                id="uncertain",
                statement="A resposta ainda precisa ser aplicada à decisão.",
                impact="Mantém a recomendação provisória.",
                confidence=0.5,
            )
        ],
        unresolved_questions=[question],
        confidence=0.5,
    )

    findings = validate_adr_draft(draft, answered_questions=[question.question])

    assert "unresolved_questions.already_answered" in {finding.code for finding in findings}


def test_proposed_adr_requires_negative_consequences() -> None:
    draft = _proposed_draft().model_copy(update={"negative_consequences": []})

    assert "negative_consequences.required" in _finding_codes(draft)


def test_proposed_adr_requires_a_measurable_review_trigger() -> None:
    draft = _proposed_draft().model_copy(update={"review_triggers": []})

    assert "review_triggers.required" in _finding_codes(draft)


@pytest.mark.parametrize("threshold", [nan, inf, -inf])
def test_review_trigger_threshold_must_be_finite(threshold: float) -> None:
    trigger = ReviewTrigger(metric="latencia_p95", operator="lte", threshold=threshold, unit="ms")
    draft = _proposed_draft().model_copy(update={"review_triggers": [trigger]})

    assert "review_triggers.threshold_finite" in _finding_codes(draft)


@given(question_count=st.integers(min_value=4, max_value=10))
def test_provisional_adr_rejects_more_than_three_unresolved_questions(question_count: int) -> None:
    questions = [
        UnresolvedQuestion(
            id=f"question-{index}",
            question=f"Qual é a restrição pendente {index}?",
            impact="A resposta pode alterar a recomendação.",
        )
        for index in range(question_count)
    ]

    with pytest.raises(ValidationError, match="unresolved_questions"):
        _validated_copy(
            _proposed_draft(),
            status="provisional",
            decision=None,
            assumptions=[
                Assumption(
                    id="assumption-0",
                    statement="O volume inicial é moderado.",
                    impact="Permite uma decisão provisória.",
                    confidence=0.4,
                )
            ],
            unresolved_questions=questions,
        )

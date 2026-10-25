from __future__ import annotations

from uuid import uuid4

from adr_forge.scenarios.clarification import ClarificationAnswer
from adr_forge.scenarios.models import DecisionCategory, ScenarioRevision
from adr_forge.shared.adr_prompt import build_adr_prompt, build_adr_repair_prompt
from adr_forge.strategies.base import build_adr_prompt as build_strategy_prompt


def test_prompt_carries_answered_clarifications_and_avoids_repetition() -> None:
    prompt = build_adr_prompt(
        "Escolher a persistência para pagamentos.",
        ["A equipe já opera PostgreSQL."],
        ["A integridade financeira é obrigatória."],
        ["PostgreSQL", "MongoDB"],
        [
            "Pergunta: Qual volume deve ser suportado?\n"
            "Impacto: O volume muda a topologia.\n"
            "Resposta: Até 20 mil transações por minuto."
        ],
    )

    assert "Até 20 mil transações por minuto." in prompt
    assert "Não repita perguntas que já tenham uma resposta acima." in prompt
    assert "conclua o ADR" in prompt


def test_prompt_describes_the_nested_adr_contract() -> None:
    prompt = build_adr_prompt("Escolher a persistência.", [], [], [])

    assert 'schema_version deve ser "adr-v1"' in prompt
    assert "context, facts, constraints" in prompt
    assert "context deve conter pelo menos um item" in prompt
    assert "constraints deve conter somente textos" in prompt
    assert "confidence de cada assumption deve ser um número" in prompt
    assert "Cada assumption é {id, statement, impact, confidence}" in prompt
    assert "unresolved_question é {id, question, impact}" in prompt
    assert 'evidence_kind aceita somente "fact", "assumption", "constraint"' in prompt
    assert 'restrições usam "constraint:0", "constraint:1"' in prompt
    assert "qualquer texto antes ou depois do JSON" in prompt
    assert 'likelihood e impact aceitam somente as strings "low", "medium" ou "high"' in prompt
    assert 'fatos usam "fact:0", "fact:1"' in prompt


def test_strategy_prompt_includes_persisted_clarification_answers() -> None:
    scenario = ScenarioRevision(
        scenario_id=uuid4(),
        revision_number=2,
        problem="Escolher a persistência para pagamentos.",
        facts=[],
        constraints=[],
        desired_qualities=[],
        candidate_alternatives=[],
        categories=[DecisionCategory.UNSUPPORTED],
        clarification_answers=[
            ClarificationAnswer(
                question_id="volume",
                question="Qual volume deve ser suportado?",
                impact="O volume muda a topologia.",
                answer="Até 20 mil transações por minuto.",
                source_run_id=uuid4(),
            )
        ],
    )

    prompt = build_strategy_prompt(scenario)

    assert "Resposta: Até 20 mil transações por minuto." in prompt


def test_repair_prompt_preserves_the_raw_response_and_validation_findings() -> None:
    prompt = build_adr_repair_prompt(
        build_adr_prompt("Escolher a persistência.", [], [], []),
        '{"status":"provisional","unresolved_questions":[]}',
        [
            {
                "code": "unresolved_questions.required",
                "path": "/unresolved_questions",
                "severity": "error",
                "message": "A provisional ADR requires one to three unresolved questions.",
            }
        ],
    )

    assert '"unresolved_questions":[]' in prompt
    assert "unresolved_questions.required" in prompt
    assert "nunca retorne unresolved_questions vazio" in prompt
    assert '"id":"pergunta-1"' in prompt
    assert "remova notas, explicações" in prompt
    assert 'evidence_kind deve ser somente "fact", "assumption", "constraint"' in prompt
    assert "Converta likelihood e impact numéricos" in prompt
    assert "constraints deve ser uma lista de strings" in prompt
    assert "Não repita em unresolved_questions" in prompt

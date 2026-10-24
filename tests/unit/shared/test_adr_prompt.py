from __future__ import annotations

from uuid import uuid4

from adr_forge.scenarios.clarification import ClarificationAnswer
from adr_forge.scenarios.models import DecisionCategory, ScenarioRevision
from adr_forge.shared.adr_prompt import build_adr_prompt
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

from __future__ import annotations

import json
from uuid import uuid4

import pytest

from adr_forge.scenarios.clarification import ClarificationAnswer
from adr_forge.scenarios.models import DecisionCategory, ScenarioRevision
from adr_forge.strategies.fake import FakeStrategy
from adr_forge.system.progress import CancellationToken


@pytest.mark.asyncio
async def test_fake_strategy_does_not_repeat_answered_clarification_question() -> None:
    scenario = ScenarioRevision(
        scenario_id=uuid4(),
        revision_number=2,
        problem="Escolher a persistência inicial.",
        facts=[],
        constraints=[],
        desired_qualities=[],
        candidate_alternatives=[],
        categories=[DecisionCategory.UNSUPPORTED],
        clarification_answers=[
            ClarificationAnswer(
                question_id="context-scale",
                question="Qual é a escala esperada de uso e dados?",
                impact="Define capacidade e custo operacional.",
                answer="Até vinte mil transações por minuto.",
                source_run_id=uuid4(),
            )
        ],
    )

    generated = await FakeStrategy().generate(scenario, cancellation=CancellationToken())
    questions = json.loads(generated.raw_output)["unresolved_questions"]

    assert [question["id"] for question in questions] == ["context-constraints"]

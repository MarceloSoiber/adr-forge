from __future__ import annotations

from uuid import uuid4

import pytest

from adr_forge.scenarios.models import DecisionCategory, ScenarioRevision
from adr_forge.strategies.fake import FakeStrategy
from adr_forge.system.progress import CancellationToken


@pytest.mark.asyncio
async def test_generate_does_not_mutate_scenario_when_completing_alternatives() -> None:
    scenario = ScenarioRevision(
        scenario_id=uuid4(),
        revision_number=1,
        problem="Precisamos escolher uma arquitetura que mantenha o sistema operável.",
        candidate_alternatives=["Monólito modular"],
        categories=[DecisionCategory.MODULAR_MONOLITH_VS_MICROSERVICES],
    )
    original_content = scenario.model_dump()
    original_content_hash = scenario.content_hash

    await FakeStrategy().generate(scenario, cancellation=CancellationToken())

    assert scenario.model_dump() == original_content
    assert scenario.content_hash == original_content_hash

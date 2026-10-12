from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from adr_forge.scenarios.models import (
    DecisionCategory,
    DecisionScenario,
    ScenarioRevision,
    classify_categories,
)


def _revision(*, categories: list[DecisionCategory]) -> ScenarioRevision:
    return ScenarioRevision(
        scenario_id=uuid4(),
        revision_number=1,
        problem="Precisamos escolher uma arquitetura que mantenha o sistema operável.",
        facts=["A equipe opera o sistema em horário comercial."],
        constraints=["O orçamento mensal é limitado."],
        desired_qualities=["operabilidade"],
        candidate_alternatives=["monólito modular", "microsserviços"],
        categories=categories,
    )


def test_first_revision_is_immutable_and_numbered_one() -> None:
    scenario = DecisionScenario(title="Escolha de arquitetura")
    revision = _revision(categories=[DecisionCategory.MODULAR_MONOLITH_VS_MICROSERVICES])

    assert scenario.current_revision_number == 1
    assert revision.revision_number == 1
    with pytest.raises((ValidationError, TypeError)):
        revision.problem = "Outro problema"  # type: ignore[misc]


def test_canonical_content_hash_excludes_identity_but_preserves_content() -> None:
    first = _revision(categories=[DecisionCategory.SQL_VS_NOSQL])
    second = _revision(categories=[DecisionCategory.SQL_VS_NOSQL])

    assert first.scenario_id != second.scenario_id
    assert first.content_hash == second.content_hash
    changed = first.model_copy(update={"facts": ["O tráfego é imprevisível."]})
    assert changed.content_hash != first.content_hash


def test_duplicate_hash_is_rejected_per_scenario() -> None:
    scenario_id = uuid4()
    first = ScenarioRevision(
        scenario_id=scenario_id,
        revision_number=1,
        problem="Precisamos escolher uma arquitetura que mantenha o sistema operável.",
        categories=[DecisionCategory.SQL_VS_NOSQL],
    )
    duplicate = first.model_copy(update={"revision_number": 2})

    assert first.scenario_id == duplicate.scenario_id
    assert first.content_hash == duplicate.content_hash


@pytest.mark.parametrize(
    ("matched", "expected"),
    [
        ([DecisionCategory.SQL_VS_NOSQL], [DecisionCategory.SQL_VS_NOSQL]),
        (
            [
                DecisionCategory.CONTAINERS_VS_SERVERLESS_VS_TRADITIONAL,
                DecisionCategory.SYNC_VS_ASYNC,
            ],
            [
                DecisionCategory.SYNC_VS_ASYNC,
                DecisionCategory.CONTAINERS_VS_SERVERLESS_VS_TRADITIONAL,
            ],
        ),
        ([], [DecisionCategory.UNSUPPORTED]),
    ],
)
def test_category_classification_normalizes_supported_and_unsupported_values(
    matched: list[DecisionCategory], expected: list[DecisionCategory]
) -> None:
    assert classify_categories(matched) == expected


def test_unsupported_cannot_be_combined_with_supported_category() -> None:
    with pytest.raises(ValidationError, match="unsupported"):
        _revision(
            categories=[DecisionCategory.UNSUPPORTED, DecisionCategory.SQL_VS_NOSQL],
        )

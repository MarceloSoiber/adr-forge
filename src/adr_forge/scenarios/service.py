"""Scenario creation and retrieval use cases."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from adr_forge.scenarios.models import (
    DecisionCategory,
    DecisionScenario,
    ScenarioRevision,
    classify_categories,
)
from adr_forge.scenarios.repository import ScenarioRepository
from adr_forge.shared.errors import NotFoundError, ValidationError

CategoryClassifier = Callable[[str], list[DecisionCategory]]


class CreateScenarioInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=3, max_length=200)
    language: str = "pt-BR"
    problem: str = Field(min_length=20, max_length=20_000)
    facts: list[str] = Field(default_factory=list, max_length=50)
    constraints: list[str] = Field(default_factory=list, max_length=50)
    desired_qualities: list[str] = Field(default_factory=list, max_length=20)
    candidate_alternatives: list[str] = Field(default_factory=list, max_length=20)


def classify_supported_categories(problem: str) -> list[DecisionCategory]:
    """Classify the initial supported Portuguese decision families deterministically."""
    text = problem.casefold()
    matched: list[DecisionCategory] = []
    if "sql" in text and ("nosql" in text or "no sql" in text):
        matched.append(DecisionCategory.SQL_VS_NOSQL)
    if "síncron" in text and "assíncron" in text:
        matched.append(DecisionCategory.SYNC_VS_ASYNC)
    if ("monólito" in text or "monolito" in text) and "microserv" in text:
        matched.append(DecisionCategory.MODULAR_MONOLITH_VS_MICROSERVICES)
    if "container" in text and ("serverless" in text or "tradicional" in text):
        matched.append(DecisionCategory.CONTAINERS_VS_SERVERLESS_VS_TRADITIONAL)
    return classify_categories(matched)


class ScenarioService:
    def __init__(
        self,
        repository: ScenarioRepository,
        classifier: CategoryClassifier = classify_supported_categories,
    ) -> None:
        self._repository = repository
        self._classifier = classifier

    async def create(
        self, command: CreateScenarioInput
    ) -> tuple[DecisionScenario, ScenarioRevision]:
        request_size = len(command.model_dump_json().encode("utf-8"))
        if request_size > 100 * 1024:
            raise ValidationError("Scenario request body must not exceed 100 KiB.")
        scenario = DecisionScenario(title=command.title, language=command.language)
        revision = ScenarioRevision(
            scenario_id=scenario.id,
            revision_number=1,
            problem=command.problem,
            facts=command.facts,
            constraints=command.constraints,
            desired_qualities=command.desired_qualities,
            candidate_alternatives=command.candidate_alternatives,
            categories=classify_categories(self._classifier(command.problem)),
        )
        await self._repository.create_first(scenario, revision)
        return scenario, revision

    async def get_current(
        self, scenario_id: UUID | str
    ) -> tuple[DecisionScenario, ScenarioRevision]:
        found = await self._repository.get(str(scenario_id))
        if found is None:
            raise NotFoundError("No scenario has this identifier.")
        return found

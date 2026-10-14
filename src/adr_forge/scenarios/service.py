"""Scenario creation and retrieval use cases."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from adr_forge.scenarios.clarification import ClarificationAnswer, ClarificationAnswerReference
from adr_forge.scenarios.models import (
    DecisionCategory,
    DecisionScenario,
    ScenarioRevision,
    classify_categories,
)
from adr_forge.scenarios.repository import ScenarioRepository
from adr_forge.shared.errors import NotFoundError, StaleRevisionError, ValidationError

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


class CreateRevisionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_revision_number: int = Field(ge=1)
    clarification_answers: list[ClarificationAnswerReference] = Field(min_length=1, max_length=3)

    @model_validator(mode="after")
    def require_unique_questions(self) -> CreateRevisionInput:
        ids = [answer.question_id for answer in self.clarification_answers]
        if len(ids) != len(set(ids)):
            raise ValueError("clarification question IDs must be unique")
        return self


def classify_supported_categories(problem: str) -> list[DecisionCategory]:
    """Classify the initial supported Portuguese decision families deterministically."""
    text = problem.casefold()
    matched: list[DecisionCategory] = []
    if ("sql" in text and ("nosql" in text or "no sql" in text)) or (
        "postgres" in text and "mongo" in text
    ):
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
            categories=classify_categories(
                self._classifier(f"{command.problem} {' '.join(command.candidate_alternatives)}")
            ),
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

    async def create_clarification_revision(
        self,
        scenario_id: UUID | str,
        command: CreateRevisionInput,
        answers: list[ClarificationAnswer],
    ) -> ScenarioRevision:
        """Append authoritative clarification snapshots without changing base evidence."""
        request_size = len(command.model_dump_json().encode("utf-8"))
        if request_size > 100 * 1024:
            raise ValidationError("Clarification request body must not exceed 100 KiB.")
        scenario, base = await self.get_current(scenario_id)
        if base.revision_number != command.base_revision_number:
            raise StaleRevisionError("Reload the scenario and deliberately rebase answers.")
        if len(answers) != len(command.clarification_answers):
            raise ValidationError("Every clarification answer must resolve to source evidence.")
        expected = {
            (item.question_id, item.source_run_id) for item in command.clarification_answers
        }
        actual = {(item.question_id, item.source_run_id) for item in answers}
        if actual != expected:
            raise ValidationError("Clarification answer provenance does not match the request.")
        revision = ScenarioRevision(
            scenario_id=scenario.id,
            revision_number=base.revision_number + 1,
            problem=base.problem,
            facts=base.facts,
            constraints=base.constraints,
            desired_qualities=base.desired_qualities,
            candidate_alternatives=base.candidate_alternatives,
            clarification_answers=[*base.clarification_answers, *answers],
            categories=base.categories,
        )
        if not await self._repository.append_revision(scenario, base, revision):
            raise StaleRevisionError("Reload the scenario and deliberately rebase answers.")
        return revision

"""Application-level generation and validation use case for analysis runs."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from adr_forge.decisions.parsing import ParseResult, parse_adr_output
from adr_forge.scenarios.models import ScenarioRevision
from adr_forge.strategies.base import GenerationResult, StructuredOutputStrategy
from adr_forge.system.progress import CancellationToken


@dataclass(frozen=True, slots=True)
class GeneratedDecision:
    generation: GenerationResult
    parsed: ParseResult


class DecisionService:
    """Generate once, retain raw output, then validate the strict ADR contract."""

    async def execute(
        self,
        strategy: StructuredOutputStrategy,
        scenario: ScenarioRevision,
        run_id: UUID,
        cancellation: CancellationToken,
    ) -> GeneratedDecision:
        generation = await strategy.generate(scenario, cancellation=cancellation)
        cancellation.raise_if_cancelled()
        return GeneratedDecision(
            generation=generation,
            parsed=self.parse(generation, run_id, scenario),
        )

    @staticmethod
    def parse(
        generation: GenerationResult, run_id: UUID, scenario: ScenarioRevision
    ) -> ParseResult:
        """Validate an already captured generation without modifying its raw response."""
        return parse_adr_output(
            generation.raw_output,
            run_id,
            answered_questions=[answer.question for answer in scenario.clarification_answers],
        )

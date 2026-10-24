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
            parsed=parse_adr_output(generation.raw_output, run_id),
        )

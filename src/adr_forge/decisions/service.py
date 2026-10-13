"""Application-level generation and validation use case for analysis runs."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from adr_forge.decisions.parsing import ParsedOutputs, parse_with_one_repair
from adr_forge.scenarios.models import ScenarioRevision
from adr_forge.strategies.base import GenerationResult, StructuredOutputStrategy
from adr_forge.system.progress import CancellationToken


@dataclass(frozen=True, slots=True)
class GeneratedDecision:
    generation: GenerationResult
    parsed: ParsedOutputs


class DecisionService:
    """Generate once, retain raw output, then validate without silently repairing it."""

    async def execute(
        self,
        strategy: StructuredOutputStrategy,
        scenario: ScenarioRevision,
        run_id: UUID,
        cancellation: CancellationToken,
        repair: Callable[[str], str] | None = None,
    ) -> GeneratedDecision:
        generation = await strategy.generate(scenario, cancellation=cancellation)
        cancellation.raise_if_cancelled()
        return GeneratedDecision(
            generation=generation,
            parsed=parse_with_one_repair(generation.raw_output, run_id, repair),
        )

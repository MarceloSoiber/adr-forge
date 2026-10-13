"""Shared contracts and prompt construction for analysis strategies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from adr_forge.scenarios.models import ScenarioRevision
from adr_forge.system.progress import CancellationToken


@dataclass(frozen=True, slots=True)
class GenerationTelemetry:
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: int | None = None
    peak_vram_mb: int | None = None


@dataclass(frozen=True, slots=True)
class GenerationResult:
    raw_output: str
    telemetry: GenerationTelemetry = GenerationTelemetry()


class StructuredOutputStrategy(Protocol):
    async def generate(
        self, scenario: ScenarioRevision, *, cancellation: CancellationToken
    ) -> GenerationResult: ...


def build_adr_prompt(scenario: ScenarioRevision) -> str:
    """Build the same unprivileged structured-output prompt for every baseline."""
    return (
        "Gere somente JSON para um ADR em português. Não invente fatos. "
        f"Problema: {scenario.problem}\n"
        f"Fatos: {scenario.facts}\nRestrições: {scenario.constraints}\n"
        f"Alternativas candidatas: {scenario.candidate_alternatives}"
    )

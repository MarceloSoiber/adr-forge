"""Shared contracts and prompt construction for analysis strategies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from adr_forge.scenarios.models import ScenarioRevision
from adr_forge.shared.adr_prompt import build_adr_prompt as _build_adr_prompt
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


@dataclass(frozen=True, slots=True)
class StrategyInput:
    scenario_revision_id: UUID
    scenario_content_hash: str
    scenario: ScenarioRevision
    snapshot: Any | None
    retrieval_snapshot_id: UUID | None
    prompt_version: str
    generation_config_hash: str


class StructuredOutputStrategy(Protocol):
    async def generate(
        self, scenario: ScenarioRevision, *, cancellation: CancellationToken
    ) -> GenerationResult: ...

    async def repair(
        self,
        scenario: ScenarioRevision,
        raw_output: str,
        findings: list[dict[str, Any]],
        *,
        cancellation: CancellationToken,
    ) -> GenerationResult: ...


def build_adr_prompt(scenario: ScenarioRevision) -> str:
    """Build the same unprivileged structured-output prompt for every baseline."""
    return _build_adr_prompt(
        scenario.problem,
        scenario.facts,
        scenario.constraints,
        scenario.candidate_alternatives,
        [
            "Pergunta: "
            f"{answer.question}\nImpacto: {answer.impact}\nResposta: {answer.answer}"
            for answer in scenario.clarification_answers
        ],
    )

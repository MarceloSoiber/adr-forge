"""Freeze comparable strategy inputs before execution."""

from __future__ import annotations

from typing import Any

from adr_forge.retrieval.models import RetrievalSnapshot
from adr_forge.scenarios.models import ScenarioRevision
from adr_forge.shared.hashing import canonical_sha256
from adr_forge.strategies.base import GenerationResult, StrategyInput


class StrategyExecutionService:
    def __init__(self, runtimes: dict[str, Any]) -> None:
        self._runtimes = runtimes

    async def execute(self, strategy: str, *, scenario: ScenarioRevision, snapshot: RetrievalSnapshot | None, generation_configuration: dict[str, Any], prompt_version: str = "adr-v1") -> GenerationResult:
        requires_snapshot = strategy in {"rag", "fine_tuned_rag"}
        if requires_snapshot != (snapshot is not None):
            raise ValueError("strategy snapshot requirement was not met")
        runtime = self._runtimes[strategy]
        value = StrategyInput(scenario.id, scenario.content_hash, scenario, snapshot, snapshot.id if snapshot else None, prompt_version, canonical_sha256(generation_configuration))
        return await runtime.generate(value)

    async def execute_comparison(self, *, scenario: ScenarioRevision, snapshot: RetrievalSnapshot, generation_configuration: dict[str, Any], strategies: list[tuple[str, str]]) -> list[GenerationResult]:
        return [await self.execute(strategy, scenario=scenario, snapshot=snapshot if strategy in {"rag", "fine_tuned_rag"} else None, generation_configuration=generation_configuration, prompt_version=prompt_version) for strategy, prompt_version in strategies]

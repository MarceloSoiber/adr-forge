"""In-memory strategy registry for the local single-process application."""

from __future__ import annotations

from adr_forge.shared.hashing import canonical_sha256
from adr_forge.strategies.models import (
    AnalysisStrategy,
    RuntimeKind,
    StrategyAvailability,
    StrategyKind,
)
from adr_forge.strategies.qwen_runtime import QWEN_MODEL_ID


class StrategyRegistry:
    def __init__(self, strategies: list[AnalysisStrategy] | None = None) -> None:
        self._strategies: dict[tuple[str, str], AnalysisStrategy] = {}
        for strategy in strategies or []:
            self.register(strategy)

    def register(self, strategy: AnalysisStrategy) -> None:
        key = (strategy.id, strategy.version)
        if key in self._strategies:
            raise ValueError(f"strategy already registered: {strategy.id}@{strategy.version}")
        self._strategies[key] = strategy

    def get(self, strategy_id: str, version: str) -> AnalysisStrategy | None:
        return self._strategies.get((strategy_id, version))

    def list(self) -> list[AnalysisStrategy]:
        return sorted(
            self._strategies.values(), key=lambda strategy: (strategy.id, strategy.version)
        )


def default_registry(model_revision: str = "main") -> StrategyRegistry:
    """Return the CPU-safe fake and pinned Qwen baseline configurations."""
    generation_config_hash = canonical_sha256({"max_new_tokens": 1024, "temperature": 0})
    return StrategyRegistry(
        [
            AnalysisStrategy(
                id="fake-baseline",
                version="1",
                kind=StrategyKind.BASE,
                model_id="adr-forge/fake",
                model_revision="1",
                prompt_version="adr-v1",
                generation_config_hash=generation_config_hash,
                runtime_kind=RuntimeKind.FAKE,
                availability=StrategyAvailability(available=True),
            ),
            AnalysisStrategy(
                id="qwen3-4b-baseline",
                version="1",
                kind=StrategyKind.BASE,
                model_id=QWEN_MODEL_ID,
                model_revision=model_revision,
                prompt_version="adr-v1",
                generation_config_hash=generation_config_hash,
                runtime_kind=RuntimeKind.TRANSFORMERS,
                availability=StrategyAvailability(
                    available=False,
                    unavailable_reason="Requires optional ml dependencies and local GPU preflight.",
                ),
            ),
        ]
    )

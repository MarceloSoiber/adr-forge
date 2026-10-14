"""Comparable strategy inputs are frozen before any runtime generates an ADR."""

from __future__ import annotations

from uuid import uuid4

import pytest

from adr_forge.retrieval.models import RetrievalChunk, RetrievalFilters, RetrievalSnapshot
from adr_forge.scenarios.models import DecisionCategory, ScenarioRevision
from adr_forge.strategies.base import GenerationResult, StrategyInput
from adr_forge.strategies.service import StrategyExecutionService


class _RecordingRuntime:
    def __init__(self) -> None:
        self.inputs: list[StrategyInput] = []

    async def generate(self, strategy_input: StrategyInput) -> GenerationResult:
        self.inputs.append(strategy_input)
        return GenerationResult(raw_output="{}")


def _scenario() -> ScenarioRevision:
    return ScenarioRevision(
        scenario_id=uuid4(),
        revision_number=1,
        problem="Precisamos escolher um modo de processamento que permaneça operável e auditável.",
        facts=["Há picos previsíveis no período noturno."],
        constraints=["A implantação deve manter recursos locais."],
        candidate_alternatives=["síncrono", "assíncrono"],
        categories=[DecisionCategory.SYNC_VS_ASYNC],
    )


def _snapshot() -> RetrievalSnapshot:
    return RetrievalSnapshot(
        provider="fixture",
        provider_version="fixture-v1",
        query="processamento assíncrono",
        filters=RetrievalFilters(limit=8),
        embedding_model="embedder",
        embedding_version="revision-1",
        chunks=[
            RetrievalChunk(
                source_id="source-a",
                chunk_id="a",
                title="A",
                uri="local://a",
                location={"chunk_index": 1},
                content="Primeira evidência.",
                score=0.9,
                match_reasons=["vector"],
                rank=1,
            ),
            RetrievalChunk(
                source_id="source-b",
                chunk_id="b",
                title="B",
                uri="local://b",
                location={"chunk_index": 2},
                content="Segunda evidência.",
                score=0.8,
                match_reasons=["text"],
                rank=2,
            ),
        ],
    )


@pytest.mark.asyncio
async def test_comparable_rag_strategies_observe_the_same_frozen_strategy_input() -> None:
    prompted, rag = _RecordingRuntime(), _RecordingRuntime()
    service = StrategyExecutionService(runtimes={"prompted": prompted, "rag": rag})
    scenario, snapshot = _scenario(), _snapshot()

    await service.execute_comparison(
        scenario=scenario,
        snapshot=snapshot,
        generation_configuration={"temperature": 0, "max_new_tokens": 512},
        strategies=[("prompted", "prompt-v2"), ("rag", "prompt-v2")],
    )

    prompted_input, rag_input = prompted.inputs[0], rag.inputs[0]
    assert prompted_input.scenario_revision_id == rag_input.scenario_revision_id == scenario.id
    assert (
        prompted_input.scenario_content_hash
        == rag_input.scenario_content_hash
        == scenario.content_hash
    )
    assert rag_input.retrieval_snapshot_id == snapshot.id
    assert [chunk.content for chunk in rag_input.snapshot.chunks] == [
        "Primeira evidência.",
        "Segunda evidência.",
    ]
    assert prompted_input.prompt_version == rag_input.prompt_version == "prompt-v2"
    assert prompted_input.generation_config_hash == rag_input.generation_config_hash


@pytest.mark.asyncio
async def test_rag_requires_frozen_snapshot_and_non_rag_rejects_one() -> None:
    service = StrategyExecutionService(
        runtimes={"prompted": _RecordingRuntime(), "rag": _RecordingRuntime()}
    )
    with pytest.raises(ValueError, match="snapshot"):
        await service.execute(
            "rag", scenario=_scenario(), snapshot=None, generation_configuration={}
        )
    with pytest.raises(ValueError, match="snapshot"):
        await service.execute(
            "prompted", scenario=_scenario(), snapshot=_snapshot(), generation_configuration={}
        )

"""Serialized execution, durable progress ordering, and recovery coverage."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from adr_forge.experiments.run_models import AnalysisRun, RunStatus
from adr_forge.scenarios.models import DecisionCategory, DecisionScenario, ScenarioRevision
from adr_forge.strategies.executor import AnalysisExecutor
from adr_forge.system.progress import ProgressPublisher


@pytest.mark.asyncio
async def test_executor_serializes_jobs_and_persists_before_publishing() -> None:
    order: list[str] = []
    active = 0
    max_active = 0

    async def persist(run_id: str, status: str, stage: str, percent: int | None) -> bool:
        order.append(f"persist:{run_id}:{stage}")
        return True

    progress = ProgressPublisher()
    progress.subscribe("one", lambda snapshot: order.append(f"publish:one:{snapshot.stage}"))

    async def job(_: object) -> None:
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0)
        active -= 1

    executor = AnalysisExecutor(progress, persist_snapshot=persist)
    await executor.enqueue("one", job)
    await executor.enqueue("two", job)
    await executor._queue.join()
    await executor.stop()

    assert max_active == 1
    assert order.index("persist:one:waiting_resources") < order.index(
        "publish:one:waiting_resources"
    )
    assert progress.current("two").stage == "completed"  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_executor_cooperatively_cancels_queued_job() -> None:
    executed = False

    async def job(_: object) -> None:
        nonlocal executed
        executed = True

    executor = AnalysisExecutor()
    await executor.enqueue("run", job)
    assert executor.cancel("run") is True
    await executor._queue.join()
    await executor.stop()

    assert executed is False
    assert executor.progress.current("run").stage == "cancelled"  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_async_subscription_keeps_current_snapshot_during_reconnect() -> None:
    publisher = ProgressPublisher()
    publisher.publish("run", "waiting_resources", 0)
    stream = publisher.subscribe_async("run")
    first = await anext(stream)
    await stream.aclose()

    assert first.stage == "waiting_resources"


class _RecoveryRepository:
    def __init__(self, run: AnalysisRun) -> None:
        self.run = run
        self.transitions: list[dict[str, Any]] = []

    async def list_non_terminal(self) -> list[dict[str, Any]]:
        return [{**self.run.model_dump(mode="python"), "validation_attempts": []}]

    async def transition(self, payload: dict[str, Any], expected_sequence: int) -> bool:
        self.transitions.append(payload)
        return expected_sequence == self.run.progress_sequence


@pytest.mark.asyncio
async def test_startup_recovery_persists_interruption_before_publication() -> None:
    scenario = DecisionScenario(title="Decisão de recuperação")
    revision = ScenarioRevision(
        scenario_id=scenario.id,
        revision_number=1,
        problem="Precisamos recuperar uma execução interrompida com segurança suficiente.",
        categories=[DecisionCategory.SQL_VS_NOSQL],
    )
    pending = AnalysisRun(
        scenario_revision_id=revision.id,
        strategy_id="fake",
        strategy_version="1",
        scenario_content_hash="a" * 64,
        strategy_configuration_hash="b" * 64,
        generation_config_hash="c" * 64,
    )
    repository = _RecoveryRepository(pending)
    executor = AnalysisExecutor()

    assert await executor.recover_abandoned_runs(repository) == 1  # type: ignore[arg-type]
    persisted = repository.transitions[0]
    assert persisted["status"] == RunStatus.INTERRUPTED
    assert executor.progress.current(str(pending.id)).stage == "startup_recovery"  # type: ignore[union-attr]

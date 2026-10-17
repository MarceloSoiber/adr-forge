"""Durable state and optimistic-concurrency coverage for analysis runs."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config

from adr_forge.experiments.run_models import AnalysisRun, RunStatus
from adr_forge.experiments.run_repository import RunRepository
from adr_forge.persistence.database import create_database_engine, create_session_factory
from adr_forge.scenarios.models import DecisionCategory, DecisionScenario, ScenarioRevision
from adr_forge.scenarios.repository import ScenarioRepository


@pytest.fixture
def migrated_run_database(tmp_path: Path) -> Path:
    """Provide a database at the final Phase 3 schema revision."""
    database_path = tmp_path / "analysis-runs.sqlite3"
    repository_root = Path(__file__).parents[3]
    config = Config()
    config.set_main_option("script_location", str(repository_root / "alembic"))
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{database_path}")
    command.upgrade(config, "0011_run_provenance")
    return database_path


async def _create_revision(session_factory: object) -> ScenarioRevision:
    scenario = DecisionScenario(title="Decisão de persistência")
    revision = ScenarioRevision(
        scenario_id=scenario.id,
        revision_number=1,
        problem="Precisamos escolher uma forma confiável de persistir os dados do produto.",
        categories=[DecisionCategory.SQL_VS_NOSQL],
    )
    await ScenarioRepository(session_factory).create_first(scenario, revision)  # type: ignore[arg-type]
    return revision


def _payload(run: AnalysisRun) -> dict[str, object]:
    payload = run.model_dump(mode="python")
    payload["validation_attempts"] = []
    return payload


def _run(
    *,
    scenario_revision_id: object,
    strategy_version: str = "1.0.0",
    experiment_id: UUID | None = None,
) -> AnalysisRun:
    return AnalysisRun(
        scenario_revision_id=scenario_revision_id,  # type: ignore[arg-type]
        strategy_id="fake",
        strategy_version=strategy_version,
        experiment_id=experiment_id,
        scenario_content_hash="a" * 64,
        strategy_configuration_hash="b" * 64,
        generation_config_hash="c" * 64,
    )


@pytest.mark.asyncio
async def test_add_persists_snapshot_initial_event_and_validation_attempt(
    migrated_run_database: Path,
) -> None:
    engine = create_database_engine(f"sqlite+aiosqlite:///{migrated_run_database}")
    session_factory = create_session_factory(engine)
    repository = RunRepository(session_factory)
    try:
        revision = await _create_revision(session_factory)
        run = _run(scenario_revision_id=revision.id)

        await repository.add(_payload(run))
        await repository.add_validation_attempt(
            str(run.id),
            {
                "attempt": "original",
                "artifact_id": "f" * 36,
                "parse_succeeded": False,
                "findings": [{"code": "missing_context"}],
                "created_at": datetime.now(UTC),
            },
        )

        stored = await repository.get(str(run.id))
        events = await repository.list_events(str(run.id))

        assert stored is not None
        assert stored["status"] == RunStatus.PENDING
        assert stored["validation_attempts"] == []
        assert [(event["progress_sequence"], event["status"]) for event in events] == [
            (0, RunStatus.PENDING)
        ]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_list_by_experiment_returns_only_matching_runs_in_creation_order(
    migrated_run_database: Path,
) -> None:
    engine = create_database_engine(f"sqlite+aiosqlite:///{migrated_run_database}")
    session_factory = create_session_factory(engine)
    repository = RunRepository(session_factory)
    try:
        revision = await _create_revision(session_factory)
        experiment_id = uuid4()
        first = _run(scenario_revision_id=revision.id, experiment_id=experiment_id)
        other = _run(scenario_revision_id=revision.id, experiment_id=uuid4())
        second = _run(scenario_revision_id=revision.id, experiment_id=experiment_id)
        for run in (first, other, second):
            await repository.add(_payload(run))

        stored = await repository.list_by_experiment(str(experiment_id))

        assert [entry["id"] for entry in stored] == [str(first.id), str(second.id)]
        assert all(entry["experiment_id"] == str(experiment_id) for entry in stored)
        assert all(entry["validation_attempts"] == [] for entry in stored)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_transition_uses_sequence_compare_and_swap_and_records_event(
    migrated_run_database: Path,
) -> None:
    engine = create_database_engine(f"sqlite+aiosqlite:///{migrated_run_database}")
    session_factory = create_session_factory(engine)
    repository = RunRepository(session_factory)
    try:
        revision = await _create_revision(session_factory)
        initial = _run(scenario_revision_id=revision.id)
        await repository.add(_payload(initial))

        waiting = initial.transition(
            RunStatus.WAITING_RESOURCES, stage="waiting_gpu", progress_percent=5
        )
        assert await repository.transition(_payload(waiting), expected_sequence=0)
        assert not await repository.transition(_payload(waiting), expected_sequence=0)

        stored = await repository.get(str(initial.id))
        events = await repository.list_events(str(initial.id))
        assert stored is not None
        assert stored["progress_sequence"] == 1
        assert stored["status"] == RunStatus.WAITING_RESOURCES
        assert [event["progress_sequence"] for event in events] == [0, 1]
    finally:
        await engine.dispose()


def test_state_machine_allows_cancel_and_interruption_from_active_states() -> None:
    initial = _run(
        scenario_revision_id=ScenarioRevision(
            scenario_id=DecisionScenario(title="Decisão teste").id,
            revision_number=1,
            problem="Precisamos tomar uma decisão arquitetural com evidências suficientes.",
            categories=[DecisionCategory.SQL_VS_NOSQL],
        ).id,
    )

    cancelled = initial.transition(RunStatus.CANCELLED, stage="cancelled")
    waiting = initial.transition(RunStatus.WAITING_RESOURCES, stage="waiting_gpu")
    running = waiting.transition(RunStatus.RUNNING, stage="generating")
    interrupted = running.transition(RunStatus.INTERRUPTED, stage="startup_recovery")

    assert cancelled.finished_at is not None
    assert interrupted.finished_at is not None
    assert interrupted.progress_sequence == 3

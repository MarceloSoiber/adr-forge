"""Recovery behaviour exercised against disposable database and artifact roots."""

from __future__ import annotations

import asyncio
import json
import sqlite3
from collections.abc import AsyncIterator
from datetime import timedelta
from hashlib import sha256
from pathlib import Path

import httpx
import pytest
from alembic import command
from alembic.config import Config
from apps.api.main import create_app

from adr_forge.artifacts.repository import ArtifactRepository
from adr_forge.artifacts.service import ArtifactMaintenance
from adr_forge.artifacts.store import ArtifactStore, ArtifactStoreError
from adr_forge.experiments.run_models import AnalysisRun, RunStatus
from adr_forge.experiments.run_repository import RunRepository
from adr_forge.persistence.backup import create_sqlite_backup
from adr_forge.persistence.database import create_database_engine, create_session_factory
from adr_forge.scenarios.models import DecisionCategory, DecisionScenario, ScenarioRevision
from adr_forge.scenarios.repository import ScenarioRepository
from adr_forge.shared.config import Settings
from adr_forge.shared.time import utc_now


@pytest.fixture
async def isolated_root(tmp_path: Path) -> AsyncIterator[tuple[Path, Path]]:
    """Provide a migrated database and artifact root with no developer-state dependency."""
    database_path = tmp_path / "adr-forge.sqlite3"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{database_path}")
    await asyncio.to_thread(command.upgrade, config, "head")
    yield database_path, tmp_path / "artifacts"


def test_backup_restore_isolated_root_is_manifest_verified(
    tmp_path: Path,
) -> None:
    """A published backup and its canonical manifest are enough to restore the snapshot."""
    source = tmp_path / "live.sqlite3"
    backup_path = tmp_path / "published" / "adr-forge.sqlite3"
    with sqlite3.connect(source) as connection:
        connection.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
        connection.execute("INSERT INTO alembic_version VALUES ('recovery_test')")
        connection.execute("CREATE TABLE durable_value (value TEXT NOT NULL)")
        connection.execute("INSERT INTO durable_value VALUES ('survives restore')")
        connection.commit()

    result = create_sqlite_backup(source, backup_path, application_version="test")
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))

    assert manifest["database_sha256"] == sha256(backup_path.read_bytes()).hexdigest()
    assert manifest["database_size_bytes"] == backup_path.stat().st_size
    assert manifest["schema_revision"] == "recovery_test"
    with sqlite3.connect(backup_path) as restored:
        assert restored.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert restored.execute("SELECT value FROM durable_value").fetchone() == (
            "survives restore",
        )


@pytest.mark.asyncio
async def test_api_startup_marks_pending_run_interrupted(
    isolated_root: tuple[Path, Path],
) -> None:
    """A process restart durably closes pending work before accepting new work."""
    database_path, artifact_root = isolated_root
    engine = create_database_engine(f"sqlite+aiosqlite:///{database_path}")
    sessions = create_session_factory(engine)
    try:
        scenario = DecisionScenario(title="Recuperação após reinício")
        revision = ScenarioRevision(
            scenario_id=scenario.id,
            revision_number=1,
            problem="Precisamos registrar com segurança uma execução interrompida pelo reinício.",
            categories=[DecisionCategory.SQL_VS_NOSQL],
        )
        await ScenarioRepository(sessions).create_first(scenario, revision)
        pending = AnalysisRun(
            scenario_revision_id=revision.id,
            strategy_id="fake-baseline",
            strategy_version="1",
        )
        payload = pending.model_dump(mode="python")
        payload["validation_attempts"] = []
        await RunRepository(sessions).add(payload)
    finally:
        await engine.dispose()

    application = create_app(
        Settings(
            database_url=f"sqlite+aiosqlite:///{database_path}",
            artifact_root=artifact_root,
        )
    )
    async with application.router.lifespan_context(application):
        repository = RunRepository(application.state.session_factory)
        recovered = await repository.get(str(pending.id))
        assert recovered is not None
        assert recovered["status"] == "interrupted"
        assert recovered["stage"] == "startup_recovery"
        assert recovered["progress_percent"] == 100
        assert recovered["failure_code"] == "interrupted_restart"
        events = await repository.list_events(str(pending.id))
        assert [(event["progress_sequence"], event["status"]) for event in events] == [
            (0, "pending"),
            (1, "interrupted"),
        ]


@pytest.mark.asyncio
async def test_sse_emits_persisted_snapshot_before_live_progress_on_reconnect(
    isolated_root: tuple[Path, Path],
) -> None:
    """A reconnect sees durable state first, then only newer publisher notifications."""
    database_path, artifact_root = isolated_root
    application = create_app(
        Settings(
            database_url=f"sqlite+aiosqlite:///{database_path}",
            artifact_root=artifact_root,
        )
    )
    async with application.router.lifespan_context(application):
        sessions = application.state.session_factory
        scenario = DecisionScenario(title="Reconexão de eventos")
        revision = ScenarioRevision(
            scenario_id=scenario.id,
            revision_number=1,
            problem="Precisamos provar que a reconexão começa pelo estado persistido da execução.",
            categories=[DecisionCategory.SQL_VS_NOSQL],
        )
        await ScenarioRepository(sessions).create_first(scenario, revision)
        pending = AnalysisRun(
            scenario_revision_id=revision.id,
            strategy_id="fake-baseline",
            strategy_version="1",
        )
        repository = RunRepository(sessions)
        await repository.add({**pending.model_dump(mode="python"), "validation_attempts": []})

        async def publish_new_progress() -> None:
            await asyncio.sleep(0.01)
            waiting = pending.transition(
                RunStatus.WAITING_RESOURCES, stage="waiting_resources", progress_percent=0
            )
            assert await repository.transition(
                {**waiting.model_dump(mode="python"), "validation_attempts": []},
                pending.progress_sequence,
            )
            application.state.analysis_executor.progress.publish(
                str(pending.id), "waiting_resources", 0
            )
            running = waiting.transition(RunStatus.RUNNING, stage="running", progress_percent=50)
            assert await repository.transition(
                {**running.model_dump(mode="python"), "validation_attempts": []},
                waiting.progress_sequence,
            )
            application.state.analysis_executor.progress.publish(str(pending.id), "running", 50)
            completed = running.transition(
                RunStatus.COMPLETED, stage="completed", progress_percent=100
            )
            assert await repository.transition(
                {**completed.model_dump(mode="python"), "validation_attempts": []},
                running.progress_sequence,
            )
            application.state.analysis_executor.progress.publish(str(pending.id), "completed", 100)

        publisher = asyncio.create_task(publish_new_progress())
        transport = httpx.ASGITransport(app=application)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get(f"/api/v1/analysis-runs/{pending.id}/events")
        await publisher

    assert response.status_code == 200
    events = [
        json.loads(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    assert [(event["progress_sequence"], event["status"]) for event in events] == [
        (0, "pending"),
        (1, "waiting_resources"),
        (2, "running"),
        (3, "completed"),
    ]


class _FailOnceRemoveStore(ArtifactStore):
    """A local fault injector proving prune can be retried without metadata loss."""

    def __init__(self, root: Path) -> None:
        super().__init__(root)
        self._fail_next_remove = True

    async def remove(self, relative_path: str) -> bool:
        if self._fail_next_remove:
            self._fail_next_remove = False
            raise ArtifactStoreError("injected transient cleanup failure")
        return await super().remove(relative_path)


@pytest.mark.asyncio
async def test_prune_fault_is_safe_and_a_retry_reclaims_only_eligible_artifact(
    isolated_root: tuple[Path, Path],
) -> None:
    """A failed cleanup leaves both bytes and metadata for an explicit safe retry."""
    database_path, artifact_root = isolated_root
    engine = create_database_engine(f"sqlite+aiosqlite:///{database_path}")
    sessions = create_session_factory(engine)
    repository = ArtifactRepository(sessions)
    store = _FailOnceRemoveStore(artifact_root)
    try:
        digest, size, relative_path = await store.put_bytes(b"retryable artifact")
        artifact_id = await repository.create(
            kind="report",
            sha256=digest,
            relative_path=relative_path,
            size_bytes=size,
            media_type="text/plain",
            created_at=utc_now() - timedelta(days=2),
            retention="temporary",
        )
        service = ArtifactMaintenance(repository, store)

        failed = await service.prune(confirmed=True)
        assert failed.reclaimed_bytes == 0
        assert failed.results[0].status == "failed"
        assert await store.read_bytes(relative_path) == b"retryable artifact"
        assert [item.id for item in await repository.list_catalog()] == [artifact_id]

        retried = await service.prune(confirmed=True)
        assert [
            (item.artifact_id, item.status, item.reclaimed_bytes) for item in retried.results
        ] == [(artifact_id, "deleted", size)]
        assert not (artifact_root / relative_path).exists()
        assert await repository.list_catalog() == []
    finally:
        await engine.dispose()

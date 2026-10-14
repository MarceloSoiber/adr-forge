"""Blind-comparison HTTP flow persists state and keeps identities reveal-gated."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from alembic import command
from alembic.config import Config

from apps.api.main import create_app
from adr_forge.api.routes import comparisons
from adr_forge.shared.config import Settings


class _CompletedRuns:
    def __init__(self, revision_id: str) -> None:
        self.revision_id = revision_id

    async def get(self, run_id: str):
        return {
            "id": run_id,
            "scenario_revision_id": self.revision_id,
            "status": "completed",
            "strategy_id": "hidden-strategy",
            "strategy_version": "1",
        }

    async def get_adr(self, run_id: str):
        return {"id": str(uuid4()), "analysis_run_id": run_id, "created_at": "now", "title": "ADR"}


@pytest.fixture
async def client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[httpx.AsyncClient]:
    database_path = tmp_path / "comparisons.sqlite3"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{database_path}")
    await asyncio.to_thread(command.upgrade, config, "head")
    revision_id = str(uuid4())

    async def runs(_request):
        return _CompletedRuns(revision_id)

    monkeypatch.setattr(comparisons, "_run_repository", runs)
    application = create_app(
        Settings(
            database_url=f"sqlite+aiosqlite:///{database_path}",
            artifact_root=tmp_path / "artifacts",
        )
    )
    transport = httpx.ASGITransport(app=application)
    async with application.router.lifespan_context(application):
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as session:
            yield session


@pytest.mark.asyncio
async def test_comparison_api_persists_submission_and_reveals_only_after_evaluation(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post(
        "/api/v1/comparisons",
        json={
            "run_ids": [str(uuid4()), str(uuid4())],
            "rubric_version_id": str(uuid4()),
        },
    )
    assert response.status_code == 201, response.text
    comparison = response.json()
    assert "strategy_id" not in response.text
    comparison_id = comparison["id"]

    assert (await client.get(f"/api/v1/comparisons/{comparison_id}/reveal")).status_code == 409
    labels = [candidate["label"] for candidate in comparison["candidates"]]
    scores = {label: {"quality": 4} for label in labels}
    submitted = await client.post(
        f"/api/v1/comparisons/{comparison_id}/evaluation",
        json={
            "evaluator_id": "reviewer",
            "evaluator_type": "human",
            "scores": scores,
            "preference": labels[0],
            "notes": "checked",
        },
    )
    assert submitted.status_code == 201, submitted.text
    assert (await client.get(f"/api/v1/comparisons/{comparison_id}")).json()["evaluated"] is True
    revealed = await client.get(f"/api/v1/comparisons/{comparison_id}/reveal")
    assert revealed.status_code == 200, revealed.text
    assert {candidate["run_id"] for candidate in revealed.json()["candidates"]}

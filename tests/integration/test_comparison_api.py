"""Blind-comparison HTTP flow persists state and keeps identities reveal-gated."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
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
        return {
            "id": str(uuid4()),
            "analysis_run_id": run_id,
            "schema_version": "adr-v1",
            "title": "Persistência do catálogo",
            "status": "proposed",
            "context": ["O catálogo exige consistência."],
            "facts": ["Há relações entre produtos e estoque."],
            "assumptions": [],
            "unresolved_questions": [],
            "constraints": ["A solução deve permanecer local."],
            "alternatives": [
                {
                    "id": "postgresql",
                    "name": "PostgreSQL",
                    "summary": "Banco relacional.",
                    "viable": True,
                    "benefits": ["Consistência."],
                    "drawbacks": ["Operação."],
                    "constraint_ids": ["constraint:0"],
                },
                {
                    "id": "sqlite",
                    "name": "SQLite",
                    "summary": "Banco embarcado.",
                    "viable": True,
                    "benefits": ["Simplicidade."],
                    "drawbacks": ["Concorrência limitada."],
                    "constraint_ids": ["constraint:0"],
                },
            ],
            "decision": "PostgreSQL",
            "rationale": [
                {
                    "claim": "A decisão usa o fato disponível.",
                    "evidence_kind": "fact",
                    "evidence_id": "fact:0",
                }
            ],
            "positive_consequences": ["Consistência explícita."],
            "negative_consequences": ["Exige operação."],
            "risks": [],
            "review_triggers": [
                {"metric": "latencia", "operator": "gt", "threshold": 500, "unit": "ms"}
            ],
            "confidence": 0.8,
            "reference_ids": [],
            "created_at": datetime.now(UTC),
        }


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
            model_revision="cdbee75f17c01a7cc42f958dc650907174af0554",
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

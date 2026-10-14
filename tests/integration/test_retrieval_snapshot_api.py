"""The snapshot endpoint freezes a configured fixture and reuses its identity."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from alembic import command
from alembic.config import Config
from apps.api.main import create_app

from adr_forge.retrieval.models import RetrievalChunk, RetrievalFilters, RetrievalSnapshot
from adr_forge.shared.config import Settings


@pytest.fixture
async def retrieval_client(tmp_path: Path) -> AsyncIterator[httpx.AsyncClient]:
    database_path = tmp_path / "adr-forge.sqlite3"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{database_path}")
    await asyncio.to_thread(command.upgrade, config, "head")
    application = create_app(
        Settings(
            database_url=f"sqlite+aiosqlite:///{database_path}",
            artifact_root=tmp_path / "artifacts",
        )
    )
    application.state.retrieval_fixture_providers = {
        "async-reference": RetrievalSnapshot(
            provider="fixture",
            provider_version="fixture-v1",
            query="Quando usar processamento assíncrono?",
            filters=RetrievalFilters(limit=2),
            embedding_model="fixture-embedder",
            embedding_version="fixture-1",
            chunks=[
                RetrievalChunk(
                    id="chunk-1",
                    source_id="reference-1",
                    source_title="Referência",
                    uri="fixture://reference-1",
                    location={"page": 1},
                    content="Evidência imutável.",
                    score=0.9,
                    rank=1,
                )
            ],
        )
    }
    transport = httpx.ASGITransport(app=application)
    async with application.router.lifespan_context(application):
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            yield client


@pytest.mark.asyncio
async def test_fixture_snapshot_is_persisted_once_and_reused(
    retrieval_client: httpx.AsyncClient,
) -> None:
    request = {
        "provider": "fixture",
        "fixture_id": "async-reference",
        "query": "Quando usar processamento assíncrono?",
        "filters": {"limit": 2},
    }

    created = await retrieval_client.post("/api/v1/retrieval-snapshots", json=request)
    reused = await retrieval_client.post("/api/v1/retrieval-snapshots", json=request)

    assert created.status_code == 201, created.text
    assert reused.status_code == 201, reused.text
    assert created.json()["id"] == reused.json()["id"]
    assert created.json()["content_hash"] == reused.json()["content_hash"]
    assert "chunks" not in created.json()


@pytest.mark.asyncio
async def test_fixture_id_is_required_and_unknown_fixture_is_unavailable(
    retrieval_client: httpx.AsyncClient,
) -> None:
    missing = await retrieval_client.post(
        "/api/v1/retrieval-snapshots",
        json={"provider": "fixture", "query": "consulta", "filters": {}},
    )
    unknown = await retrieval_client.post(
        "/api/v1/retrieval-snapshots",
        json={
            "provider": "fixture",
            "fixture_id": "not-configured",
            "query": "consulta",
            "filters": {},
        },
    )

    assert missing.status_code == 422
    assert unknown.status_code == 503

"""CPU-only vertical slice for the deterministic fake analysis strategy."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from apps.api.main import create_app

from adr_forge.shared.config import Settings

TERMINAL_STATUSES = {
    "completed",
    "needs_clarification",
    "invalid_output",
    "failed",
    "cancelled",
    "interrupted",
}


@pytest.fixture
async def client(tmp_path: Path) -> AsyncIterator[httpx.AsyncClient]:
    """Run the API against storage isolated from developer state."""
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'adr-forge.sqlite3'}",
        artifact_root=tmp_path / "artifacts",
    )
    application = create_app(settings)
    transport = httpx.ASGITransport(app=application)
    async with application.router.lifespan_context(application):
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as session:
            yield session


async def _wait_for_terminal_run(client: httpx.AsyncClient, run_id: str) -> dict[str, Any]:
    """Poll persisted state instead of depending on timing of the fake worker."""
    for _ in range(100):
        response = await client.get(f"/api/v1/analysis-runs/{run_id}")
        assert response.status_code == 200, response.text
        run = response.json()
        if run["status"] in TERMINAL_STATUSES:
            return run
        await asyncio.sleep(0.01)
    pytest.fail("fake analysis run did not reach a terminal status")


@pytest.mark.asyncio
async def test_fake_analysis_api_flow_creates_adr_and_exports_markdown(
    client: httpx.AsyncClient,
) -> None:
    """Create a scenario, run the CPU fake, observe SSE, then retrieve its ADR."""
    scenario_response = await client.post(
        "/api/v1/scenarios",
        json={
            "title": "Persistência transacional do catálogo",
            "language": "pt-BR",
            "problem": (
                "Precisamos escolher a persistência para o catálogo transacional, "
                "mantendo consistência e consultas relacionais previsíveis."
            ),
            "facts": ["O catálogo possui relações entre produtos, preços e estoque."],
            "constraints": ["A operação deve permanecer local durante a avaliação."],
            "desired_qualities": ["consistência", "auditabilidade"],
            "candidate_alternatives": ["PostgreSQL", "MongoDB"],
        },
    )

    assert scenario_response.status_code == 201, scenario_response.text
    scenario = scenario_response.json()
    revision = scenario["current_revision"]
    assert scenario["language"] == "pt-BR"
    assert revision["categories"] == ["sql_vs_nosql"]
    assert revision["content_hash"]

    run_response = await client.post(
        "/api/v1/analysis-runs",
        json={
            "scenario_revision_id": revision["id"],
            "strategy_id": "fake-baseline",
            "strategy_version": "1",
        },
    )
    assert run_response.status_code == 202, run_response.text
    created_run = run_response.json()

    terminal_run = await _wait_for_terminal_run(client, created_run["id"])
    assert terminal_run["status"] == "completed"
    assert terminal_run["progress_sequence"] >= created_run["progress_sequence"]
    # The first (and only, for a valid fake response) validation attempt is evidence
    # that the original generated output was retained and assessed before publishing ADR.
    assert terminal_run["validation_attempts"]
    original_attempt = terminal_run["validation_attempts"][0]
    assert original_attempt["attempt"] == "original"
    assert original_attempt["artifact_id"]
    assert original_attempt["parse_succeeded"] is True

    events_response = await client.get(f"/api/v1/analysis-runs/{created_run['id']}/events")
    assert events_response.status_code == 200, events_response.text
    assert events_response.headers["content-type"].startswith("text/event-stream")
    event_payloads = [
        json.loads(line.removeprefix("data: "))
        for line in events_response.text.splitlines()
        if line.startswith("data: ")
    ]
    assert event_payloads
    assert event_payloads[0]["run_id"] == created_run["id"]
    assert event_payloads[-1]["status"] == "completed"
    assert event_payloads[-1]["progress_sequence"] == terminal_run["progress_sequence"]

    adr_response = await client.get(f"/api/v1/analysis-runs/{created_run['id']}/adr")
    assert adr_response.status_code == 200, adr_response.text
    adr = adr_response.json()
    assert adr["analysis_run_id"] == created_run["id"]
    assert adr["status"] == "proposed"
    assert adr["decision"] == "PostgreSQL"

    export_response = await client.get(
        f"/api/v1/analysis-runs/{created_run['id']}/export?format=markdown"
    )
    assert export_response.status_code == 200, export_response.text
    assert export_response.headers["content-type"].startswith("text/markdown")
    assert "attachment" in export_response.headers["content-disposition"]
    assert f"# {adr['title']}" in export_response.text
    assert "## Decisão" in export_response.text
    assert adr["decision"] in export_response.text

"""Contract coverage for immutable clarification revisions."""

from __future__ import annotations

import httpx
import pytest
from tests.integration.test_analysis_vertical_slice import client as client_fixture


@pytest.mark.asyncio
async def test_clarification_answers_create_a_new_revision_and_reject_stale_base(
    client: httpx.AsyncClient,
) -> None:
    created = await client.post(
        "/api/v1/scenarios",
        json={
            "title": "Contexto incompleto",
            "language": "pt-BR",
            "problem": "Precisamos escolher a persistência para o catálogo local de uma aplicação.",
        },
    )
    assert created.status_code == 201, created.text
    scenario = created.json()
    base = scenario["current_revision"]
    run = await client.post(
        "/api/v1/analysis-runs",
        json={
            "scenario_revision_id": base["id"],
            "strategy_id": "fake-baseline",
            "strategy_version": "1",
        },
    )
    assert run.status_code == 202, run.text
    adr = await client.get(f"/api/v1/analysis-runs/{run.json()['id']}/adr")
    assert adr.status_code == 200, adr.text
    question = adr.json()["unresolved_questions"][0]
    payload = {
        "base_revision_number": 1,
        "clarification_answers": [
            {
                "question_id": question["id"],
                "answer": "Esperamos até dez mil produtos e cem pedidos por dia.",
                "source_run_id": run.json()["id"],
            }
        ],
    }
    revision = await client.post(f"/api/v1/scenarios/{scenario['id']}/revisions", json=payload)
    assert revision.status_code == 201, revision.text
    assert revision.json()["revision_number"] == 2
    assert revision.json()["clarification_answers"][0]["question"] == question["question"]
    stale = await client.post(f"/api/v1/scenarios/{scenario['id']}/revisions", json=payload)
    assert stale.status_code == 409
    assert stale.json()["code"] == "stale_revision"


client = client_fixture

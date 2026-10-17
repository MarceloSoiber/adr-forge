"""Contract-level checks for the local system endpoints."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from apps.api.main import create_app
from fastapi import FastAPI

from adr_forge.shared.config import Settings
from adr_forge.system.resources import (
    DiskCapacity,
    GpuCapacity,
    MemoryCapacity,
    ResourceSnapshot,
)


class FixedResourceProbe:
    def __init__(self, disk: DiskCapacity) -> None:
        self._disk = disk

    def disk_capacity(self, _: Path) -> DiskCapacity:
        return self._disk

    def snapshot(self, _: Path) -> ResourceSnapshot:
        return ResourceSnapshot(
            disk=self._disk,
            memory=MemoryCapacity(total_bytes=32, available_bytes=16, available=True),
            gpu=GpuCapacity(available=False, total_vram_bytes=None, free_vram_bytes=None),
        )


def _app(tmp_path: Path, disk: DiskCapacity, *, token: str | None = None) -> FastAPI:
    application = create_app(
        Settings(
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'adr-forge.sqlite3'}",
            artifact_root=tmp_path / "artifacts",
            model_revision="cdbee75f17c01a7cc42f958dc650907174af0554",
            knowledge_hub_token=token,
        )
    )
    application.state.resources = FixedResourceProbe(disk)
    return application


@pytest.mark.asyncio
async def test_system_routes_match_their_public_response_shapes(tmp_path: Path) -> None:
    application = _app(
        tmp_path,
        DiskCapacity(total_bytes=20 * 1024**3, free_bytes=10 * 1024**3, available=True),
    )
    transport = httpx.ASGITransport(app=application)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        health = await client.get("/api/v1/health")
        readiness = await client.get("/api/v1/readiness")
        resources = await client.get("/api/v1/system/resources")
        integration = await client.get("/api/v1/integrations/knowledge-hub")

    assert health.json() == {"status": "ok"}
    assert readiness.json() == {
        "ready": True,
        "checks": {"artifact_root": True, "disk_capacity": True, "disk_reserve": True},
    }
    assert set(resources.json()) == {"disk", "memory", "gpu", "artifact_budget", "blockers"}
    assert resources.json()["blockers"] == []
    assert integration.json() == {
        "name": "knowledge_hub",
        "available": False,
        "reason": "not_configured",
        "latency_ms": None,
    }


@pytest.mark.asyncio
async def test_readiness_returns_the_documented_problem_status_when_disk_is_unavailable(
    tmp_path: Path,
) -> None:
    application = _app(tmp_path, DiskCapacity(None, None, False))
    transport = httpx.ASGITransport(app=application)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/v1/readiness")

    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "precondition_failed"


def test_system_operations_publish_the_committed_operation_ids() -> None:
    paths = create_app().openapi()["paths"]

    health = paths["/api/v1/health"]["get"]
    readiness = paths["/api/v1/readiness"]["get"]
    resources = paths["/api/v1/system/resources"]["get"]
    integration = paths["/api/v1/integrations/knowledge-hub"]["get"]

    assert health["operationId"] == "getHealth"
    assert readiness["operationId"] == "getReadiness"
    assert resources["operationId"] == "getSystemResources"
    assert integration["operationId"] == "getKnowledgeHubStatus"
    assert readiness["responses"]["503"]["content"] == {
        "application/problem+json": {"schema": {"$ref": "#/components/schemas/Problem"}}
    }
    assert health["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/HealthResponse"
    }
    assert resources["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/SystemResources"
    }
    assert integration["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/IntegrationStatus"
    }

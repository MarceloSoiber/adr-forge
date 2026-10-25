"""Small, sanitized system endpoints used before story-specific routes exist."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from adr_forge.shared.errors import PreconditionFailedError


class HealthResponse(BaseModel):
    status: Literal["ok"]


class ReadinessResponse(BaseModel):
    ready: bool
    checks: dict[str, bool]


class SystemResources(BaseModel):
    """Sanitized capacity data for local diagnostics."""

    disk: dict[str, Any]
    memory: dict[str, Any]
    gpu: dict[str, Any]
    artifact_budget: dict[str, Any]
    blockers: list[str] = Field(default_factory=list)


class IntegrationStatus(BaseModel):
    name: str
    available: bool
    reason: str | None = None
    latency_ms: int | None = Field(default=None, ge=0)


_PROBLEM_RESPONSE = {
    "description": "The local storage precondition is not satisfied.",
    "content": {"application/problem+json": {"schema": {"$ref": "#/components/schemas/Problem"}}},
}


router = APIRouter(prefix="/api/v1", tags=["system"])


def _resources(request: Request) -> SystemResources:
    settings = request.app.state.settings
    snapshot = request.app.state.resources.snapshot(settings.artifact_root)
    blockers: list[str] = []
    if not snapshot.disk.available:
        blockers.append("disk_unavailable")
    elif snapshot.disk.free_bytes is None or (
        snapshot.disk.free_bytes < settings.artifact_free_disk_reserve_bytes
    ):
        blockers.append("insufficient_disk_capacity")

    return SystemResources(
        disk={
            "total_bytes": snapshot.disk.total_bytes,
            "free_bytes": snapshot.disk.free_bytes,
            "available": snapshot.disk.available,
        },
        memory={
            "total_bytes": snapshot.memory.total_bytes,
            "available_bytes": snapshot.memory.available_bytes,
            "available": snapshot.memory.available,
        },
        gpu={
            "available": snapshot.gpu.available,
            "total_vram_bytes": snapshot.gpu.total_vram_bytes,
            "free_vram_bytes": snapshot.gpu.free_vram_bytes,
            "processes": [
                {
                    "pid": process.pid,
                    "name": process.name,
                    "used_vram_bytes": process.used_vram_bytes,
                }
                for process in snapshot.gpu.processes
            ],
        },
        artifact_budget={
            "reserve_bytes": settings.artifact_free_disk_reserve_bytes,
            "free_bytes": snapshot.disk.free_bytes,
        },
        blockers=blockers,
    )


@router.get("/health", operation_id="getHealth", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get(
    "/readiness",
    operation_id="getReadiness",
    response_model=ReadinessResponse,
    responses={503: _PROBLEM_RESPONSE},
)
async def readiness(request: Request) -> ReadinessResponse:
    settings = request.app.state.settings
    try:
        settings.artifact_root.mkdir(parents=True, exist_ok=True)
        if not settings.artifact_root.is_dir():
            raise OSError("artifact root is unavailable")
        capacity = request.app.state.resources.disk_capacity(settings.artifact_root)
        if not capacity.available or capacity.free_bytes is None:
            raise OSError("disk capacity is unavailable")
        if capacity.free_bytes < settings.artifact_free_disk_reserve_bytes:
            raise OSError("free disk reserve is unavailable")
    except OSError as exc:
        raise PreconditionFailedError("local storage is not ready") from exc
    return ReadinessResponse(
        ready=True,
        checks={"artifact_root": True, "disk_capacity": True, "disk_reserve": True},
    )


@router.get(
    "/system/resources",
    operation_id="getSystemResources",
    response_model=SystemResources,
)
async def system_resources(request: Request) -> SystemResources:
    return _resources(request)


@router.get(
    "/integrations/knowledge-hub",
    operation_id="getKnowledgeHubStatus",
    response_model=IntegrationStatus,
)
async def knowledge_hub_status(request: Request) -> IntegrationStatus:
    configured = bool(request.app.state.settings.knowledge_hub_token)
    return IntegrationStatus(
        name="knowledge_hub",
        available=configured,
        reason=None if configured else "not_configured",
    )

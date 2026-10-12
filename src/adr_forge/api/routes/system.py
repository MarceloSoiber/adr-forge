"""Small, sanitized system endpoints used before story-specific routes exist."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from adr_forge.shared.errors import PreconditionFailedError

router = APIRouter(tags=["system"])


def _resources(request: Request) -> dict[str, Any]:
    settings = request.app.state.settings
    snapshot = request.app.state.resources.snapshot(settings.artifact_root)
    return {
        "disk": {
            "total_bytes": snapshot.disk.total_bytes,
            "free_bytes": snapshot.disk.free_bytes,
            "available": snapshot.disk.available,
        },
        "memory": {
            "total_bytes": snapshot.memory.total_bytes,
            "available_bytes": snapshot.memory.available_bytes,
            "available": snapshot.memory.available,
        },
        "gpu": {
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
    }


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readiness")
async def readiness(request: Request) -> dict[str, str]:
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
    return {"status": "ready"}


@router.get("/system/resources")
async def system_resources(request: Request) -> dict[str, Any]:
    return _resources(request)


@router.get("/integrations/knowledge-hub")
async def knowledge_hub_status(request: Request) -> dict[str, str]:
    configured = bool(request.app.state.settings.knowledge_hub_token)
    return {"name": "knowledge_hub", "status": "configured" if configured else "not_configured"}

"""Read-only local diagnostics shared by human and automation users."""

from __future__ import annotations

import json
from typing import Annotated, Any

import typer

from adr_forge.shared.config import Settings
from adr_forge.system.resources import HostResourceProbe


def doctor(
    as_json: Annotated[bool, typer.Option("--json", help="Emit one JSON value.")] = False,
) -> None:
    """Inspect local configuration and capacity without changing project data."""
    settings = Settings()
    probe = HostResourceProbe()
    disk = probe.disk_capacity(settings.artifact_root)
    ready = (
        disk.available
        and disk.free_bytes is not None
        and disk.free_bytes >= settings.artifact_free_disk_reserve_bytes
    )
    result: dict[str, Any] = {
        "status": "ok" if ready else "precondition_failed",
        "database": "configured",
        "artifact_root": str(settings.artifact_root),
        "disk": {"available": disk.available, "free_bytes": disk.free_bytes},
        "gpu": {"available": probe.gpu_capacity().available},
        "knowledge_hub": {"configured": bool(settings.knowledge_hub_token)},
    }
    if as_json:
        typer.echo(json.dumps(result, separators=(",", ":"), sort_keys=True))
    else:
        typer.echo(f"ADR Forge doctor: {result['status']}")
        typer.echo(f"Disk available: {disk.available}")
        typer.echo(f"GPU available: {result['gpu']['available']}")
    if not ready:
        raise typer.Exit(code=3)

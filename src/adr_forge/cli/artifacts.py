"""Artifact inspection and explicitly confirmed cleanup commands."""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict
from typing import Annotated

import typer
from sqlalchemy.ext.asyncio import AsyncEngine

from adr_forge.artifacts.repository import ArtifactRepository
from adr_forge.artifacts.service import ArtifactCapacityError, ArtifactMaintenance
from adr_forge.artifacts.store import ArtifactStore
from adr_forge.persistence.database import create_database_engine, create_session_factory
from adr_forge.shared.config import Settings
from adr_forge.system.resources import HostResourceProbe


def _maintenance() -> tuple[ArtifactMaintenance, AsyncEngine]:
    settings = Settings()
    engine = create_database_engine(settings.database_url)
    return (
        ArtifactMaintenance(
            ArtifactRepository(create_session_factory(engine)),
            ArtifactStore(settings.artifact_root),
        ),
        engine,
    )


def artifacts_list(as_json: Annotated[bool, typer.Option("--json")] = False) -> None:
    """List catalogued artifacts in deterministic order without reconciling storage."""

    async def run() -> dict[str, object]:
        maintenance, engine = _maintenance()
        try:
            rows = await maintenance.list()
            settings = Settings()
            disk = HostResourceProbe().disk_capacity(settings.artifact_root)
            return {
                "artifacts": [asdict(row) for row in rows],
                "artifact_count": len(rows),
                "used_bytes": sum(row.size_bytes for row in rows),
                "warning_bytes": settings.artifact_warning_bytes,
                "limit_bytes": settings.artifact_limit_bytes,
                "free_bytes": disk.free_bytes,
                "reserve_bytes": settings.artifact_free_disk_reserve_bytes,
            }
        finally:
            await engine.dispose()

    payload = asyncio.run(run())
    typer.echo(json.dumps(payload, default=str, sort_keys=True) if as_json else str(payload))


def artifacts_prune(
    confirm: Annotated[bool, typer.Option("--confirm")] = False,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Delete only eligible, unreferenced artifacts after explicit confirmation."""

    async def run() -> dict[str, object]:
        maintenance, engine = _maintenance()
        try:
            report = await maintenance.prune(confirmed=confirm)
            return {
                "operation_id": report.operation_id,
                "selected_count": len(report.results),
                "deleted_count": sum(item.status == "deleted" for item in report.results),
                "failed_count": sum(item.status == "failed" for item in report.results),
                "reclaimed_bytes": report.reclaimed_bytes,
                "results": [asdict(item) for item in report.results],
            }
        finally:
            await engine.dispose()

    try:
        payload = asyncio.run(run())
    except ArtifactCapacityError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc
    typer.echo(json.dumps(payload, default=str, sort_keys=True) if as_json else str(payload))

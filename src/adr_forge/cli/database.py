"""Database maintenance commands exposed through the local CLI."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from sqlalchemy.engine import make_url

from adr_forge import __version__
from adr_forge.persistence.backup import BackupError, create_sqlite_backup
from adr_forge.shared.config import Settings


def database_backup(
    output: Path = typer.Option(  # noqa: B008
        ..., "--output", exists=False, file_okay=True, dir_okay=False
    ),
    json_output: bool = typer.Option(False, "--json", help="Emit one JSON result."),
) -> None:
    """Create a verified, non-overwriting SQLite backup and sidecar manifest."""

    settings = Settings()
    database_url = make_url(settings.database_url)
    if database_url.get_backend_name() != "sqlite" or database_url.database is None:
        raise typer.BadParameter("configured database must be a SQLite file")
    try:
        result = create_sqlite_backup(
            Path(database_url.database), output, application_version=__version__
        )
    except BackupError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc

    payload = {
        "database_path": str(result.database_path),
        "manifest_path": str(result.manifest_path),
        **result.manifest.as_dict(),
    }
    if json_output:
        typer.echo(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return
    typer.echo(f"Backup created: {result.database_path}")
    typer.echo(f"Manifest created: {result.manifest_path}")

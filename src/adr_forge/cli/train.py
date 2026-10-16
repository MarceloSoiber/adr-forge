"""Foreground, guarded QLoRA training command."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from adr_forge.system.gpu_lease import GpuLease, GpuPreflight
from adr_forge.system.resources import HostResourceProbe
from adr_forge.training.service import TrainingPreconditionError, TrainingService
from adr_forge.training.sft import SFTExecutionError, load_sft_config


def train_sft(
    config: Path = typer.Option(..., exists=True, readable=True),  # noqa: B008
    resume: bool = typer.Option(False),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Run local QLoRA only after GPU and disk safety checks pass."""
    try:
        resolved = load_sft_config(config)
    except SFTExecutionError as exc:
        typer.echo(f"invalid training config: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    probe = HostResourceProbe()
    service = TrainingService(
        preflight=GpuPreflight(probe, minimum_free_vram_bytes=1).check,
        lease=GpuLease(resolved.output_dir / ".gpu.lock"),
        minimum_free_disk_bytes=1,
    )
    typer.echo(json.dumps({"stage": "preflight"}), err=True)
    try:
        outcome = service.run(resolved, trainer_factory=None, resume=resume)
    except TrainingPreconditionError as exc:
        typer.echo(f"training precondition failed: {exc}", err=True)
        raise typer.Exit(code=3) from exc
    except SFTExecutionError as exc:
        typer.echo(f"training unavailable or failed: {exc}", err=True)
        raise typer.Exit(code=4 if "install adr-forge[ml]" in str(exc) else 1) from exc
    result = {"status": "completed", "adapter_manifest": str(outcome.result.adapter_manifest)}
    typer.echo(json.dumps({"stage": "completed"}), err=True)
    typer.echo(json.dumps(result) if json_output else str(result))

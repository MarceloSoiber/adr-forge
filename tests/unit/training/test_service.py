"""Resource gates for foreground SFT orchestration."""

from __future__ import annotations

from pathlib import Path

import pytest

from adr_forge.system.gpu_lease import GpuLease, PreflightResult
from adr_forge.system.resources import GpuCapacity
from adr_forge.training.service import TrainingPreconditionError, TrainingService
from adr_forge.training.sft import SFTConfig


def _config(tmp_path: Path) -> SFTConfig:
    return SFTConfig(
        model_id="Qwen/Qwen3-4B-Instruct-2507",
        model_revision="revision",
        dataset_path=tmp_path / "training.jsonl",
        output_dir=tmp_path / "output",
        max_seq_length=32,
        seed=1,
        save_steps=1,
        lora_rank=8,
        lora_alpha=16,
        lora_dropout=0.0,
        load_in_4bit=True,
    )


def test_training_service_checks_gpu_before_invoking_the_trainer(tmp_path: Path) -> None:
    called = False

    def preflight() -> PreflightResult:
        return PreflightResult(False, ("insufficient_vram",), GpuCapacity(False, None, None))

    service = TrainingService(
        preflight=preflight,
        lease=GpuLease(tmp_path / "gpu.lock"),
        minimum_free_disk_bytes=1,
    )

    def trainer_factory(*_args: object) -> object:
        nonlocal called
        called = True
        return object()

    with pytest.raises(TrainingPreconditionError, match="insufficient_vram"):
        service.run(_config(tmp_path), trainer_factory=trainer_factory)  # type: ignore[arg-type]
    assert called is False

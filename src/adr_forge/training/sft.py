"""Framework-neutral orchestration for completion-only SFT runs.

The actual trainer is supplied by the caller.  Keeping the orchestration here
free from ML imports makes validation and artifact bookkeeping usable on CPU
only development and CI environments.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol


class SFTExecutionError(RuntimeError):
    """Raised when an SFT run cannot safely publish its adapter artifacts."""


@dataclass(frozen=True, slots=True)
class SFTConfig:
    """All inputs that affect a reproducible fine-tuning run."""

    model_id: str
    model_revision: str
    dataset_path: Path
    output_dir: Path
    max_seq_length: int
    seed: int
    save_steps: int
    lora_rank: int
    lora_alpha: int
    lora_dropout: float
    load_in_4bit: bool

    def __post_init__(self) -> None:
        if not self.model_id.strip():
            raise ValueError("model_id must not be empty")
        if not self.model_revision.strip():
            raise ValueError("model_revision must not be empty")
        if self.max_seq_length <= 0 or self.save_steps <= 0:
            raise ValueError("max_seq_length and save_steps must be positive")
        if self.lora_rank <= 0 or self.lora_alpha <= 0:
            raise ValueError("LoRA rank and alpha must be positive")


@dataclass(frozen=True, slots=True)
class SFTResult:
    adapter_manifest: Path
    adapter_sha256: str


class Trainer(Protocol):
    def train(self, *, resume_from_checkpoint: Path | None = None) -> None: ...

    def save_adapter(self, target: Path) -> None: ...


TrainerFactory = Callable[[SFTConfig, list[dict[str, object]]], Trainer]


def format_completion_example(example: dict[str, object]) -> dict[str, object]:
    """Mark the assistant completion as the only text contributing to loss."""
    prompt = example.get("prompt")
    completion = example.get("completion")
    if not isinstance(prompt, str) or not isinstance(completion, str):
        raise ValueError("each training example requires string prompt and completion fields")
    return {
        "text": f"{prompt}{completion}",
        "assistant_start": len(prompt),
        "loss_scope": "completion_only",
    }


def _load_examples(dataset_path: Path) -> list[dict[str, object]]:
    try:
        lines = dataset_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise SFTExecutionError(f"cannot read training dataset: {exc}") from exc

    examples: list[dict[str, object]] = []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SFTExecutionError(f"invalid JSONL at line {line_number}: {exc.msg}") from exc
        if not isinstance(payload, dict):
            raise SFTExecutionError(f"invalid training example at line {line_number}")
        try:
            examples.append(format_completion_example(payload))
        except ValueError as exc:
            raise SFTExecutionError(
                f"invalid training example at line {line_number}: {exc}"
            ) from exc
    if not examples:
        raise SFTExecutionError("training dataset contains no examples")
    return examples


def _latest_checkpoint(output_dir: Path) -> Path | None:
    checkpoints = output_dir / "checkpoints"
    complete = [
        candidate
        for candidate in checkpoints.glob("checkpoint-*")
        if candidate.is_dir() and (candidate / "trainer_state.json").is_file()
    ]
    if not complete:
        return None
    return max(complete, key=lambda candidate: candidate.name)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as artifact:
        for chunk in iter(lambda: artifact.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _effective_config(config: SFTConfig) -> dict[str, object]:
    values = asdict(config)
    values["dataset_path"] = str(config.dataset_path)
    values["output_dir"] = str(config.output_dir)
    return values


def run_sft(
    config: SFTConfig,
    *,
    trainer_factory: TrainerFactory,
    resume: bool = False,
) -> SFTResult:
    """Train an adapter and publish its manifest only after a complete save."""
    examples = _load_examples(config.dataset_path)
    config.output_dir.mkdir(parents=True, exist_ok=True)
    trainer = trainer_factory(config, examples)
    temporary_adapter = config.output_dir / ".adapter.tmp"
    final_adapter = config.output_dir / "adapter"
    manifest_path = config.output_dir / "adapter-manifest.json"

    if temporary_adapter.exists():
        shutil.rmtree(temporary_adapter)

    try:
        trainer.train(
            resume_from_checkpoint=_latest_checkpoint(config.output_dir) if resume else None
        )
        trainer.save_adapter(temporary_adapter)
        adapter_files = sorted(path for path in temporary_adapter.rglob("*") if path.is_file())
        if not adapter_files:
            raise SFTExecutionError("trainer did not produce an adapter artifact")
        adapter_sha256 = _sha256_file(adapter_files[0])
        if final_adapter.exists():
            raise SFTExecutionError("refusing to overwrite an existing adapter")
        temporary_adapter.replace(final_adapter)
        manifest = {
            "model": {"id": config.model_id, "revision": config.model_revision},
            "adapter": {"sha256": adapter_sha256},
            "effective_config": _effective_config(config),
        }
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        return SFTResult(adapter_manifest=manifest_path, adapter_sha256=adapter_sha256)
    except Exception as exc:
        if temporary_adapter.exists():
            shutil.rmtree(temporary_adapter)
        if manifest_path.exists():
            manifest_path.unlink()
        if isinstance(exc, SFTExecutionError):
            raise
        raise SFTExecutionError(str(exc)) from exc

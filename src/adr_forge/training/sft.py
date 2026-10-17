"""Framework-neutral orchestration and lazy QLoRA construction for SFT runs.

Importing this module must be safe on CPU-only machines.  Optional ML packages
are imported only by :func:`create_trl_trainer`, after the caller has validated
the run inputs and acquired any resource lease.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Protocol, cast

import yaml

from adr_forge.shared.hashing import canonical_json


class SFTExecutionError(RuntimeError):
    """Raised when an SFT run cannot safely publish its adapter artifacts."""


@dataclass(frozen=True, slots=True)
class SFTConfig:
    """Resolved values that influence an SFT run.

    The small framework-independent shape is also the boundary used by fake
    trainers in tests.  Additional production settings intentionally have
    defaults so older, explicit programmatic callers remain compatible.
    """

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
    learning_rate: float = 2e-4
    num_train_epochs: float = 1.0
    per_device_train_batch_size: int = 1
    gradient_accumulation_steps: int = 1
    logging_steps: int = 1
    dataset_build_sha256: str | None = None
    dataset_manifest_sha256: str | None = None
    code_revision: str = "unknown"
    trust_remote_code: bool = False
    use_safetensors: bool = True

    def __post_init__(self) -> None:
        if not self.model_id.strip() or not self.model_revision.strip():
            raise ValueError("model_id and model_revision must not be empty")
        if self.trust_remote_code or not self.use_safetensors:
            raise ValueError("training requires trust_remote_code=false and safetensors=true")
        positive = (
            self.max_seq_length,
            self.save_steps,
            self.lora_rank,
            self.lora_alpha,
            self.per_device_train_batch_size,
            self.gradient_accumulation_steps,
            self.logging_steps,
        )
        if any(value <= 0 for value in positive):
            raise ValueError("training sizes, LoRA values, and intervals must be positive")
        if self.learning_rate <= 0 or self.num_train_epochs <= 0:
            raise ValueError("learning_rate and num_train_epochs must be positive")
        if not 0 <= self.lora_dropout < 1:
            raise ValueError("lora_dropout must be in [0, 1)")

    def model_copy(self, *, update: dict[str, object] | None = None) -> SFTConfig:
        """Pydantic-compatible convenience used by the opt-in smoke test."""
        return replace(self, **cast(Any, update or {}))


@dataclass(frozen=True, slots=True)
class SFTResult:
    adapter_manifest: Path
    adapter_sha256: str


class Trainer(Protocol):
    def train(self, *, resume_from_checkpoint: Path | None = None) -> None: ...

    def save_adapter(self, target: Path) -> None: ...


TrainerFactory = Callable[[SFTConfig, list[dict[str, object]]], Trainer]


def format_completion_example(example: dict[str, object]) -> dict[str, object]:
    """Expose the exact prompt/completion boundary for completion-only loss."""
    prompt, completion = example.get("prompt"), example.get("completion")
    if not isinstance(prompt, str) or not isinstance(completion, str):
        raise ValueError("each training example requires string prompt and completion fields")
    if not prompt or not completion:
        raise ValueError("training prompt and completion must not be empty")
    return {
        "text": f"{prompt}{completion}",
        # Keep the two fields separately as well.  Current TRL releases use
        # this shape to create the completion mask, while ``text`` and
        # ``assistant_start`` remain useful, framework-neutral evidence of the
        # intended boundary.
        "prompt": prompt,
        "completion": completion,
        "assistant_start": len(prompt),
        "loss_scope": "completion_only",
    }


def load_sft_config(path: Path) -> SFTConfig:
    """Load a YAML configuration without importing any ML dependency."""
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise SFTExecutionError(f"cannot load training config: {exc}") from exc
    if not isinstance(document, dict):
        raise SFTExecutionError("training config must be a mapping")
    model_path = document.pop("model_config", None)
    if model_path is not None:
        if not isinstance(model_path, str):
            raise SFTExecutionError("model_config must be a path")
        try:
            model = yaml.safe_load((path.parent / model_path).read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise SFTExecutionError(f"cannot load model config: {exc}") from exc
        if not isinstance(model, dict):
            raise SFTExecutionError("model config must be a mapping")
        document = {**model, **document}
    for key in ("dataset_path", "output_dir"):
        value = document.get(key)
        if isinstance(value, str):
            document[key] = (path.parent / value).resolve()
    if "model_revision" in document:
        document["model_revision"] = str(document["model_revision"])
    try:
        return SFTConfig(**document)
    except (TypeError, ValueError) as exc:
        raise SFTExecutionError(f"invalid training config: {exc}") from exc


def _load_examples(dataset_path: Path, limit: int | None) -> list[dict[str, object]]:
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
            if not isinstance(payload, dict):
                raise ValueError("must be an object")
            examples.append(format_completion_example(payload))
        except (json.JSONDecodeError, ValueError) as exc:
            detail = exc.msg if isinstance(exc, json.JSONDecodeError) else str(exc)
            raise SFTExecutionError(
                f"invalid training example at line {line_number}: {detail}"
            ) from exc
        if limit is not None and len(examples) >= limit:
            break
    if not examples:
        raise SFTExecutionError("training dataset contains no examples")
    return examples


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_records(root: Path) -> list[dict[str, object]]:
    records = []
    for item in sorted(
        (path for path in root.rglob("*") if path.is_file()), key=lambda path: path.as_posix()
    ):
        relative = item.relative_to(root).as_posix()
        records.append(
            {"path": relative, "size": item.stat().st_size, "sha256": _sha256_file(item)}
        )
    return records


def _hash_records(records: Iterable[dict[str, object]]) -> str:
    return hashlib.sha256(canonical_json(list(records)).encode("utf-8")).hexdigest()


def _effective_config(config: SFTConfig) -> dict[str, object]:
    values = asdict(config)
    values["dataset_path"] = str(config.dataset_path)
    values["output_dir"] = str(config.output_dir)
    return values


def _resume_config(config: SFTConfig, dataset_sha256: str) -> dict[str, object]:
    values = _effective_config(config)
    values.pop("output_dir")
    values["dataset_sha256"] = dataset_sha256
    return values


def _config_hash(config: SFTConfig, dataset_sha256: str) -> str:
    return hashlib.sha256(
        canonical_json(_resume_config(config, dataset_sha256)).encode("utf-8")
    ).hexdigest()


def _checkpoint_metadata(checkpoint: Path, config_hash: str) -> Path:
    return checkpoint / ".adr-forge-checkpoint.json"


def _record_complete_checkpoints(output_dir: Path, config_hash: str) -> None:
    root = output_dir / "checkpoints"
    if not root.is_dir():
        return
    for checkpoint in root.glob("checkpoint-*"):
        state = checkpoint / "trainer_state.json"
        if not checkpoint.is_dir() or not state.is_file():
            continue
        metadata = _checkpoint_metadata(checkpoint, config_hash)
        if metadata.exists():
            continue
        files = _file_records(checkpoint)
        _atomic_json(
            metadata,
            {
                "config_sha256": config_hash,
                "files": files,
                "aggregate_sha256": _hash_records(files),
            },
        )


def _latest_checkpoint(output_dir: Path, config_hash: str) -> Path | None:
    candidates: list[tuple[int, Path]] = []
    for candidate in (output_dir / "checkpoints").glob("checkpoint-*"):
        suffix = candidate.name.removeprefix("checkpoint-")
        metadata = _checkpoint_metadata(candidate, config_hash)
        if (
            not candidate.is_dir()
            or not suffix.isdecimal()
            or not (candidate / "trainer_state.json").is_file()
        ):
            continue
        try:
            record = json.loads(metadata.read_text(encoding="utf-8"))
            files = record["files"]
            if record["config_sha256"] != config_hash or record[
                "aggregate_sha256"
            ] != _hash_records(files):
                continue
            if not isinstance(files, list) or any(not isinstance(item, dict) for item in files):
                continue
            if any(_sha256_file(candidate / str(item["path"])) != item["sha256"] for item in files):
                continue
        except (OSError, KeyError, TypeError, json.JSONDecodeError):
            continue
        candidates.append((int(suffix), candidate))
    return max(candidates, default=(0, None), key=lambda item: item[0])[1]


def _atomic_json(path: Path, payload: dict[str, object]) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("x", encoding="utf-8") as target:
        target.write(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
        target.flush()
        os.fsync(target.fileno())
    temporary.replace(path)


def _hardware_evidence() -> dict[str, object]:
    """Capture CUDA evidence when optional ML training has used a GPU."""
    try:
        import torch
    except ImportError:
        return {"cuda_device": None, "peak_vram_bytes": 0}
    if not torch.cuda.is_available():
        return {"cuda_device": None, "peak_vram_bytes": 0}
    return {
        "cuda_device": torch.cuda.get_device_name(0),
        "peak_vram_bytes": torch.cuda.max_memory_allocated(),
    }


def run_sft(
    config: SFTConfig,
    *,
    trainer_factory: TrainerFactory | None = None,
    resume: bool = False,
    max_train_examples: int | None = None,
) -> SFTResult:
    """Train and atomically publish a complete, multi-file adapter manifest."""
    if max_train_examples is not None and max_train_examples <= 0:
        raise SFTExecutionError("max_train_examples must be positive")
    examples = _load_examples(config.dataset_path, max_train_examples)
    dataset_sha256 = _sha256_file(config.dataset_path)
    config_sha256 = _config_hash(config, dataset_sha256)
    config.output_dir.mkdir(parents=True, exist_ok=True)
    final_adapter, manifest_path = (
        config.output_dir / "adapter",
        config.output_dir / "adapter-manifest.json",
    )
    temporary_adapter = config.output_dir / ".adapter.tmp"
    if final_adapter.exists() or manifest_path.exists():
        raise SFTExecutionError("refusing to overwrite an existing adapter publication")
    if temporary_adapter.exists():
        shutil.rmtree(temporary_adapter)
    checkpoint = _latest_checkpoint(config.output_dir, config_sha256) if resume else None
    if (
        resume
        and checkpoint is None
        and any((config.output_dir / "checkpoints").glob("checkpoint-*"))
    ):
        raise SFTExecutionError("no compatible complete checkpoint available for resume")
    started = time.monotonic()
    published = False
    try:
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.reset_peak_memory_stats()
        except ImportError:
            pass
        trainer = (trainer_factory or create_trl_trainer)(config, examples)
        trainer.train(resume_from_checkpoint=checkpoint)
        _record_complete_checkpoints(config.output_dir, config_sha256)
        trainer.save_adapter(temporary_adapter)
        files = _file_records(temporary_adapter)
        if not files:
            raise SFTExecutionError("trainer did not produce an adapter artifact")
        aggregate = _hash_records(files)
        temporary_adapter.replace(final_adapter)
        published = True
        hardware = _hardware_evidence()
        manifest: dict[str, object] = {
            "schema_version": "adapter-v1",
            "model": {"id": config.model_id, "revision": config.model_revision},
            "dataset": {
                "sha256": dataset_sha256,
                "build_sha256": config.dataset_build_sha256,
                "manifest_sha256": config.dataset_manifest_sha256,
            },
            "effective_config": _effective_config(config),
            "effective_config_sha256": config_sha256,
            "code_revision": config.code_revision,
            "adapter": {"files": files, "sha256": aggregate},
            "hardware": hardware,
            "peak_vram_bytes": hardware["peak_vram_bytes"],
            "duration_seconds": time.monotonic() - started,
            "terminal_outcome": "completed",
        }
        _atomic_json(manifest_path, manifest)
        return SFTResult(adapter_manifest=manifest_path, adapter_sha256=aggregate)
    except Exception as exc:
        if temporary_adapter.exists():
            shutil.rmtree(temporary_adapter)
        if published and final_adapter.exists():
            shutil.rmtree(final_adapter)
        if manifest_path.exists():
            manifest_path.unlink()
        if isinstance(exc, SFTExecutionError):
            raise
        raise SFTExecutionError(str(exc)) from exc


def create_trl_trainer(config: SFTConfig, examples: list[dict[str, object]]) -> Trainer:
    """Construct the production TRL/PEFT trainer lazily.

    This function is deliberately the only optional-ML import boundary.  TRL's
    trainer receives canonical prompt/completion rows, ensuring current TRL
    releases build the completion-only loss mask without a deprecated custom
    collator.
    """
    try:
        from datasets import Dataset  # type: ignore[attr-defined]
        from peft import LoraConfig, TaskType
        from transformers import (
            AutoModelForCausalLM,
            AutoTokenizer,
            BitsAndBytesConfig,
        )
        from trl import SFTConfig as TRLSFTConfig
        from trl import SFTTrainer
    except ImportError as exc:  # pragma: no cover - depends on the optional ml extra
        raise SFTExecutionError("install adr-forge[ml] to run QLoRA training") from exc
    tokenizer = AutoTokenizer.from_pretrained(
        config.model_id,
        revision=config.model_revision,
        trust_remote_code=False,
        use_safetensors=True,
    )
    tokenizer.pad_token = tokenizer.pad_token or tokenizer.eos_token
    quantization = BitsAndBytesConfig(
        load_in_4bit=config.load_in_4bit, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True
    )
    model = AutoModelForCausalLM.from_pretrained(
        config.model_id,
        revision=config.model_revision,
        trust_remote_code=False,
        use_safetensors=True,
        quantization_config=quantization,
        device_map="auto",
    )
    arguments = TRLSFTConfig(
        output_dir=str(config.output_dir),
        seed=config.seed,
        learning_rate=config.learning_rate,
        num_train_epochs=config.num_train_epochs,
        per_device_train_batch_size=config.per_device_train_batch_size,
        gradient_accumulation_steps=config.gradient_accumulation_steps,
        logging_steps=config.logging_steps,
        save_steps=config.save_steps,
        save_strategy="steps",
        report_to=[],
        max_length=config.max_seq_length,
        completion_only_loss=True,
    )
    trainer = SFTTrainer(
        model=model,
        args=arguments,
        train_dataset=Dataset.from_list(
            [
                {"prompt": example["prompt"], "completion": example["completion"]}
                for example in examples
            ]
        ),
        processing_class=tokenizer,
        peft_config=LoraConfig(
            task_type=TaskType.CAUSAL_LM,
            r=config.lora_rank,
            lora_alpha=config.lora_alpha,
            lora_dropout=config.lora_dropout,
            bias="none",
        ),
    )
    return _TRLTrainer(trainer)


class _TRLTrainer:
    def __init__(self, trainer: Any) -> None:
        self._trainer = trainer

    def train(self, *, resume_from_checkpoint: Path | None = None) -> None:
        self._trainer.train(
            resume_from_checkpoint=str(resume_from_checkpoint) if resume_from_checkpoint else None
        )

    def save_adapter(self, target: Path) -> None:
        self._trainer.save_model(str(target))

"""Contract-first unit tests for the local completion-only SFT pipeline.

The public API under test is intentionally framework-neutral: ``SFTConfig``
captures all effective inputs, ``format_completion_example`` exposes the
assistant-only loss boundary, and ``run_sft`` accepts factories so its
orchestration can be exercised without importing optional ML dependencies.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest


def _config(tmp_path: Path, **overrides: object) -> Any:
    from adr_forge.training.sft import SFTConfig

    values: dict[str, object] = {
        "model_id": "Qwen/Qwen3-4B-Instruct-2507",
        "model_revision": "4b7e2d3c",
        "dataset_path": tmp_path / "training.jsonl",
        "output_dir": tmp_path / "output",
        "max_seq_length": 512,
        "seed": 7,
        "save_steps": 2,
        "lora_rank": 8,
        "lora_alpha": 16,
        "lora_dropout": 0.05,
        "load_in_4bit": True,
    }
    values.update(overrides)
    return SFTConfig(**values)


def test_sft_config_captures_reproducible_effective_values(tmp_path: Path) -> None:
    """Config must reject ambiguous runs before model allocation."""
    config = _config(tmp_path)

    assert config.model_id == "Qwen/Qwen3-4B-Instruct-2507"
    assert config.model_revision == "4b7e2d3c"
    assert config.load_in_4bit is True
    assert config.lora_rank == 8

    with pytest.raises(ValueError):
        _config(tmp_path, model_revision="")


def test_completion_formatter_masks_everything_before_assistant_output() -> None:
    from adr_forge.training.sft import format_completion_example

    formatted = format_completion_example(
        {
            "prompt": "Usuário: escolha uma opção\nAssistente:",
            "completion": "Use PostgreSQL por consistência transacional.",
        }
    )

    assert formatted["text"].startswith("Usuário:")
    assert formatted["text"].endswith("consistência transacional.")
    assert formatted["prompt"] == "Usuário: escolha uma opção\nAssistente:"
    assert formatted["completion"] == "Use PostgreSQL por consistência transacional."
    assert formatted["assistant_start"] == len("Usuário: escolha uma opção\nAssistente:")
    assert formatted["loss_scope"] == "completion_only"


def test_chat_prompt_keeps_the_completion_boundary_after_the_assistant_marker() -> None:
    from adr_forge.shared.chat_prompt import render_assistant_prompt

    class Tokenizer:
        def apply_chat_template(
            self, messages: list[dict[str, str]], *, tokenize: bool, add_generation_prompt: bool
        ) -> str:
            assert messages == [{"role": "user", "content": "Gere JSON"}]
            assert tokenize is False
            assert add_generation_prompt is True
            return "<user>Gere JSON</user><assistant>"

    assert render_assistant_prompt(Tokenizer(), "Gere JSON").endswith("<assistant>")


class _FakeTrainer:
    def __init__(self, output_dir: Path, *, fail: bool = False) -> None:
        self.output_dir = output_dir
        self.fail = fail
        self.resume_from_checkpoint: Path | None = None
        self.formatted_examples: list[dict[str, object]] = []

    def train(self, *, resume_from_checkpoint: Path | None = None) -> None:
        self.resume_from_checkpoint = resume_from_checkpoint
        checkpoint = self.output_dir / "checkpoints" / "checkpoint-2"
        checkpoint.mkdir(parents=True, exist_ok=True)
        (checkpoint / "trainer_state.json").write_text('{"step": 2}', encoding="utf-8")
        if self.fail:
            raise RuntimeError("simulated trainer failure")

    def save_adapter(self, target: Path) -> None:
        target.mkdir(parents=True, exist_ok=True)
        (target / "adapter_model.safetensors").write_bytes(b"adapter")
        (target / "adapter_config.json").write_text('{"r": 8}', encoding="utf-8")


def _trainer_factory(
    holder: dict[str, _FakeTrainer], *, fail: bool = False
) -> Callable[[Any, list[dict[str, object]]], _FakeTrainer]:
    def create(config: Any, examples: list[dict[str, object]]) -> _FakeTrainer:
        trainer = _FakeTrainer(config.output_dir, fail=fail)
        trainer.formatted_examples = examples
        holder["trainer"] = trainer
        return trainer

    return create


def test_sft_writes_atomic_checkpoint_and_hashed_adapter_manifest(tmp_path: Path) -> None:
    from adr_forge.training.sft import run_sft

    dataset = tmp_path / "training.jsonl"
    dataset.write_text(
        json.dumps({"prompt": "Pergunta: banco?\nResposta:", "completion": "SQL."}) + "\n",
        encoding="utf-8",
    )
    holder: dict[str, _FakeTrainer] = {}

    result = run_sft(_config(tmp_path), trainer_factory=_trainer_factory(holder))

    checkpoint = tmp_path / "output" / "checkpoints" / "checkpoint-2" / "trainer_state.json"
    assert checkpoint.is_file()
    assert holder["trainer"].formatted_examples[0]["loss_scope"] == "completion_only"
    manifest = json.loads(result.adapter_manifest.read_text(encoding="utf-8"))
    assert manifest["model"] == {
        "id": "Qwen/Qwen3-4B-Instruct-2507",
        "revision": "4b7e2d3c",
    }
    assert manifest["adapter"]["sha256"] == result.adapter_sha256
    assert len(result.adapter_sha256) == 64
    assert [item["path"] for item in manifest["adapter"]["files"]] == [
        "adapter_config.json",
        "adapter_model.safetensors",
    ]
    assert manifest["effective_config"]["lora_rank"] == 8


def test_sft_resumes_from_latest_complete_checkpoint(tmp_path: Path) -> None:
    from adr_forge.training.sft import (
        _config_hash,
        _record_complete_checkpoints,
        _sha256_file,
        run_sft,
    )

    dataset = tmp_path / "training.jsonl"
    dataset.write_text('{"prompt": "P", "completion": "C"}\n', encoding="utf-8")
    checkpoint = tmp_path / "output" / "checkpoints" / "checkpoint-9"
    checkpoint.mkdir(parents=True)
    (checkpoint / "trainer_state.json").write_text('{"step": 9}', encoding="utf-8")
    config = _config(tmp_path)
    _record_complete_checkpoints(checkpoint.parents[1], _config_hash(config, _sha256_file(dataset)))
    holder: dict[str, _FakeTrainer] = {}

    run_sft(config, trainer_factory=_trainer_factory(holder), resume=True)

    assert holder["trainer"].resume_from_checkpoint == checkpoint


def test_sft_rejects_incompatible_or_incomplete_resume_checkpoint(tmp_path: Path) -> None:
    from adr_forge.training.sft import SFTExecutionError, run_sft

    dataset = tmp_path / "training.jsonl"
    dataset.write_text('{"prompt": "P", "completion": "C"}\n', encoding="utf-8")
    checkpoint = tmp_path / "output" / "checkpoints" / "checkpoint-10"
    checkpoint.mkdir(parents=True)
    (checkpoint / "trainer_state.json").write_text('{"step": 10}', encoding="utf-8")

    with pytest.raises(SFTExecutionError, match="compatible complete checkpoint"):
        run_sft(_config(tmp_path), trainer_factory=_trainer_factory({}), resume=True)


def test_load_sft_config_resolves_the_pinned_model_descriptor(tmp_path: Path) -> None:
    from adr_forge.training.sft import load_sft_config

    model = tmp_path / "model.yaml"
    model.write_text(
        "model_id: Qwen/Qwen3-4B-Instruct-2507\nmodel_revision: 1234567\n"
        "trust_remote_code: false\nuse_safetensors: true\n",
        encoding="utf-8",
    )
    config = tmp_path / "run.yaml"
    config.write_text(
        "model_config: model.yaml\ndataset_path: data.jsonl\noutput_dir: artifacts\n"
        "max_seq_length: 128\nseed: 1\nsave_steps: 1\nlora_rank: 8\nlora_alpha: 16\n"
        "lora_dropout: 0.0\nload_in_4bit: true\n",
        encoding="utf-8",
    )

    resolved = load_sft_config(config)

    assert resolved.model_revision == "1234567"
    assert resolved.dataset_path == (tmp_path / "data.jsonl").resolve()


def test_sft_failure_cleans_temporary_adapter_and_never_publishes_manifest(tmp_path: Path) -> None:
    from adr_forge.training.sft import SFTExecutionError, run_sft

    dataset = tmp_path / "training.jsonl"
    dataset.write_text('{"prompt": "P", "completion": "C"}\n', encoding="utf-8")

    with pytest.raises(SFTExecutionError, match="simulated trainer failure"):
        run_sft(_config(tmp_path), trainer_factory=_trainer_factory({}, fail=True))

    output_dir = tmp_path / "output"
    assert not (output_dir / "adapter").exists()
    assert not (output_dir / "adapter-manifest.json").exists()
    assert not list(output_dir.glob("*.tmp"))

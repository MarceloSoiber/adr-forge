"""Opt-in local QLoRA smoke test for the pinned Qwen training path.

This module deliberately does not import the training implementation or ML
frameworks while it is collected by the default CPU-only test suite.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.gpu

_ENABLE_ENV = "ADR_FORGE_QLORA_SMOKE"


def test_qwen_qlora_smoke_records_reproducibility_evidence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Run only after an operator explicitly provisions local GPU artifacts.

    Run manually with ``ADR_FORGE_QLORA_SMOKE=1 pytest -m gpu``. The smoke
    configuration is intentionally tiny; it verifies recorded evidence rather
    than variable generated text or training quality.
    """
    if os.environ.get(_ENABLE_ENV) != "1":
        pytest.skip(f"set {_ENABLE_ENV}=1 to run the local QLoRA smoke")

    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")
    torch = pytest.importorskip("torch", reason="QLoRA smoke requires optional ml dependencies")
    if not torch.cuda.is_available():
        pytest.skip("QLoRA smoke requires a locally available CUDA device")

    from adr_forge.training.sft import load_sft_config, run_sft

    root = Path(__file__).resolve().parents[2]
    config = load_sft_config(root / "configs" / "training" / "qwen3-4b-smoke.yaml")
    result = run_sft(
        config.model_copy(update={"output_dir": tmp_path / "qwen-qlora-smoke"}),
        max_train_examples=1,
    )

    manifest = json.loads(result.adapter_manifest.read_text(encoding="utf-8"))
    assert manifest["model"]["id"] == "Qwen/Qwen3-4B-Instruct-2507"
    assert manifest["model"]["revision"]
    assert manifest["effective_config"]
    assert manifest["hardware"]["cuda_device"]
    assert manifest["duration_seconds"] > 0
    assert manifest["peak_vram_bytes"] > 0
    assert len(manifest["adapter"]["sha256"]) == 64

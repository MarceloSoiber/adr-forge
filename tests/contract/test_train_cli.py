from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from adr_forge.cli.main import app


def test_train_sft_rejects_invalid_config_without_allocating_gpu(tmp_path: Path) -> None:
    config = tmp_path / "invalid.yaml"
    config.write_text("model_id: only\n", encoding="utf-8")

    result = CliRunner().invoke(app, ["train", "sft", "--config", str(config), "--json"])

    assert result.exit_code == 2
    assert result.stdout == ""
    assert result.stderr

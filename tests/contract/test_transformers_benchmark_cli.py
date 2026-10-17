"""Contracts for the opt-in local Transformers benchmark path."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from adr_forge.cli.main import app
from adr_forge.strategies.base import GenerationResult


def test_transformers_benchmark_records_baseline_and_adapter_outputs(
    monkeypatch, tmp_path: Path
) -> None:
    import adr_forge.cli.benchmark_run as command

    manifest = tmp_path / "adapter-manifest.json"
    manifest.write_text("{}", encoding="utf-8")
    adapter = tmp_path / "adapter"
    adapter.mkdir()
    calls: list[Path | None] = []

    class Verified:
        manifest_path = manifest

    class Runtime:
        def __init__(
            self, *, revision: str, max_new_tokens: int, adapter_path: Path | None
        ) -> None:
            calls.append(adapter_path)

        async def generate(self, *_args, **_kwargs) -> GenerationResult:
            return GenerationResult(
                json.dumps(
                    {
                        "status": "proposed",
                        "context": ["contexto"],
                        "alternatives": [{"viable": True}, {"viable": True}],
                        "negative_consequences": ["custo"],
                        "review_triggers": [{"metric": "erros"}],
                        "assumptions": [],
                        "constraints": ["restrição"],
                        "decision": "SQL",
                    }
                )
            )

    monkeypatch.setattr(command, "verify_adapter_manifest", lambda *_args, **_kwargs: Verified())
    monkeypatch.setattr(command, "QwenRuntime", Runtime)
    monkeypatch.chdir(tmp_path)
    config = tmp_path / "comparison.yaml"
    config.write_text(
        """
name: local comparison
rubric: {name: architecture}
execution:
  runtime: transformers
  model_revision: pinned-revision
  adapter_manifest: adapter-manifest.json
generation: {max_new_tokens: 16}
strategies:
  - {id: baseline, version: "1", mode: baseline}
  - {id: tuned, version: "1", mode: adapter}
scenarios:
  - id: scenario
    categories: [sql_vs_nosql]
    problem: Escolher a persistência transacional para o serviço de faturamento.
    facts: [A equipe mantém PostgreSQL.]
    constraints: [Transações são obrigatórias.]
    desired_qualities: [Integridade]
    candidate_alternatives: [PostgreSQL, Documento]
""",
        encoding="utf-8",
    )

    result = CliRunner().invoke(app, ["benchmark", "run", "--config", str(config), "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["runtime"] == "transformers"
    assert payload["accounting"]["completed"] == 2
    assert calls == [None, adapter]
    assert len(payload["executions"]) == 2
    assert all(item["evaluation"]["passed"] for item in payload["executions"].values())

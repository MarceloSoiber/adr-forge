"""Composition tests that avoid importing optional ML dependencies."""

from __future__ import annotations

from pathlib import Path

from adr_forge.shared.config import Settings
from adr_forge.strategies.models import (
    AnalysisStrategy,
    RuntimeKind,
    StrategyAvailability,
    StrategyKind,
)
from adr_forge.strategies.qwen_runtime import QwenRuntime
from adr_forge.strategies.runtime import RuntimeSessionManager, build_runtime

_REVISION = "cdbee75f17c01a7cc42f958dc650907174af0554"


def test_runtime_builds_qwen_adapter_without_importing_ml_dependencies(tmp_path: Path) -> None:
    strategy = AnalysisStrategy(
        id="fine-tuned",
        version="1",
        kind=StrategyKind.FINE_TUNED,
        model_id="Qwen/Qwen3-4B-Instruct-2507",
        model_revision=_REVISION,
        adapter_path=tmp_path / "adapter",
        prompt_version="adr-structured-v1",
        generation_config_hash="a" * 64,
        runtime_kind=RuntimeKind.TRANSFORMERS,
        availability=StrategyAvailability(available=True),
    )

    runtime = build_runtime(strategy, Settings(model_revision=_REVISION))

    assert isinstance(runtime, QwenRuntime)
    assert runtime.adapter_path == tmp_path / "adapter"


def test_runtime_session_reuses_continuation_and_replaces_new_analysis(
    tmp_path: Path, monkeypatch
) -> None:
    strategy = AnalysisStrategy(
        id="fine-tuned",
        version="1",
        kind=StrategyKind.FINE_TUNED,
        model_id="Qwen/Qwen3-4B-Instruct-2507",
        model_revision=_REVISION,
        adapter_path=tmp_path / "adapter",
        prompt_version="adr-structured-v1",
        generation_config_hash="a" * 64,
        runtime_kind=RuntimeKind.TRANSFORMERS,
        availability=StrategyAvailability(available=True),
    )
    created = []

    class Runtime:
        closed = False

        def close(self) -> None:
            self.closed = True

    def factory(*_args):
        runtime = Runtime()
        created.append(runtime)
        return runtime

    monkeypatch.setattr("adr_forge.strategies.runtime.build_runtime", factory)
    sessions = RuntimeSessionManager()

    first = sessions.activate("run-1", strategy, Settings(model_revision=_REVISION))
    continued = sessions.activate(
        "run-2",
        strategy,
        Settings(model_revision=_REVISION),
        continuation_run_id="run-1",
    )
    replacement = sessions.activate("run-3", strategy, Settings(model_revision=_REVISION))

    assert continued is first
    assert replacement is not first
    assert first.closed is True
    assert len(created) == 2

"""Composition of configured strategy metadata into executable runtimes."""

from __future__ import annotations

from adr_forge.shared.config import Settings
from adr_forge.strategies.base import StructuredOutputStrategy
from adr_forge.strategies.fake import FakeStrategy
from adr_forge.strategies.models import AnalysisStrategy, RuntimeKind
from adr_forge.strategies.openai_compatible import OpenAICompatibleStrategy
from adr_forge.strategies.qwen_runtime import QwenRuntime


class RuntimeSessionManager:
    """Keep one runtime alive across clarification runs in the local application."""

    def __init__(self) -> None:
        self._active_run_id: str | None = None
        self._runtime: StructuredOutputStrategy | None = None

    def activate(
        self,
        run_id: str,
        strategy: AnalysisStrategy,
        settings: Settings,
        *,
        continuation_run_id: str | None = None,
    ) -> StructuredOutputStrategy:
        if continuation_run_id == self._active_run_id and self._runtime is not None:
            self._active_run_id = run_id
            return self._runtime
        self.close()
        self._runtime = build_runtime(strategy, settings)
        self._active_run_id = run_id
        return self._runtime

    def close(self) -> None:
        runtime = self._runtime
        self._runtime = None
        self._active_run_id = None
        close = getattr(runtime, "close", None)
        if callable(close):
            close()


def build_runtime(strategy: AnalysisStrategy, settings: Settings) -> StructuredOutputStrategy:
    """Create the runtime selected by a validated, available strategy record."""
    if strategy.runtime_kind is RuntimeKind.FAKE:
        return FakeStrategy()
    if strategy.runtime_kind is RuntimeKind.OPENAI_COMPATIBLE:
        if settings.lm_studio_base_url is None or settings.lm_studio_model_id is None:
            raise ValueError("LM Studio runtime is not configured")
        return OpenAICompatibleStrategy(
            base_url=str(settings.lm_studio_base_url),
            model_id=settings.lm_studio_model_id,
            timeout_seconds=settings.lm_studio_timeout_seconds,
            api_key=(
                settings.lm_studio_api_key.get_secret_value()
                if settings.lm_studio_api_key is not None
                else None
            ),
        )
    if strategy.runtime_kind is RuntimeKind.TRANSFORMERS:
        if strategy.adapter_path is None:
            raise ValueError("Transformers adapter runtime is not configured")
        return QwenRuntime(
            revision=strategy.model_revision,
            adapter_path=strategy.adapter_path,
        )
    raise ValueError(f"No executable runtime is configured for {strategy.id}@{strategy.version}")

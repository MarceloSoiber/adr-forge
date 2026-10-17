"""Composition of configured strategy metadata into executable runtimes."""

from __future__ import annotations

from adr_forge.shared.config import Settings
from adr_forge.strategies.base import StructuredOutputStrategy
from adr_forge.strategies.fake import FakeStrategy
from adr_forge.strategies.models import AnalysisStrategy, RuntimeKind
from adr_forge.strategies.openai_compatible import OpenAICompatibleStrategy


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
    raise ValueError(f"No executable runtime is configured for {strategy.id}@{strategy.version}")

"""Compose strategy discovery from the local application configuration."""

from __future__ import annotations

from importlib.util import find_spec

from adr_forge.shared.config import Settings
from adr_forge.strategies.registry import StrategyRegistry, default_registry


def configured_registry(settings: Settings) -> StrategyRegistry:
    """Build one registry shape for every HTTP consumer without importing ML."""
    adapter_runtime_available = (
        find_spec("transformers") is not None and find_spec("peft") is not None
    )
    return default_registry(
        model_revision=settings.model_revision,
        lm_studio_base_url=settings.lm_studio_base_url,
        lm_studio_model_id=settings.lm_studio_model_id,
        retrieval_configured=settings.knowledge_hub_token is not None,
        adapter_manifest_path=settings.adapter_manifest_path,
        adapter_runtime_available=adapter_runtime_available,
    )

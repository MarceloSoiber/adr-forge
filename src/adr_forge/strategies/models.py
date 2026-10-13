"""Versioned analysis-strategy configuration."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class StrategyKind(StrEnum):
    BASE = "base"
    PROMPTED = "prompted"
    RAG = "rag"
    FINE_TUNED = "fine_tuned"
    FINE_TUNED_RAG = "fine_tuned_rag"


class RuntimeKind(StrEnum):
    TRANSFORMERS = "transformers"
    OPENAI_COMPATIBLE = "openai_compatible"
    FAKE = "fake"


class StrategyAvailability(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    available: bool
    unavailable_reason: str | None = None


class AnalysisStrategy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=3, max_length=80, pattern=r"^[a-z0-9][a-z0-9-]*$")
    version: str = Field(min_length=1)
    kind: StrategyKind
    model_id: str = Field(min_length=1)
    model_revision: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
    generation_config_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    requires_retrieval: bool = False
    runtime_kind: RuntimeKind
    enabled: bool = True
    availability: StrategyAvailability

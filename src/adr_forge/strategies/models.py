"""Versioned analysis-strategy configuration."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from uuid import UUID

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
    unavailable_reason_code: str | None = None


class AnalysisStrategy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=3, max_length=80, pattern=r"^[a-z0-9][a-z0-9-]*$")
    version: str = Field(min_length=1)
    kind: StrategyKind
    model_id: str = Field(min_length=1)
    model_revision: str = Field(min_length=1)
    adapter_artifact_id: UUID | None = None
    adapter_path: Path | None = None
    prompt_version: str = Field(min_length=1)
    generation_config_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    requires_retrieval: bool = False
    runtime_kind: RuntimeKind
    enabled: bool = True
    availability: StrategyAvailability

    def model_post_init(self, __context: object) -> None:
        retrieval_kinds = {StrategyKind.RAG, StrategyKind.FINE_TUNED_RAG}
        fine_tuned_kinds = {StrategyKind.FINE_TUNED, StrategyKind.FINE_TUNED_RAG}
        if self.requires_retrieval != (self.kind in retrieval_kinds):
            raise ValueError("requires_retrieval must match the strategy kind")
        if self.kind not in fine_tuned_kinds and self.adapter_artifact_id is not None:
            raise ValueError("only fine-tuned strategies may specify an adapter artifact")
        if self.kind not in fine_tuned_kinds and self.adapter_path is not None:
            raise ValueError("only fine-tuned strategies may specify an adapter path")

"""Immutable, replayable retrieval evidence snapshots."""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from adr_forge.shared.hashing import canonical_json_bytes, canonical_sha256


class RetrievalFilters(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    limit: int = Field(default=8, ge=1, le=50)
    category_ids: list[int] | None = None
    tag_ids: list[int] | None = None
    project_ids: list[int] | None = None
    min_score: float | None = Field(default=None, ge=0, le=1)
    include_match_reasons: bool = True

    @field_validator("category_ids", "tag_ids", "project_ids")
    @classmethod
    def positive_ids(cls, value: list[int] | None) -> list[int] | None:
        if value is not None and any(item <= 0 for item in value):
            raise ValueError("filter identifiers must be positive")
        return value


class RetrievalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    query: str = Field(min_length=1)
    filters: RetrievalFilters = Field(default_factory=RetrievalFilters)


class EmbeddingIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    model: str = Field(min_length=1)
    version: str = Field(min_length=1)


class RetrievalChunk(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)
    source_id: str = Field(min_length=1)
    chunk_id: int | str = Field(alias="id")
    title: str = Field(alias="source_title", min_length=1)
    uri: str = Field(min_length=1)
    location: dict[str, Any]
    content: str = Field(min_length=1)
    score: float = Field(ge=0, le=1)
    match_reasons: list[str] = Field(default_factory=list)
    rank: int = Field(ge=1)
    source_type: str = "document"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("score")
    @classmethod
    def finite_score(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("score must be finite")
        return value


class RetrievalSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: UUID = Field(default_factory=uuid4)
    schema_version: str = "retrieval-snapshot-v1"
    provider: str = Field(min_length=1)
    provider_version: str = Field(min_length=1)
    query: str = Field(min_length=1)
    filters: RetrievalFilters = Field(default_factory=RetrievalFilters)
    embedding_model: str = Field(min_length=1)
    embedding_version: str = Field(min_length=1)
    chunks: list[RetrievalChunk] = Field(min_length=1)
    content_hash: str | None = None
    artifact_id: UUID | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def embedding(self) -> EmbeddingIdentity:
        return EmbeddingIdentity(model=self.embedding_model, version=self.embedding_version)

    @model_validator(mode="after")
    def validate_hash(self) -> RetrievalSnapshot:
        if not self.query.strip():
            raise ValueError("query must not be blank")
        # ``model_copy`` deliberately skips Pydantic validation; validate again
        # at this aggregate boundary so persisted snapshots cannot contain a
        # malformed nested chunk.
        chunks = [RetrievalChunk.model_validate(chunk.model_dump()) for chunk in self.chunks]
        if len({chunk.rank for chunk in chunks}) != len(chunks):
            raise ValueError("chunks must have unique ranks")
        digest = canonical_sha256(self.canonical_document())
        if self.content_hash is not None and self.content_hash != digest:
            raise ValueError("content_hash does not match canonical snapshot")
        object.__setattr__(self, "chunks", chunks)
        object.__setattr__(self, "content_hash", digest)
        return self

    def canonical_document(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "provider": self.provider,
            "provider_version": self.provider_version,
            "query": self.query,
            "filters": self.filters.model_dump(mode="python"),
            "embedding_model": self.embedding_model,
            "embedding_version": self.embedding_version,
            "chunks": [chunk.model_dump(mode="python", by_alias=False) for chunk in self.chunks],
        }

    def canonical_json_bytes(self) -> bytes:
        return canonical_json_bytes(self.canonical_document())

    @property
    def results(self) -> list[RetrievalChunk]:
        """Provider-shaped alias retained for the HTTP adapter boundary."""
        return self.chunks

    @classmethod
    def from_canonical_json(cls, value: bytes) -> RetrievalSnapshot:
        return cls.model_validate(json.loads(value))

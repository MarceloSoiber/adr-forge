"""HTTP adapter for creating immutable, replayable retrieval snapshots."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator

from adr_forge.api.problem_details import ProblemDetails
from adr_forge.artifacts.repository import ArtifactRepository
from adr_forge.artifacts.store import ArtifactStore
from adr_forge.retrieval.knowledge_hub import KnowledgeHubProvider
from adr_forge.retrieval.models import (
    RetrievalFilters as DomainRetrievalFilters,
)
from adr_forge.retrieval.models import (
    RetrievalSnapshot as DomainRetrievalSnapshot,
)
from adr_forge.retrieval.repository import RetrievalSnapshotRepository
from adr_forge.retrieval.service import RetrievalService
from adr_forge.retrieval.snapshot_provider import SnapshotRetrievalProvider
from adr_forge.shared.errors import PreconditionFailedError, ValidationError

PROBLEM = {
    "content": {
        "application/problem+json": {
            "schema": ProblemDetails.model_json_schema(),
        }
    }
}


class RetrievalFilters(BaseModel):
    """The public filter shape, deliberately excluding provider-only switches."""

    model_config = ConfigDict(extra="forbid")

    limit: int = Field(default=8, ge=1, le=50)
    category_ids: list[Annotated[int, Field(ge=1)]] | None = None
    tag_ids: list[Annotated[int, Field(ge=1)]] | None = None
    project_ids: list[Annotated[int, Field(ge=1)]] | None = None
    min_score: float | None = Field(default=None, ge=0, le=1)


class CreateRetrievalSnapshotRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Literal["knowledge_hub", "fixture"]
    query: str = Field(min_length=1, max_length=10_000)
    filters: RetrievalFilters
    fixture_id: str | None = Field(default=None, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$")

    @model_validator(mode="after")
    def validate_provider_options(self) -> CreateRetrievalSnapshotRequest:
        if self.provider == "fixture" and self.fixture_id is None:
            raise ValueError("fixture_id is required when provider is fixture")
        if self.provider == "knowledge_hub" and self.fixture_id is not None:
            raise ValueError("fixture_id is only valid when provider is fixture")
        return self


class RetrievalSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    schema_version: str
    provider: Literal["knowledge_hub", "fixture"]
    provider_version: str
    query: str
    filters: RetrievalFilters
    embedding_model: str
    embedding_version: str
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    artifact_id: UUID
    created_at: datetime


router = APIRouter(prefix="/api/v1", tags=["retrieval"])


def _filters(value: RetrievalFilters) -> DomainRetrievalFilters:
    return DomainRetrievalFilters(**value.model_dump(), include_match_reasons=True)


async def _retrieve(
    request: Request, command: CreateRetrievalSnapshotRequest, filters: DomainRetrievalFilters
) -> DomainRetrievalSnapshot:
    if command.provider == "knowledge_hub":
        if request.app.state.settings.knowledge_hub_token is None:
            raise PreconditionFailedError("Knowledge Hub is not configured.")
        return await KnowledgeHubProvider(request.app.state.settings).retrieve(
            command.query, filters=filters
        )

    # Fixture identities are resolved by the composition root/test harness; the
    # request can never select a filesystem path.
    fixtures = getattr(request.app.state, "retrieval_fixture_providers", {})
    configured = fixtures.get(command.fixture_id)
    if configured is None:
        raise PreconditionFailedError("Requested retrieval fixture is not configured.")
    if isinstance(configured, DomainRetrievalSnapshot):
        configured = SnapshotRetrievalProvider(configured)
    if not isinstance(configured, SnapshotRetrievalProvider):
        raise PreconditionFailedError("Requested retrieval fixture is invalid.")
    snapshot = await configured.retrieve(command.query, filters=filters)
    if snapshot.filters != filters:
        raise ValidationError("Requested filters do not match the frozen fixture.")
    return snapshot


def _response(snapshot: DomainRetrievalSnapshot) -> dict[str, object]:
    if snapshot.artifact_id is None or snapshot.content_hash is None:
        raise RuntimeError("retrieval snapshot was not persisted")
    return {
        "id": snapshot.id,
        "schema_version": snapshot.schema_version,
        "provider": snapshot.provider,
        "provider_version": snapshot.provider_version,
        "query": snapshot.query,
        "filters": snapshot.filters.model_dump(exclude={"include_match_reasons"}),
        "embedding_model": snapshot.embedding_model,
        "embedding_version": snapshot.embedding_version,
        "content_hash": snapshot.content_hash,
        "artifact_id": snapshot.artifact_id,
        "created_at": snapshot.created_at,
    }


@router.post(
    "/retrieval-snapshots",
    response_model=RetrievalSnapshot,
    status_code=201,
    operation_id="createRetrievalSnapshot",
    responses={
        409: PROBLEM,
        422: PROBLEM,
        503: PROBLEM,
    },
)
async def create_retrieval_snapshot(
    command: CreateRetrievalSnapshotRequest, request: Request
) -> dict[str, object]:
    filters = _filters(command.filters)
    snapshot = await _retrieve(request, command, filters)
    service = RetrievalService(
        RetrievalSnapshotRepository(request.app.state.session_factory),
        ArtifactRepository(request.app.state.session_factory),
        ArtifactStore(request.app.state.settings.artifact_root),
    )
    return _response(await service.freeze(snapshot))

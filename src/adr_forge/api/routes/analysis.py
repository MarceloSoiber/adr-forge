"""Phase 3 HTTP contract surface for scenario analysis."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse, Response, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from adr_forge.artifacts.repository import ArtifactRepository
from adr_forge.artifacts.store import ArtifactStore
from adr_forge.decisions.rendering import render_markdown
from adr_forge.decisions.repair import repair_adr_json
from adr_forge.decisions.schemas import ADRDraft as DomainADRDraft
from adr_forge.decisions.schemas import (
    ADRStatus,
    Alternative,
    Assumption,
    RationaleLink,
    ReviewTrigger,
    Risk,
    UnresolvedQuestion,
)
from adr_forge.decisions.service import DecisionService
from adr_forge.experiments.run_models import AnalysisRun as DomainAnalysisRun
from adr_forge.experiments.run_models import RunStatus
from adr_forge.experiments.run_repository import RunRepository
from adr_forge.scenarios.clarification import ClarificationAnswer, ClarificationAnswerReference
from adr_forge.scenarios.models import DecisionCategory
from adr_forge.scenarios.repository import ScenarioRepository
from adr_forge.scenarios.service import CreateRevisionInput, CreateScenarioInput, ScenarioService
from adr_forge.shared.errors import (
    ConflictError,
    NotFoundError,
    StaleRevisionError,
    ValidationError,
)
from adr_forge.shared.hashing import canonical_sha256
from adr_forge.strategies.configuration import configured_registry
from adr_forge.strategies.runtime import build_runtime
from adr_forge.system.progress import CancellationToken


class Problem(BaseModel):
    """OpenAPI component for RFC 9457 error responses."""

    type: str
    title: str
    status: int
    detail: str | None = None
    code: str | None = None
    request_id: str | None = None


PROBLEM = {
    "model": Problem,
    "content": {"application/problem+json": {"schema": {"$ref": "#/components/schemas/Problem"}}},
}
ExportFormat = Literal["markdown", "json"]


class CreateScenarioRequest(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    language: str = Field(json_schema_extra={"const": "pt-BR"})
    problem: str = Field(min_length=20, max_length=20_000)
    facts: list[str] = Field(default_factory=list, max_length=50)
    constraints: list[str] = Field(default_factory=list, max_length=50)
    desired_qualities: list[str] = Field(default_factory=list, max_length=20)
    candidate_alternatives: list[str] = Field(default_factory=list, max_length=20)


class ScenarioRevision(BaseModel):
    id: UUID
    scenario_id: UUID
    revision_number: int = Field(ge=1)
    problem: str
    facts: list[str]
    constraints: list[str]
    desired_qualities: list[str]
    candidate_alternatives: list[str]
    clarification_answers: list[ClarificationAnswer]
    categories: list[DecisionCategory]
    content_hash: str
    created_at: datetime


class ScenarioResponse(BaseModel):
    id: UUID
    title: str
    language: str
    current_revision: ScenarioRevision


class CreateRevisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_revision_number: int = Field(ge=1)
    clarification_answers: list[ClarificationAnswerReference] = Field(min_length=1, max_length=3)


class CreateAnalysisRunRequest(BaseModel):
    scenario_revision_id: UUID
    strategy_id: str
    strategy_version: str
    retrieval_snapshot_id: UUID | None = None
    experiment_id: UUID | None = None


class ValidationFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    path: str
    severity: Literal["error", "warning"]
    message: str = Field(max_length=2_000)


class OutputValidationAttempt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attempt: Literal["original", "repaired"]
    output_artifact_id: UUID
    artifact_id: UUID | None = None
    parse_succeeded: bool
    schema_version: str | None = None
    findings: list[ValidationFinding]


class AnalysisRun(BaseModel):
    id: UUID
    scenario_revision_id: UUID
    strategy_id: str
    strategy_version: str
    retrieval_snapshot_id: UUID | None = None
    experiment_id: UUID | None = None
    scenario_content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    strategy_configuration_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    generation_config_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    status: RunStatus
    stage: str
    progress_percent: int | None = Field(default=None, ge=0, le=100)
    progress_sequence: int = Field(ge=0)
    validation_attempts: list[OutputValidationAttempt] = Field(max_length=2)
    raw_output_artifact_id: UUID | None = None
    repaired_output_artifact_id: UUID | None = None
    adr_draft_id: UUID | None = None
    failure_code: str | None = None
    failure_detail: str | None = Field(default=None, max_length=2000)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    latency_ms: int | None = Field(default=None, ge=0)
    peak_vram_mb: int | None = Field(default=None, ge=0)
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class ProgressEvent(BaseModel):
    run_id: UUID
    status: RunStatus
    stage: str
    progress_percent: int | None = Field(default=None, ge=0, le=100)
    progress_sequence: int = Field(ge=0)
    failure_code: str | None = None
    failure_detail: str | None = Field(default=None, max_length=2000)
    updated_at: datetime


class AdrDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    analysis_run_id: UUID
    schema_version: str
    title: str = Field(min_length=3, max_length=200)
    status: ADRStatus
    context: list[str] = Field(min_length=1)
    facts: list[str]
    assumptions: list[Assumption]
    unresolved_questions: list[UnresolvedQuestion] = Field(max_length=3)
    constraints: list[str]
    alternatives: list[Alternative]
    decision: str | None
    rationale: list[RationaleLink]
    positive_consequences: list[str]
    negative_consequences: list[str]
    risks: list[Risk]
    review_triggers: list[ReviewTrigger]
    confidence: float = Field(ge=0, le=1)
    reference_ids: list[str]
    created_at: datetime


router = APIRouter(prefix="/api/v1")


def _scenario_response(scenario: Any, revision: Any) -> dict[str, Any]:
    return {
        "id": scenario.id,
        "title": scenario.title,
        "language": scenario.language,
        "current_revision": {
            **revision.model_dump(mode="json"),
            "content_hash": revision.content_hash,
        },
    }


def _run_response(run: dict[str, Any]) -> dict[str, Any]:
    validation_attempts = [
        {
            "attempt": attempt["attempt"],
            "output_artifact_id": attempt.get("output_artifact_id", attempt.get("artifact_id")),
            "artifact_id": attempt.get("artifact_id", attempt.get("output_artifact_id")),
            "parse_succeeded": attempt["parse_succeeded"],
            "schema_version": attempt.get("schema_version"),
            "findings": attempt.get("findings", []),
        }
        for attempt in run.get("validation_attempts", [])
    ]
    return {
        **run,
        "id": str(run["id"]),
        "scenario_revision_id": str(run["scenario_revision_id"]),
        "validation_attempts": validation_attempts,
    }


async def _run_repository(request: Request) -> RunRepository:
    return RunRepository(request.app.state.session_factory)


@router.post(
    "/scenarios",
    response_model=ScenarioResponse,
    status_code=201,
    operation_id="createScenario",
    responses={422: PROBLEM},
)
async def create_scenario(command: CreateScenarioRequest, request: Request) -> dict[str, Any]:
    service = ScenarioService(ScenarioRepository(request.app.state.session_factory))
    scenario, revision = await service.create(
        CreateScenarioInput.model_validate(command.model_dump())
    )
    return _scenario_response(scenario, revision)


@router.get(
    "/scenarios/{scenarioId}",
    response_model=ScenarioResponse,
    operation_id="getScenario",
    responses={404: PROBLEM},
)
async def get_scenario(scenarioId: UUID, request: Request) -> dict[str, Any]:
    service = ScenarioService(ScenarioRepository(request.app.state.session_factory))
    scenario, revision = await service.get_current(scenarioId)
    return _scenario_response(scenario, revision)


@router.post(
    "/scenarios/{scenarioId}/revisions",
    response_model=ScenarioRevision,
    status_code=201,
    operation_id="createScenarioRevision",
    responses={404: PROBLEM, 409: PROBLEM, 422: PROBLEM},
)
async def create_scenario_revision(
    scenarioId: UUID, command: CreateRevisionRequest, request: Request
) -> dict[str, Any]:
    try:
        revision_command = CreateRevisionInput.model_validate(command.model_dump())
    except ValueError as error:
        raise ValidationError(str(error)) from error
    scenarios = ScenarioRepository(request.app.state.session_factory)
    service = ScenarioService(scenarios)
    scenario, base = await service.get_current(scenarioId)
    if base.revision_number != revision_command.base_revision_number:
        raise StaleRevisionError("Reload the scenario and deliberately rebase answers.")
    runs = await _run_repository(request)
    snapshots: list[ClarificationAnswer] = []
    for answer in revision_command.clarification_answers:
        run = await runs.get(str(answer.source_run_id))
        if run is None:
            raise NotFoundError("Source analysis run not found.")
        if str(run["scenario_revision_id"]) != str(base.id):
            raise ValidationError("Source run does not belong to the base scenario revision.")
        if run["status"] != RunStatus.NEEDS_CLARIFICATION.value:
            raise ValidationError("Source run is not awaiting clarification.")
        adr = await runs.get_adr(str(answer.source_run_id))
        if adr is None or adr.get("status") != "provisional":
            raise ValidationError("Source run has no provisional ADR.")
        questions = adr.get("unresolved_questions", [])
        question = next((item for item in questions if item.get("id") == answer.question_id), None)
        if question is None:
            raise ValidationError("Clarification question does not belong to the source ADR.")
        snapshots.append(
            ClarificationAnswer(
                question_id=answer.question_id,
                answer=answer.answer,
                source_run_id=answer.source_run_id,
                question=question["question"],
                impact=question["impact"],
            )
        )
    revision = await service.create_clarification_revision(scenario.id, revision_command, snapshots)
    return {**revision.model_dump(mode="json"), "content_hash": revision.content_hash}


@router.post(
    "/analysis-runs",
    response_model=AnalysisRun,
    status_code=202,
    operation_id="createAnalysisRun",
    responses={409: PROBLEM, 422: PROBLEM},
)
async def create_analysis_run(
    command: CreateAnalysisRunRequest, request: Request
) -> dict[str, Any]:
    scenarios = ScenarioRepository(request.app.state.session_factory)
    revision = await scenarios.get_revision(str(command.scenario_revision_id))
    if revision is None:
        raise ConflictError("Scenario revision not found")
    settings = request.app.state.settings
    registry = configured_registry(settings)
    availability = registry.available_for(
        command.strategy_id,
        command.strategy_version,
        snapshot_id=command.retrieval_snapshot_id,
    )
    if not availability.available:
        raise ConflictError(availability.unavailable_reason or "Strategy is unavailable")
    selected = registry.get(command.strategy_id, command.strategy_version)
    assert selected is not None
    repository = await _run_repository(request)
    run = DomainAnalysisRun(
        scenario_revision_id=revision.id,
        strategy_id=command.strategy_id,
        strategy_version=command.strategy_version,
        retrieval_snapshot_id=command.retrieval_snapshot_id,
        experiment_id=command.experiment_id,
        scenario_content_hash=revision.content_hash,
        strategy_configuration_hash=canonical_sha256(selected.model_dump(mode="json")),
        generation_config_hash=selected.generation_config_hash,
    )
    await repository.add({**run.model_dump(mode="python"), "validation_attempts": []})
    waiting = run.transition(
        RunStatus.WAITING_RESOURCES, stage="aguardando recursos", progress_percent=0
    )
    await repository.transition(
        {**waiting.model_dump(mode="python"), "validation_attempts": []},
        run.progress_sequence,
    )
    running = waiting.transition(RunStatus.RUNNING, stage="gerando ADR", progress_percent=25)
    await repository.transition(
        {**running.model_dump(mode="python"), "validation_attempts": []},
        waiting.progress_sequence,
    )

    now = datetime.now(UTC)
    try:
        generated = await DecisionService().execute(
            build_runtime(selected, settings),
            revision,
            run.id,
            CancellationToken(),
            repair=repair_adr_json,
        )
    except RuntimeError:
        failed = running.transition(
            RunStatus.FAILED,
            stage="falha na inferência",
            progress_percent=100,
            failure_code="inference_failed",
        )
        await repository.transition(
            {**failed.model_dump(mode="python"), "validation_attempts": []},
            running.progress_sequence,
        )
        persisted = await repository.get(str(run.id))
        assert persisted is not None
        return _run_response(persisted)
    original_parsed = generated.parsed.original
    raw_output = generated.generation.raw_output.encode("utf-8")
    sha256, size_bytes, relative_path = await ArtifactStore(
        request.app.state.settings.artifact_root
    ).put_bytes(raw_output)
    artifact_id = await ArtifactRepository(request.app.state.session_factory).create_raw_output(
        sha256=sha256, relative_path=relative_path, size_bytes=size_bytes, created_at=now
    )
    await ArtifactRepository(request.app.state.session_factory).reference(
        artifact_id, "analysis_run", run.id
    )
    original_attempt = {
        "attempt": "original",
        "artifact_id": artifact_id,
        "parse_succeeded": original_parsed.parse_succeeded,
        "schema_version": (
            original_parsed.draft.schema_version if original_parsed.draft is not None else None
        ),
        "findings": [asdict(finding) for finding in original_parsed.findings],
        "created_at": now,
    }
    await repository.add_validation_attempt(str(run.id), original_attempt)

    attempts = [original_attempt]
    parsed = original_parsed
    repaired_artifact_id: str | None = None
    if generated.parsed.repaired is not None and generated.parsed.repaired_output is not None:
        repaired_output = generated.parsed.repaired_output.encode("utf-8")
        repaired_sha256, repaired_size, repaired_path = await ArtifactStore(
            request.app.state.settings.artifact_root
        ).put_bytes(repaired_output)
        repaired_artifact_id = await ArtifactRepository(
            request.app.state.session_factory
        ).create_raw_output(
            sha256=repaired_sha256,
            relative_path=repaired_path,
            size_bytes=repaired_size,
            created_at=now,
        )
        await ArtifactRepository(request.app.state.session_factory).reference(
            repaired_artifact_id, "analysis_run", run.id
        )
        repaired = generated.parsed.repaired
        repaired_attempt = {
            "attempt": "repaired",
            "artifact_id": repaired_artifact_id,
            "parse_succeeded": repaired.parse_succeeded,
            "schema_version": repaired.draft.schema_version if repaired.draft is not None else None,
            "findings": [asdict(finding) for finding in repaired.findings],
            "created_at": now,
        }
        await repository.add_validation_attempt(str(run.id), repaired_attempt)
        attempts.append(repaired_attempt)
        if repaired.draft is not None and not any(
            finding.severity == "error" for finding in repaired.findings
        ):
            parsed = repaired
    if parsed.draft is None or any(finding.severity == "error" for finding in parsed.findings):
        detail = "; ".join(finding.message for finding in parsed.findings[:3])
        invalid = running.transition(
            RunStatus.INVALID_OUTPUT,
            stage="saída inválida",
            progress_percent=100,
            failure_code="invalid_output",
            failure_detail=detail or "A resposta não segue o formato ADR esperado.",
            raw_output_artifact_id=UUID(artifact_id),
            repaired_output_artifact_id=(
                UUID(repaired_artifact_id) if repaired_artifact_id is not None else None
            ),
        )
        await repository.transition(
            {**invalid.model_dump(mode="python"), "validation_attempts": attempts},
            running.progress_sequence,
        )
        persisted = await repository.get(str(run.id))
        assert persisted is not None
        return _run_response(persisted)
    adr = parsed.draft
    terminal_status = (
        RunStatus.NEEDS_CLARIFICATION if adr.status.value == "provisional" else RunStatus.COMPLETED
    )
    terminal_stage = (
        "aguardando esclarecimentos"
        if terminal_status == RunStatus.NEEDS_CLARIFICATION
        else "concluído"
    )
    completed = running.transition(
        terminal_status,
        stage=terminal_stage,
        progress_percent=100,
        adr_draft_id=adr.id,
        raw_output_artifact_id=UUID(artifact_id),
        repaired_output_artifact_id=(
            UUID(repaired_artifact_id) if repaired_artifact_id is not None else None
        ),
        input_tokens=generated.generation.telemetry.input_tokens,
        output_tokens=generated.generation.telemetry.output_tokens,
        latency_ms=generated.generation.telemetry.latency_ms,
        peak_vram_mb=generated.generation.telemetry.peak_vram_mb,
    )
    completed_values = {**completed.model_dump(mode="python"), "validation_attempts": attempts}
    if not await repository.transition(completed_values, running.progress_sequence):
        raise ConflictError("Run changed while it was being completed")
    await repository.save_adr(str(run.id), adr.model_dump(mode="python"))
    persisted = await repository.get(str(run.id))
    if persisted is None:
        raise NotFoundError("Analysis run was not persisted")
    persisted["validation_attempts"] = [
        {k: v for k, v in attempt.items() if k != "created_at"} for attempt in attempts
    ]
    return _run_response(persisted)


@router.get(
    "/analysis-runs/{runId}",
    response_model=AnalysisRun,
    operation_id="getAnalysisRun",
    responses={404: PROBLEM},
)
async def get_analysis_run(runId: UUID, request: Request) -> dict[str, Any]:
    found = await (await _run_repository(request)).get(str(runId))
    if found is None:
        raise NotFoundError("Analysis run not found")
    return _run_response(found)


@router.get(
    "/analysis-runs/{runId}/output",
    operation_id="getRunOutput",
    response_class=PlainTextResponse,
    responses={404: PROBLEM, 409: PROBLEM},
)
async def get_run_output(runId: UUID, request: Request) -> PlainTextResponse:
    """Return the captured local model response without logging its content."""
    run = await (await _run_repository(request)).get(str(runId))
    if run is None:
        raise NotFoundError("Analysis run not found")
    artifact_id = run.get("raw_output_artifact_id")
    if artifact_id is None:
        raise ConflictError("Model output is not available for this run")
    artifact = await ArtifactRepository(request.app.state.session_factory).get_raw_output(
        str(artifact_id)
    )
    if artifact is None:
        raise NotFoundError("Model output artifact not found")
    content = await ArtifactStore(request.app.state.settings.artifact_root).read_bytes(
        artifact.relative_path
    )
    return PlainTextResponse(content.decode("utf-8"), media_type="text/plain")


@router.get(
    "/analysis-runs/{runId}/events",
    operation_id="streamAnalysisRunEvents",
    responses={
        200: {"content": {"text/event-stream": {"schema": {"type": "string"}}}},
        404: PROBLEM,
    },
)
async def stream_analysis_run_events(runId: UUID, request: Request) -> Response:
    repository = await _run_repository(request)
    if await repository.get(str(runId)) is None:
        raise NotFoundError("Analysis run not found")
    publisher = request.app.state.analysis_executor.progress

    async def event_stream() -> AsyncIterator[str]:
        """Project durable run state onto a best-effort in-process SSE stream.

        Subscribe before loading the snapshot: any transition committed during the
        database read wakes the stream, which then replays durable events newer
        than the emitted snapshot.  The database remains the source of truth.
        """
        loop = asyncio.get_running_loop()
        notifications: asyncio.Queue[None] = asyncio.Queue(maxsize=1)

        def notify(_: object) -> None:
            def enqueue() -> None:
                if notifications.empty():
                    notifications.put_nowait(None)

            loop.call_soon_threadsafe(enqueue)

        unsubscribe = publisher.subscribe(str(runId), notify)
        try:
            snapshot = await repository.get(str(runId))
            if snapshot is None:
                return
            last_sequence = snapshot["progress_sequence"]
            yield _sse_progress(runId, snapshot)
            if snapshot["status"] in _TERMINAL_RUN_STATUSES:
                return

            while True:
                try:
                    await asyncio.wait_for(notifications.get(), timeout=15)
                except TimeoutError:
                    if await request.is_disconnected():
                        return
                    yield ": keepalive\n\n"
                    continue
                for event in await repository.list_events(str(runId)):
                    if event["progress_sequence"] <= last_sequence:
                        continue
                    last_sequence = event["progress_sequence"]
                    yield _sse_progress(runId, event)
                    if event["status"] in _TERMINAL_RUN_STATUSES:
                        return
        finally:
            unsubscribe()

    return StreamingResponse(event_stream(), media_type="text/event-stream")


_TERMINAL_RUN_STATUSES = frozenset(
    status.value
    for status in (
        RunStatus.COMPLETED,
        RunStatus.NEEDS_CLARIFICATION,
        RunStatus.INVALID_OUTPUT,
        RunStatus.FAILED,
        RunStatus.CANCELLED,
        RunStatus.INTERRUPTED,
    )
)


def _sse_progress(run_id: UUID, event: dict[str, Any]) -> str:
    return (
        "event: progress\ndata: "
        + json.dumps({"run_id": str(run_id), **event}, default=str)
        + "\n\n"
    )


@router.post(
    "/analysis-runs/{runId}/cancel",
    response_model=AnalysisRun,
    status_code=202,
    operation_id="cancelAnalysisRun",
    responses={404: PROBLEM, 409: PROBLEM},
)
async def cancel_analysis_run(runId: UUID, request: Request) -> dict[str, Any]:
    repository = await _run_repository(request)
    current = await repository.get(str(runId))
    if current is None:
        raise NotFoundError("Analysis run not found")
    cancellable = {RunStatus.PENDING, RunStatus.WAITING_RESOURCES, RunStatus.RUNNING}
    if current["status"] not in {status.value for status in cancellable}:
        raise ConflictError("Terminal analysis runs cannot be cancelled")
    domain_values = {
        field: current[field] for field in DomainAnalysisRun.model_fields if field in current
    }
    domain_run = DomainAnalysisRun.model_validate(domain_values)
    cancelled = domain_run.transition(RunStatus.CANCELLED, stage="cancelado", progress_percent=100)
    candidate = {
        **cancelled.model_dump(mode="python"),
        "validation_attempts": current["validation_attempts"],
    }
    if not await repository.transition(candidate, domain_run.progress_sequence):
        raise ConflictError("Run changed while cancellation was requested")
    persisted = await repository.get(str(runId))
    assert persisted is not None
    return _run_response(persisted)


@router.get(
    "/analysis-runs/{runId}/adr",
    response_model=AdrDraft,
    operation_id="getRunAdr",
    responses={404: PROBLEM, 409: PROBLEM},
)
async def get_run_adr(runId: UUID, request: Request) -> dict[str, Any]:
    found = await (await _run_repository(request)).get_adr(str(runId))
    if found is None:
        raise NotFoundError("ADR not found")
    return found


@router.get(
    "/analysis-runs/{runId}/export",
    operation_id="exportRunAdr",
    summary="Export a validated ADR",
    description=(
        "Exports the validated ADR as a Markdown attachment or as the structured JSON document."
    ),
    response_class=Response,
    responses={
        200: {
            "description": "ADR export.",
            "headers": {
                "Content-Disposition": {
                    "description": "Safe local attachment filename for Markdown exports.",
                    "schema": {"type": "string"},
                }
            },
            "content": {
                "text/markdown": {"schema": {"type": "string"}},
                "application/json": {"schema": {"$ref": "#/components/schemas/AdrDraft"}},
            },
        },
        404: PROBLEM,
        409: PROBLEM,
    },
)
async def export_run_adr(
    runId: UUID, request: Request, format: ExportFormat = "markdown"
) -> Response:
    adr = await get_run_adr(runId, request)
    if format == "json":
        return Response(
            AdrDraft.model_validate(adr).model_dump_json(), media_type="application/json"
        )
    return Response(
        render_markdown(DomainADRDraft.model_validate(adr)),
        media_type="text/markdown",
        headers={"Content-Disposition": "attachment; filename=adr.md"},
    )

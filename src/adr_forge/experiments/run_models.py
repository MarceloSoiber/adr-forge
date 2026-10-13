"""Immutable state machine for one analysis execution."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RunStatus(StrEnum):
    PENDING = "pending"
    WAITING_RESOURCES = "waiting_resources"
    RUNNING = "running"
    COMPLETED = "completed"
    NEEDS_CLARIFICATION = "needs_clarification"
    INVALID_OUTPUT = "invalid_output"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"


TERMINAL_STATUSES = frozenset(
    {
        RunStatus.COMPLETED,
        RunStatus.NEEDS_CLARIFICATION,
        RunStatus.INVALID_OUTPUT,
        RunStatus.FAILED,
        RunStatus.CANCELLED,
        RunStatus.INTERRUPTED,
    }
)
_TRANSITIONS = {
    RunStatus.PENDING: {RunStatus.WAITING_RESOURCES, RunStatus.CANCELLED, RunStatus.FAILED},
    RunStatus.WAITING_RESOURCES: {RunStatus.RUNNING, RunStatus.CANCELLED, RunStatus.FAILED},
    RunStatus.RUNNING: TERMINAL_STATUSES,
}


class AnalysisRun(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID = Field(default_factory=uuid4)
    scenario_revision_id: UUID
    strategy_id: str
    strategy_version: str
    status: RunStatus = RunStatus.PENDING
    stage: str = "pending"
    progress_percent: int | None = Field(default=None, ge=0, le=100)
    progress_sequence: int = Field(default=0, ge=0)
    raw_output_artifact_id: UUID | None = None
    repaired_output_artifact_id: UUID | None = None
    adr_draft_id: UUID | None = None
    failure_code: str | None = None
    failure_detail: str | None = Field(default=None, max_length=2000)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    latency_ms: int | None = Field(default=None, ge=0)
    peak_vram_mb: int | None = Field(default=None, ge=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    finished_at: datetime | None = None

    @model_validator(mode="after")
    def terminal_runs_are_finished(self) -> AnalysisRun:
        if self.status in TERMINAL_STATUSES and self.finished_at is None:
            raise ValueError("terminal run requires finished_at")
        return self

    def transition(self, status: RunStatus, *, stage: str, **updates: object) -> AnalysisRun:
        if status not in _TRANSITIONS.get(self.status, set()):
            raise ValueError(f"illegal transition: {self.status} -> {status}")
        now = datetime.now(UTC)
        values = self.model_dump(mode="python")
        values.update(updates, status=status, stage=stage, updated_at=now)
        values["progress_sequence"] = self.progress_sequence + 1
        if status == RunStatus.RUNNING and self.started_at is None:
            values["started_at"] = now
        if status in TERMINAL_STATUSES:
            values["finished_at"] = now
        return AnalysisRun.model_validate(values)

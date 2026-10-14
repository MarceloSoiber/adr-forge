"""Immutable benchmark experiment aggregate and matrix accounting."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ExperimentStatus(StrEnum):
    DRAFT = "draft"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MatrixOutcome(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    EXCLUDED = "excluded"


ExperimentRunOutcome = MatrixOutcome


class FrozenMatrixCell(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    scenario_revision_id: UUID
    scenario_content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    strategy_id: str
    strategy_version: str
    strategy_configuration_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    generation_config_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    retrieval_snapshot_id: UUID | None = None


class ExperimentAccounting(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    completed: int
    failed: int
    excluded: int
    missing: int
    status: ExperimentStatus

    def __getitem__(self, key: str) -> int | ExperimentStatus:
        return getattr(self, key)


class Experiment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=3, max_length=200)
    status: ExperimentStatus = ExperimentStatus.DRAFT
    dataset_version_id: UUID | None = None
    rubric_version_id: UUID
    code_revision: str = Field(min_length=1, max_length=200)
    configuration_artifact_id: UUID | None = None
    matrix: list[FrozenMatrixCell] = Field(default_factory=list)
    expected_run_count: int | None = Field(default=None, ge=1)
    outcomes: list[MatrixOutcome] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    finished_at: datetime | None = None

    @model_validator(mode="after")
    def exact_matrix(self) -> Experiment:
        keys = {
            (cell.scenario_revision_id, cell.strategy_id, cell.strategy_version)
            for cell in self.matrix
        }
        if len(keys) != len(self.matrix):
            raise ValueError("experiment matrix cells must be unique")
        if self.matrix and self.expected_run_count not in {None, len(self.matrix)}:
            raise ValueError("expected_run_count must match the frozen matrix")
        if not self.matrix and self.expected_run_count is None:
            raise ValueError("experiment requires a frozen matrix")
        if (
            self.status
            in {
                ExperimentStatus.COMPLETED,
                ExperimentStatus.PARTIAL,
                ExperimentStatus.FAILED,
                ExperimentStatus.CANCELLED,
            }
            and self.finished_at is None
        ):
            raise ValueError("terminal experiment requires finished_at")
        return self

    def start(self) -> Experiment:
        return self.transition(ExperimentStatus.RUNNING)

    def record_outcome(self, outcome: MatrixOutcome) -> Experiment:
        if self.status in {
            ExperimentStatus.COMPLETED,
            ExperimentStatus.PARTIAL,
            ExperimentStatus.FAILED,
            ExperimentStatus.CANCELLED,
        }:
            raise ValueError("terminal experiments are immutable")
        if len(self.outcomes) >= self.run_count:
            raise ValueError("all expected cells are already accounted for")
        return self.model_copy(update={"outcomes": [*self.outcomes, outcome]})

    def finish(self) -> Experiment:
        status = (
            ExperimentStatus.COMPLETED
            if self.accounting().missing == 0
            else ExperimentStatus.PARTIAL
        )
        return self.transition(status)

    @property
    def run_count(self) -> int:
        return len(self.matrix) if self.matrix else self.expected_run_count or 0

    def transition(self, status: ExperimentStatus) -> Experiment:
        if self.status in {
            ExperimentStatus.COMPLETED,
            ExperimentStatus.PARTIAL,
            ExperimentStatus.FAILED,
            ExperimentStatus.CANCELLED,
        }:
            raise ValueError("terminal experiments are immutable")
        now = datetime.now(UTC)
        return self.model_copy(
            update={
                "status": status,
                "started_at": self.started_at or now
                if status == ExperimentStatus.RUNNING
                else self.started_at,
                "finished_at": now
                if status
                in {
                    ExperimentStatus.COMPLETED,
                    ExperimentStatus.PARTIAL,
                    ExperimentStatus.FAILED,
                    ExperimentStatus.CANCELLED,
                }
                else None,
            }
        )

    def accounting(self, outcomes: list[MatrixOutcome | str] | None = None) -> ExperimentAccounting:
        values = [MatrixOutcome(item) for item in (self.outcomes if outcomes is None else outcomes)]
        completed = values.count(MatrixOutcome.COMPLETED)
        failed = values.count(MatrixOutcome.FAILED)
        excluded = values.count(MatrixOutcome.EXCLUDED)
        missing = self.run_count - len(values)
        if missing < 0:
            raise ValueError("matrix has more outcomes than expected cells")
        status = ExperimentStatus.COMPLETED if missing == 0 else ExperimentStatus.PARTIAL
        return ExperimentAccounting(
            completed=completed, failed=failed, excluded=excluded, missing=missing, status=status
        )

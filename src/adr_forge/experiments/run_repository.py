"""SQLite persistence for analysis run snapshots and ADR payloads."""

from __future__ import annotations

import json
from typing import Any, cast

from sqlalchemy import text
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class RunRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def add(self, run: dict[str, Any]) -> None:
        values = dict(run)
        values["id"] = str(values["id"])
        values["scenario_revision_id"] = str(values["scenario_revision_id"])
        values["validation_attempts_json"] = json.dumps(
            values.pop("validation_attempts"), default=str
        )
        async with self._session_factory.begin() as session:
            await session.execute(
                text(
                    """INSERT INTO analysis_runs (id, scenario_revision_id, strategy_id,
                    strategy_version, status, stage, progress_percent, progress_sequence,
                    validation_attempts_json, input_tokens, output_tokens, latency_ms, peak_vram_mb,
                    created_at, updated_at)
                    VALUES (:id, :scenario_revision_id, :strategy_id, :strategy_version,
                    :status, :stage, :progress_percent, :progress_sequence,
                    :validation_attempts_json, :input_tokens, :output_tokens, :latency_ms,
                    :peak_vram_mb, :created_at, :updated_at)"""
                ),
                values,
            )
            await session.execute(
                text(
                    """INSERT INTO analysis_run_events (run_id, progress_sequence, status, stage,
                    progress_percent, updated_at)
                    VALUES (:id, :progress_sequence, :status, :stage,
                    :progress_percent, :updated_at)"""
                ),
                values,
            )

    async def get(self, run_id: str) -> dict[str, Any] | None:
        async with self._session_factory() as session:
            row = (
                (
                    await session.execute(
                        text("SELECT * FROM analysis_runs WHERE id = :id"), {"id": run_id}
                    )
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            return None
        result = dict(row)
        result["validation_attempts"] = json.loads(result.pop("validation_attempts_json"))
        return result

    async def list_non_terminal(self) -> list[dict[str, Any]]:
        """Return runs that must be closed during application startup recovery."""
        terminal = (
            "completed",
            "needs_clarification",
            "invalid_output",
            "failed",
            "cancelled",
            "interrupted",
        )
        async with self._session_factory() as session:
            rows = (
                (
                    await session.execute(
                        text(
                            "SELECT * FROM analysis_runs "
                            "WHERE status NOT IN (:completed, :needs_clarification, "
                            ":invalid_output, :failed, :cancelled, :interrupted) "
                            "ORDER BY created_at"
                        ),
                        dict(
                            zip(
                                (
                                    "completed",
                                    "needs_clarification",
                                    "invalid_output",
                                    "failed",
                                    "cancelled",
                                    "interrupted",
                                ),
                                terminal,
                                strict=True,
                            )
                        ),
                    )
                )
                .mappings()
                .all()
            )
        result = [dict(row) for row in rows]
        for run in result:
            run["validation_attempts"] = json.loads(run.pop("validation_attempts_json"))
        return result

    async def list_events(self, run_id: str) -> list[dict[str, Any]]:
        async with self._session_factory() as session:
            rows = (
                (
                    await session.execute(
                        text(
                            """SELECT run_id, progress_sequence, status, stage,
                            progress_percent, updated_at
                        FROM analysis_run_events WHERE run_id = :id ORDER BY progress_sequence"""
                        ),
                        {"id": run_id},
                    )
                )
                .mappings()
                .all()
            )
        return [dict(row) for row in rows]

    async def add_validation_attempt(self, run_id: str, attempt: dict[str, Any]) -> None:
        async with self._session_factory.begin() as session:
            await session.execute(
                text(
                    """INSERT INTO analysis_run_validation_attempts
                    (run_id, attempt, artifact_id, parse_succeeded, findings_json, created_at)
                    VALUES (:run_id, :attempt, :artifact_id, :parse_succeeded,
                    :findings_json, :created_at)"""
                ),
                {
                    "run_id": run_id,
                    "attempt": attempt["attempt"],
                    "artifact_id": attempt["artifact_id"],
                    "parse_succeeded": attempt["parse_succeeded"],
                    "findings_json": json.dumps(attempt.get("findings", [])),
                    "created_at": attempt["created_at"],
                },
            )

    async def transition(self, run: dict[str, Any], expected_sequence: int) -> bool:
        """Persist a new run snapshot and its replayable event in one transaction."""
        values = dict(run)
        values["id"] = str(values["id"])
        values["validation_attempts_json"] = json.dumps(
            values.pop("validation_attempts", []), default=str
        )
        async with self._session_factory.begin() as session:
            result = cast(
                CursorResult[Any],
                await session.execute(
                    text(
                        """UPDATE analysis_runs SET status = :status, stage = :stage,
                        progress_percent = :progress_percent,
                        progress_sequence = :progress_sequence,
                        validation_attempts_json = :validation_attempts_json,
                        updated_at = :updated_at,
                        started_at = :started_at, finished_at = :finished_at,
                        input_tokens = :input_tokens, output_tokens = :output_tokens,
                        latency_ms = :latency_ms, peak_vram_mb = :peak_vram_mb,
                        failure_code = :failure_code, failure_detail = :failure_detail
                        WHERE id = :id AND progress_sequence = :expected_sequence"""
                    ),
                    {**values, "expected_sequence": expected_sequence},
                ),
            )
            if result.rowcount != 1:
                return False
            await session.execute(
                text(
                    """INSERT INTO analysis_run_events (run_id, progress_sequence, status, stage,
                    progress_percent, updated_at)
                    VALUES (:id, :progress_sequence, :status, :stage,
                    :progress_percent, :updated_at)"""
                ),
                values,
            )
        return True

    async def save_adr(self, run_id: str, adr: dict[str, Any]) -> None:
        async with self._session_factory.begin() as session:
            await session.execute(
                text(
                    "INSERT INTO adr_drafts (id, analysis_run_id, payload_json, created_at) "
                    "VALUES (:id, :run_id, :payload, :created_at)"
                ),
                {
                    "id": str(adr["id"]),
                    "run_id": run_id,
                    "payload": json.dumps(adr, default=str),
                    "created_at": adr["created_at"],
                },
            )
            await session.execute(
                text("UPDATE analysis_runs SET adr_draft_id = :adr_id WHERE id = :id"),
                {"adr_id": str(adr["id"]), "id": run_id},
            )

    async def get_adr(self, run_id: str) -> dict[str, Any] | None:
        async with self._session_factory() as session:
            row = (
                await session.execute(
                    text("SELECT payload_json FROM adr_drafts WHERE analysis_run_id = :id"),
                    {"id": run_id},
                )
            ).scalar_one_or_none()
        return json.loads(row) if row else None

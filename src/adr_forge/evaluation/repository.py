"""SQLite persistence for append-only blind comparisons and evaluations."""

from __future__ import annotations

import json
from typing import Any, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from adr_forge.evaluation.models import CandidateRun, EvaluationResult, RubricVersion
from adr_forge.evaluation.service import Comparison, EvaluationConflict


class EvaluationRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def save_comparison(self, comparison: Comparison) -> None:
        """Store the label-to-run mapping once; it is never regenerated on reads."""
        async with self._session_factory.begin() as session:
            await session.execute(
                text("""INSERT INTO blind_comparisons
                    (id, rubric_version_id, rubric_json, current_evaluation_id, created_at)
                    VALUES (:id, :rubric_version_id, :rubric_json, NULL, CURRENT_TIMESTAMP)"""),
                {
                    "id": str(comparison.id),
                    "rubric_version_id": str(comparison.rubric.id),
                    "rubric_json": json.dumps(comparison.rubric.model_dump(mode="json")),
                },
            )
            for label, candidate in comparison._candidates:
                await session.execute(
                    text("""INSERT INTO comparison_candidates
                        (comparison_id, label, run_id, adr_json, strategy_id, strategy_version,
                         generation_config_hash, retrieval_snapshot_id)
                        VALUES (:comparison_id, :label, :run_id, :adr_json, :strategy_id,
                         :strategy_version, :generation_config_hash, :retrieval_snapshot_id)"""),
                    {
                        "comparison_id": str(comparison.id),
                        "label": label,
                        "run_id": str(candidate.run_id),
                        "adr_json": json.dumps(candidate.adr),
                        "strategy_id": candidate.strategy_id,
                        "strategy_version": candidate.strategy_version,
                        "generation_config_hash": candidate.generation_config_hash,
                        "retrieval_snapshot_id": str(candidate.retrieval_snapshot_id)
                        if candidate.retrieval_snapshot_id else None,
                    },
                )

    async def get_comparison(self, comparison_id: UUID) -> Comparison | None:
        async with self._session_factory() as session:
            header = (await session.execute(
                text("SELECT id, rubric_json FROM blind_comparisons WHERE id = :id"),
                {"id": str(comparison_id)},
            )).mappings().one_or_none()
            if header is None:
                return None
            candidates = (await session.execute(
                text("""SELECT label, run_id, adr_json, strategy_id, strategy_version,
                    generation_config_hash, retrieval_snapshot_id FROM comparison_candidates
                    WHERE comparison_id = :id ORDER BY label"""), {"id": str(comparison_id)}
            )).mappings().all()
            evaluations = (await session.execute(
                text("""SELECT id, comparison_id, rubric_version_id, evaluator_id, evaluator_type,
                    scores_json, preference, notes, supersedes_evaluation_id, submitted_at
                    FROM evaluation_results WHERE comparison_id = :id ORDER BY submitted_at, id"""),
                {"id": str(comparison_id)},
            )).mappings().all()

        # All candidate runs were validated when the comparison was created.  The
        # persisted aggregate deliberately retains only their immutable evidence.
        revision_id = UUID(int=0)
        restored_candidates = [
            (row["label"], CandidateRun(
                run_id=UUID(row["run_id"]), scenario_revision_id=revision_id,
                status="completed", adr=json.loads(row["adr_json"]),
                strategy_id=row["strategy_id"], strategy_version=row["strategy_version"],
                generation_config_hash=row["generation_config_hash"],
                retrieval_snapshot_id=UUID(row["retrieval_snapshot_id"])
                if row["retrieval_snapshot_id"] else None,
            ))
            for row in candidates
        ]
        history = [EvaluationResult.model_validate({
            **{key: value for key, value in dict(row).items() if key != "scores_json"},
            "scores": json.loads(row["scores_json"]),
        }) for row in evaluations]
        return Comparison.restore(
            identity=UUID(header["id"]), candidates=restored_candidates,
            rubric=RubricVersion.model_validate(json.loads(header["rubric_json"])), history=history,
        )

    async def append_evaluation(self, result: EvaluationResult) -> None:
        """Append an immutable result and atomically advance the comparison head."""
        try:
            async with self._session_factory.begin() as session:
                expected_head = str(result.supersedes_evaluation_id) if result.supersedes_evaluation_id else None
                condition = "current_evaluation_id IS NULL" if expected_head is None else "current_evaluation_id = :expected_head"
                advanced = cast(CursorResult[Any], await session.execute(
                    text(f"""UPDATE blind_comparisons SET current_evaluation_id = :evaluation_id
                        WHERE id = :comparison_id AND {condition}"""),
                    {"evaluation_id": str(result.id), "comparison_id": str(result.comparison_id), "expected_head": expected_head},
                ))
                if advanced.rowcount != 1:
                    raise EvaluationConflict("stale evaluation")
                await session.execute(
                    text("""INSERT INTO evaluation_results
                        (id, comparison_id, rubric_version_id, evaluator_id, evaluator_type,
                         scores_json, preference, notes, supersedes_evaluation_id, submitted_at)
                        VALUES (:id, :comparison_id, :rubric_version_id, :evaluator_id,
                         :evaluator_type, :scores_json, :preference, :notes,
                         :supersedes_evaluation_id, :submitted_at)"""),
                    {
                        "id": str(result.id), "comparison_id": str(result.comparison_id),
                        "rubric_version_id": str(result.rubric_version_id),
                        "evaluator_id": result.evaluator_id, "evaluator_type": result.evaluator_type.value,
                        "scores_json": json.dumps(result.scores), "preference": result.preference,
                        "notes": result.notes,
                        "supersedes_evaluation_id": str(result.supersedes_evaluation_id)
                        if result.supersedes_evaluation_id else None,
                        "submitted_at": result.submitted_at,
                    },
                )
        except IntegrityError as error:
            raise EvaluationConflict("evaluation conflict") from error

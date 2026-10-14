"""Transactional rules for blind human comparison, usable with an in-memory test store."""

from __future__ import annotations

from uuid import UUID

from adr_forge.evaluation.models import BlindComparison, EvaluationResult
from adr_forge.shared.errors import ConflictError, PreconditionFailedError, ValidationError


class BlindComparisonService:
    def __init__(self) -> None:
        self._comparisons: dict[UUID, BlindComparison] = {}
        self._evaluations: dict[UUID, EvaluationResult] = {}

    def create(self, comparison: BlindComparison) -> BlindComparison:
        self._comparisons[comparison.id] = comparison
        return comparison

    def get_blinded(self, comparison_id: UUID) -> dict[str, object]:
        return self._comparison(comparison_id).blinded_projection()

    def submit(self, result: EvaluationResult) -> EvaluationResult:
        comparison = self._comparison(result.comparison_id)
        if result.rubric_version_id != comparison.rubric.id:
            raise ValidationError("evaluation rubric does not match comparison")
        self._validate_result(comparison, result)
        current = comparison.current_evaluation_id
        if current is None and result.supersedes_evaluation_id is not None:
            raise ConflictError("initial evaluation cannot supersede another result")
        if current is not None and result.supersedes_evaluation_id != current:
            raise ConflictError("evaluation must explicitly supersede the current result")
        self._evaluations[result.id] = result
        self._comparisons[comparison.id] = comparison.model_copy(
            update={"current_evaluation_id": result.id}
        )
        return result

    def reveal(self, comparison_id: UUID) -> dict[str, object]:
        comparison = self._comparison(comparison_id)
        if comparison.current_evaluation_id is None:
            raise PreconditionFailedError(
                "Submit an immutable evaluation before revealing identities."
            )
        return {
            "comparison_id": comparison.id,
            "evaluation_id": comparison.current_evaluation_id,
            "candidates": [
                {
                    "label": candidate.label,
                    "run_id": candidate.run_id,
                    "strategy_id": candidate.strategy_id,
                    "strategy_version": candidate.strategy_version,
                    "retrieval_snapshot_id": candidate.retrieval_snapshot_id,
                    "generation_config_hash": candidate.generation_config_hash,
                }
                for candidate in comparison.candidates
            ],
        }

    def _comparison(self, comparison_id: UUID) -> BlindComparison:
        try:
            return self._comparisons[comparison_id]
        except KeyError as error:
            raise ValidationError("comparison not found") from error

    @staticmethod
    def _validate_result(comparison: BlindComparison, result: EvaluationResult) -> None:
        labels = {candidate.label for candidate in comparison.candidates}
        dimensions = {dimension.key: dimension for dimension in comparison.rubric.dimensions}
        if set(result.scores) != labels:
            raise ValidationError("scores must cover every anonymous comparison label")
        for label, score in result.scores.items():
            if set(score) != set(dimensions):
                raise ValidationError(f"scores for {label} must cover every rubric dimension")
            for key, value in score.items():
                dimension = dimensions[key]
                if not dimension.minimum <= value <= dimension.maximum:
                    raise ValidationError(f"score for {key} is outside rubric bounds")
        if result.preference != "tie" and result.preference not in labels:
            raise ValidationError("preference must be a label or tie")

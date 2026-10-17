"""Small in-memory blind-evaluation aggregate used by API adapters and tests."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict

from adr_forge.evaluation.models import (
    CandidateRun,
    EvaluationResult,
    EvaluatorType,
    JudgeModelIdentity,
    RubricVersion,
)

LabeledCandidate = tuple[str, CandidateRun]


class EvaluationConflict(ValueError):
    pass


class EvaluationRequired(ValueError):
    pass


class BlindedCandidate(BaseModel):
    """The identity-safe candidate representation exposed before evaluation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    label: str
    adr: dict[str, object]


class BlindedComparison(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    candidates: list[BlindedCandidate]
    evaluated: bool


class RevealedCandidate(BaseModel):
    """A candidate with its blind label and full run identity after reveal."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    label: str
    candidate: CandidateRun


class Reveal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    evaluation_id: UUID
    candidates: list[RevealedCandidate]


class Comparison:
    def __init__(
        self,
        candidates: list[CandidateRun],
        rubric: RubricVersion,
        shuffler: Callable[[list[LabeledCandidate]], list[LabeledCandidate]],
    ) -> None:
        if len(candidates) < 2 or len({item.run_id for item in candidates}) != len(candidates):
            raise ValueError("comparison requires two distinct completed runs")
        if any(item.status != "completed" for item in candidates):
            raise ValueError("comparison candidates must be completed")
        if len({item.scenario_revision_id for item in candidates}) != 1:
            raise ValueError("comparison candidates must share scenario revision")
        # Allocate labels before shuffling.  A shuffle changes display order but
        # never changes which run is represented by a given blind label.
        labeled_candidates = [
            (chr(65 + index), candidate) for index, candidate in enumerate(candidates)
        ]
        self.id = uuid4()
        self.rubric = rubric
        self._candidates: list[LabeledCandidate] = list(shuffler(labeled_candidates))
        self._history: list[EvaluationResult] = []

    def blinded(self) -> BlindedComparison:
        return BlindedComparison(
            candidates=[
                BlindedCandidate(label=label, adr=candidate.adr)
                for label, candidate in self._candidates
            ],
            evaluated=bool(self._history),
        )

    @classmethod
    def restore(
        cls,
        *,
        identity: UUID,
        candidates: list[LabeledCandidate],
        rubric: RubricVersion,
        history: list[EvaluationResult],
    ) -> Comparison:
        """Rehydrate a comparison without ever reassigning its blind labels."""
        instance = cls.__new__(cls)
        instance.id = identity
        instance.rubric = rubric
        instance._candidates = candidates
        instance._history = history
        return instance

    def submit(
        self,
        *,
        evaluator_id: str,
        evaluator_type: str,
        scores: dict[str, dict[str, int]],
        preference: str,
        judge_model_identity: JudgeModelIdentity | dict[str, str] | None = None,
        notes: str | None = None,
        supersedes_evaluation_id: UUID | None = None,
    ) -> EvaluationResult:
        labels = [item.label for item in self.blinded().candidates]
        dimensions = {item.key: item for item in self.rubric.dimensions}
        if set(scores) != set(labels) or any(
            set(value) != set(dimensions) for value in scores.values()
        ):
            raise ValueError("scores must cover every label and dimension")
        if preference != "tie" and preference not in labels:
            raise ValueError("preference must be a label or tie")
        if self._history:
            if supersedes_evaluation_id is None:
                raise EvaluationConflict("evaluation_already_submitted")
            if supersedes_evaluation_id != self._history[-1].id:
                if any(item.id == supersedes_evaluation_id for item in self._history):
                    raise EvaluationConflict("stale evaluation")
                raise EvaluationConflict("stale comparison correction parent")
        elif supersedes_evaluation_id is not None:
            raise EvaluationConflict("comparison has no evaluation to correct")
        result = EvaluationResult(
            comparison_id=self.id,
            rubric_version_id=self.rubric.id,
            evaluator_id=evaluator_id,
            evaluator_type=EvaluatorType(evaluator_type),
            judge_model_identity=judge_model_identity,
            scores=scores,
            preference=preference,
            notes=notes,
            supersedes_evaluation_id=supersedes_evaluation_id,
        )
        self._history.append(result)
        return result

    def reveal(self) -> Reveal:
        if not self._history:
            raise EvaluationRequired("evaluation_required")
        return Reveal(
            evaluation_id=self._history[-1].id,
            candidates=[
                RevealedCandidate(label=label, candidate=candidate)
                for label, candidate in self._candidates
            ],
        )

    def history(self) -> list[EvaluationResult]:
        return list(self._history)


class BlindComparisonService:
    def __init__(
        self,
        *,
        shuffler: Callable[[list[LabeledCandidate]], list[LabeledCandidate]] = lambda value: value,
    ) -> None:
        self._shuffler = shuffler

    def create(self, *, candidates: list[CandidateRun], rubric: RubricVersion) -> Comparison:
        return Comparison(candidates, rubric, self._shuffler)

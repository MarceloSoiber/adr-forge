"""Blind comparison evaluation is append-only and reveal-gated."""

from __future__ import annotations

from uuid import uuid4

import pytest

from adr_forge.evaluation.models import CandidateRun, RubricDimension, RubricVersion
from adr_forge.evaluation.service import (
    BlindComparisonService,
    EvaluationConflict,
    EvaluationRequired,
)


def _rubric() -> RubricVersion:
    return RubricVersion(
        name="adr-quality",
        version="1",
        dimensions=[
            RubricDimension(
                key="coherence",
                description="Coerência",
                minimum=1,
                maximum=5,
                anchors={"1": "fraca", "5": "forte"},
            ),
            RubricDimension(
                key="security",
                description="Segurança",
                minimum=1,
                maximum=5,
                anchors={"1": "fraca", "5": "forte"},
            ),
        ],
    )


def _candidate(*, run_id: object | None = None, revision_id: object | None = None) -> CandidateRun:
    return CandidateRun(
        run_id=run_id or uuid4(),
        scenario_revision_id=revision_id or uuid4(),
        status="completed",
        adr={"title": "ADR", "schema_version": "adr-v1"},
        strategy_id="rag",
        strategy_version="1",
        generation_config_hash="a" * 64,
        retrieval_snapshot_id=uuid4(),
    )


def _scores(labels: list[str]) -> dict[str, dict[str, int]]:
    return {label: {"coherence": 4, "security": 5} for label in labels}


def test_blinded_projection_never_contains_identity_bearing_fields_before_submission() -> None:
    revision_id = uuid4()
    comparison = BlindComparisonService(shuffler=lambda items: list(reversed(items))).create(
        candidates=[_candidate(revision_id=revision_id), _candidate(revision_id=revision_id)],
        rubric=_rubric(),
    )
    payload = comparison.blinded()

    assert [candidate.label for candidate in payload.candidates] == ["B", "A"]
    assert payload.evaluated is False
    for candidate in payload.candidates:
        serialized = candidate.model_dump()
        assert not (
            {"run_id", "strategy_id", "strategy_version", "retrieval_snapshot_id", "artifact_id"}
            & set(serialized)
        )


def test_ineligible_runs_and_reveal_before_submission_are_rejected() -> None:
    service = BlindComparisonService(shuffler=lambda items: items)
    revision_id = uuid4()
    with pytest.raises(ValueError, match="completed"):
        service.create(
            candidates=[
                _candidate(revision_id=revision_id),
                _candidate(revision_id=revision_id).model_copy(update={"status": "failed"}),
            ],
            rubric=_rubric(),
        )

    comparison = service.create(
        candidates=[_candidate(revision_id=revision_id), _candidate(revision_id=revision_id)],
        rubric=_rubric(),
    )
    with pytest.raises(EvaluationRequired):
        comparison.reveal()


def test_complete_submission_unlocks_reveal_and_preserves_immutable_history() -> None:
    service = BlindComparisonService(shuffler=lambda items: items)
    revision_id = uuid4()
    comparison = service.create(
        candidates=[_candidate(revision_id=revision_id), _candidate(revision_id=revision_id)],
        rubric=_rubric(),
    )
    labels = [candidate.label for candidate in comparison.blinded().candidates]
    first = comparison.submit(
        evaluator_id="reviewer",
        evaluator_type="human",
        scores=_scores(labels),
        preference=labels[0],
    )

    reveal = comparison.reveal()
    assert reveal.evaluation_id == first.id
    assert {candidate.label for candidate in reveal.candidates} == set(labels)
    with pytest.raises(EvaluationConflict, match="already_submitted"):
        comparison.submit(
            evaluator_id="reviewer",
            evaluator_type="human",
            scores=_scores(labels),
            preference="tie",
        )

    corrected = comparison.submit(
        evaluator_id="reviewer",
        evaluator_type="human",
        scores=_scores(labels),
        preference="tie",
        supersedes_evaluation_id=first.id,
    )
    assert corrected.id != first.id
    assert corrected.supersedes_evaluation_id == first.id
    assert comparison.history() == [first, corrected]


def test_scores_preference_and_correction_parent_must_match_current_comparison_head() -> None:
    service = BlindComparisonService(shuffler=lambda items: items)
    revision_id = uuid4()
    comparison = service.create(
        candidates=[_candidate(revision_id=revision_id), _candidate(revision_id=revision_id)],
        rubric=_rubric(),
    )
    labels = [candidate.label for candidate in comparison.blinded().candidates]
    with pytest.raises(ValueError, match="scores"):
        comparison.submit(
            evaluator_id="reviewer",
            evaluator_type="human",
            scores={labels[0]: {"coherence": 4}},
            preference=labels[0],
        )
    with pytest.raises(ValueError, match="preference"):
        comparison.submit(
            evaluator_id="reviewer", evaluator_type="human", scores=_scores(labels), preference="Z"
        )

    first = comparison.submit(
        evaluator_id="reviewer", evaluator_type="human", scores=_scores(labels), preference="tie"
    )
    with pytest.raises(EvaluationConflict, match="stale"):
        comparison.submit(
            evaluator_id="reviewer",
            evaluator_type="human",
            scores=_scores(labels),
            preference="tie",
            supersedes_evaluation_id=uuid4(),
        )

    other = service.create(
        candidates=[_candidate(revision_id=revision_id), _candidate(revision_id=revision_id)],
        rubric=_rubric(),
    )
    other_labels = [candidate.label for candidate in other.blinded().candidates]
    other.submit(
        evaluator_id="reviewer",
        evaluator_type="human",
        scores=_scores(other_labels),
        preference="tie",
    )
    with pytest.raises(EvaluationConflict, match="comparison"):
        other.submit(
            evaluator_id="reviewer",
            evaluator_type="human",
            scores=_scores(other_labels),
            preference="tie",
            supersedes_evaluation_id=first.id,
        )

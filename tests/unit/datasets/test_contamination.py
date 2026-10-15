"""Cross-partition contamination must be visible before publication."""

from __future__ import annotations

from uuid import UUID, uuid4

from adr_forge.datasets.contamination import detect_contamination
from adr_forge.datasets.models import DatasetExample, SourceType
from adr_forge.datasets.versioning import DatasetMembership, DatasetSplit
from adr_forge.scenarios.models import DecisionCategory


def _example(content: str, *, parent_ids: list[UUID] | None = None) -> DatasetExample:
    return DatasetExample(
        scenario_revision_id=uuid4(),
        source_type=SourceType.AUTHORED,
        license="CC-BY-4.0",
        language="pt-BR",
        categories=[DecisionCategory.SQL_VS_NOSQL],
        lineage_parent_ids=parent_ids or [],
        prompt=content,
        completion="ADR de teste.",
    )


def _membership(
    example: DatasetExample, split: DatasetSplit, *, group_id: UUID | None = None
) -> DatasetMembership:
    return DatasetMembership(
        dataset_version_id=uuid4(),
        example_id=example.id,
        split=split,
        lineage_group_id=str(group_id or uuid4()),
    )


def test_content_hash_is_canonical_and_changes_when_dataset_content_changes() -> None:
    same_a = _example("Escolher SQL para transações críticas.")
    same_b = _example("Escolher SQL para transações críticas.")
    changed = _example("Escolher NoSQL para eventos de telemetria.")

    assert same_a.content_hash == same_b.content_hash
    assert changed.content_hash != same_a.content_hash


def test_exact_duplicate_across_train_and_evaluation_is_a_blocking_finding() -> None:
    duplicate = _example("Escolher SQL para transações críticas.")
    duplicate_copy = _example("Escolher SQL para transações críticas.")

    findings = detect_contamination(
        examples=[duplicate, duplicate_copy],
        memberships=[
            _membership(duplicate, DatasetSplit.TRAIN),
            _membership(duplicate_copy, DatasetSplit.EVALUATION),
        ],
    )

    assert [(item.kind, item.blocking) for item in findings] == [("exact_duplicate", True)]


def test_normalized_duplicate_across_train_and_evaluation_is_a_blocking_finding() -> None:
    train = _example("Escolher SQL para transações críticas no catálogo.")
    evaluation = _example(" escolher  sql PARA transações críticas no catálogo! ")

    findings = detect_contamination(
        examples=[train, evaluation],
        memberships=[
            _membership(train, DatasetSplit.TRAIN),
            _membership(evaluation, DatasetSplit.EVALUATION),
        ],
    )

    assert [(item.kind, item.blocking) for item in findings] == [("normalized_duplicate", True)]


def test_lineage_group_cannot_cross_into_fixed_evaluation_partition() -> None:
    parent = _example("Escolher SQL para transações críticas.")
    derivative = _example(
        "Escolher SQL para transações críticas em pagamentos.", parent_ids=[parent.id]
    )
    family = uuid4()

    findings = detect_contamination(
        examples=[parent, derivative],
        memberships=[
            _membership(parent, DatasetSplit.VALIDATION, group_id=family),
            _membership(derivative, DatasetSplit.EVALUATION, group_id=family),
        ],
    )

    assert [(item.kind, item.blocking) for item in findings] == [("lineage_split_leak", True)]


def test_planted_cross_split_leakage_reports_every_blocking_mechanism() -> None:
    exact_train = _example("Escolher SQL para transações críticas.")
    exact_eval = _example("Escolher SQL para transações críticas.")
    normalized_train = _example("Eventos assíncronos devem usar fila durável.")
    normalized_eval = _example(" eventos assincronos DEVEM usar fila durável ")
    lineage_train = _example("Monólito modular para a primeira versão.")
    lineage_eval = _example("Monólito modular para a primeira versão com extração futura.")
    family = uuid4()

    findings = detect_contamination(
        examples=[
            exact_train,
            exact_eval,
            normalized_train,
            normalized_eval,
            lineage_train,
            lineage_eval,
        ],
        memberships=[
            _membership(exact_train, DatasetSplit.TRAIN),
            _membership(exact_eval, DatasetSplit.EVALUATION),
            _membership(normalized_train, DatasetSplit.TRAIN),
            _membership(normalized_eval, DatasetSplit.EVALUATION),
            _membership(lineage_train, DatasetSplit.TRAIN, group_id=family),
            _membership(lineage_eval, DatasetSplit.EVALUATION, group_id=family),
        ],
    )

    assert {(item.kind, item.blocking) for item in findings} == {
        ("exact_duplicate", True),
        ("normalized_duplicate", True),
        ("lineage_split_leak", True),
    }

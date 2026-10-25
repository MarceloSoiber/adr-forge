"""Structured training rows must teach the same valid ADR contract as inference."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from adr_forge.datasets.builder import (
    _structured_training_row,
    _structured_training_rows_v2,
    load_and_validate_manifest,
)
from adr_forge.datasets.models import DatasetExample, ReviewStatus, SourceType
from adr_forge.decisions.schemas import ADRDraft
from adr_forge.decisions.validation import validate_adr_draft


def test_structured_training_row_is_a_valid_provisional_adr() -> None:
    example = DatasetExample(
        scenario_revision_id=uuid4(),
        source_type=SourceType.AUTHORED,
        license="CC-BY-4.0",
        language="pt-BR",
        categories=["sql_vs_nosql"],
        review_status=ReviewStatus.APPROVED,
        reviewed_by="reviewer@example.test",
        reviewed_at="2026-10-16T12:00:00Z",
        prompt="Precisamos decidir a persistência para um catálogo local.",
        completion="Use uma opção relacional se a consistência for necessária.",
    )

    row = _structured_training_row(example)
    completion = json.loads(str(row["completion"]))
    draft = ADRDraft.model_validate({**completion, "analysis_run_id": str(uuid4())})

    assert row["prompt"].startswith("Gere somente um objeto JSON ADR em português")
    assert draft.status == "provisional"
    assert validate_adr_draft(draft) == []


def test_v2_complete_case_teaches_a_valid_proposed_adr() -> None:
    example = DatasetExample(
        scenario_revision_id=uuid4(),
        source_type=SourceType.AUTHORED,
        license="CC-BY-4.0",
        language="pt-BR",
        categories=["sql_vs_nosql"],
        review_status=ReviewStatus.APPROVED,
        reviewed_by="curadoria",
        reviewed_at="2026-10-16T12:00:00Z",
        prompt="Caso completo 01 — Pagamentos exigem ACID e auditoria. SQL ou NoSQL?",
        completion="Escolha SQL relacional para garantir transações e auditoria.",
    )

    rows = _structured_training_rows_v2(example)
    target = json.loads(str(rows[0]["completion"]))
    draft = ADRDraft.model_validate({**target, "analysis_run_id": str(uuid4())})

    assert len(rows) == 1
    assert draft.status == "proposed"
    assert validate_adr_draft(draft) == []


def test_v2_incomplete_case_teaches_new_question_after_clarification() -> None:
    example = DatasetExample(
        scenario_revision_id=uuid4(),
        source_type=SourceType.AUTHORED,
        license="CC-BY-4.0",
        language="pt-BR",
        categories=["sql_vs_nosql"],
        review_status=ReviewStatus.APPROVED,
        reviewed_by="curadoria",
        reviewed_at="2026-10-16T12:00:00Z",
        prompt="Caso incompleto 06 — Não há volume ou padrão de consultas.",
        completion="As consultas exigem consistência forte.",
    )

    rows = _structured_training_rows_v2(example)
    first = json.loads(str(rows[0]["completion"]))
    second = json.loads(str(rows[1]["completion"]))

    assert len(rows) == 2
    assert (
        first["unresolved_questions"][0]["question"]
        != second["unresolved_questions"][0]["question"]
    )
    assert "Esclarecimentos já respondidos" in str(rows[1]["prompt"])
    for target in (first, second):
        draft = ADRDraft.model_validate({**target, "analysis_run_id": str(uuid4())})
        assert validate_adr_draft(draft) == []


def test_v040_manifest_is_governed_and_uses_dialogue_format() -> None:
    validation = load_and_validate_manifest(Path("datasets/manifests/v0.4.0-adr-dialogue.json"))

    assert validation.valid
    assert validation.output_format == "adr-json-v2"
    assert len(validation.examples) == 100


def test_versioned_json_schema_matches_generated_contract_keys() -> None:
    schema = json.loads(Path("datasets/schemas/adr-v1.json").read_text(encoding="utf-8"))
    generated_fields = set(ADRDraft.model_fields) - {"id", "analysis_run_id", "created_at"}

    assert schema["properties"]["schema_version"] == {"const": "adr-v1"}
    assert set(schema["properties"]) == generated_fields
    assert set(schema["required"]) == generated_fields

"""Structured training rows must teach the same valid ADR contract as inference."""

from __future__ import annotations

import json
from uuid import uuid4

from adr_forge.datasets.builder import _structured_training_row
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

    assert row["prompt"].startswith("Gere somente JSON para um ADR em português")
    assert draft.status == "provisional"
    assert validate_adr_draft(draft) == []

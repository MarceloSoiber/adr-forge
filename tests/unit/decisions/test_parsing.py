from __future__ import annotations

import json
from uuid import uuid4

from adr_forge.decisions.parsing import parse_adr_output, parse_with_one_repair
from adr_forge.decisions.repair import repair_adr_json
from adr_forge.decisions.schemas import ADRDraft


def test_schema_findings_identify_missing_and_unexpected_fields() -> None:
    result = parse_adr_output('{"schema_version":"adr-v1","unexpected":true}', uuid4())

    findings = {(finding.path, finding.message) for finding in result.findings}

    assert ("/title", "Campo obrigatório ausente.") in findings
    assert (
        "/unexpected",
        "Campo não permitido. Valor recebido: true.",
    ) in findings


def test_one_repair_unblocks_constraint_object_without_inventing_content() -> None:
    run_id = uuid4()
    payload = ADRDraft(
        analysis_run_id=run_id,
        schema_version="adr-v1",
        title="Escolha pendente",
        status="provisional",
        context=["Ainda faltam informações para uma decisão conclusiva."],
        assumptions=[],
        unresolved_questions=[
            {
                "id": "question-context",
                "question": "Qual requisito deve orientar a decisão?",
                "impact": "Sem essa informação, a decisão permanece provisória.",
            }
        ],
        constraints=["placeholder"],
        confidence=0.5,
    ).model_dump(mode="json")
    payload["constraints"] = [
        {
            "id": "constraint:integrity",
            "restriction": "A integridade dos dados não pode ser comprometida.",
            "priority": True,
        }
    ]
    payload["reference"] = None

    result = parse_with_one_repair(json.dumps(payload), run_id, repair_adr_json)

    assert result.original.parse_succeeded is False
    assert result.repaired is not None
    assert result.repaired.parse_succeeded is True
    assert result.repaired.draft is not None
    assert result.repaired.draft.constraints == [
        "A integridade dos dados não pode ser comprometida."
    ]
    assert result.repaired_output is not None


def test_repair_leaves_unknown_constraint_object_invalid() -> None:
    raw_output = '{"constraints":[{"priority":true}]}'

    assert repair_adr_json(raw_output) == raw_output

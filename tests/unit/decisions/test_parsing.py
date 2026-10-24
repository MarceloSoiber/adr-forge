from __future__ import annotations

from uuid import uuid4

from adr_forge.decisions.parsing import parse_adr_output


def _valid_payload() -> dict[str, object]:
    return {
        "schema_version": "adr-v1",
        "title": "Escolha de persistência",
        "status": "provisional",
        "context": ["O serviço processa pagamentos."],
        "facts": ["A equipe opera PostgreSQL."],
        "assumptions": [
            {
                "id": "a1",
                "statement": "O volume continuará moderado.",
                "impact": "Pode exigir revisão futura.",
                "confidence": 0.5,
            }
        ],
        "unresolved_questions": [
            {"id": "q1", "question": "Qual será o pico?", "impact": "Define a capacidade."}
        ],
        "constraints": ["Integridade é obrigatória."],
        "alternatives": [],
        "decision": None,
        "rationale": [
            {"claim": "A equipe conhece a tecnologia.", "evidence_kind": "fact", "evidence_id": "0"}
        ],
        "positive_consequences": [],
        "negative_consequences": [],
        "risks": [
            {"description": "Sobrecarga.", "likelihood": 0.4, "impact": 0.8, "mitigation": "Medir."}
        ],
        "review_triggers": [
            {"metric": "latencia_p95", "operator": ">", "threshold": 200, "unit": "ms"}
        ],
        "confidence": 0.5,
        "reference_ids": [],
    }


def test_schema_findings_identify_missing_and_unexpected_fields() -> None:
    result = parse_adr_output('{"schema_version":"adr-v1","unexpected":true}', uuid4())

    findings = {(finding.path, finding.message) for finding in result.findings}

    assert ("/title", "Campo obrigatório ausente.") in findings
    assert (
        "/unexpected",
        "Campo não permitido. Valor recebido: true.",
    ) in findings


def test_parser_normalizes_unambiguous_model_equivalents() -> None:
    import json

    result = parse_adr_output(json.dumps(_valid_payload()), uuid4())

    assert result.draft is not None
    assert result.draft.risks[0].likelihood == "medium"
    assert result.draft.risks[0].impact == "high"
    assert result.draft.review_triggers[0].operator == "gt"
    assert result.draft.rationale[0].evidence_id == "fact:0"
    assert len([finding for finding in result.findings if finding.code == "output.normalized"]) == 4


def test_parser_replaces_answered_question_with_assumption_confirmation() -> None:
    import json

    payload = _valid_payload()
    payload["unresolved_questions"] = [
        {
            "id": "q1",
            "question": "Qual será o pico?",
            "impact": "Define a capacidade.",
        }
    ]

    result = parse_adr_output(
        json.dumps(payload),
        uuid4(),
        answered_questions=["Qual será o pico?"],
    )

    assert result.draft is not None
    assert result.draft.unresolved_questions[0].id == "confirm-assumption-a1"
    assert "O volume continuará moderado" in result.draft.unresolved_questions[0].question
    assert "unresolved_questions.already_answered" not in {
        finding.code for finding in result.findings
    }


def test_parser_creates_confirmation_question_when_provisional_list_is_empty() -> None:
    import json

    payload = _valid_payload()
    payload["unresolved_questions"] = []

    result = parse_adr_output(json.dumps(payload), uuid4())

    assert result.draft is not None
    assert [question.id for question in result.draft.unresolved_questions] == [
        "confirm-assumption-a1"
    ]
    assert "unresolved_questions.required" not in {finding.code for finding in result.findings}

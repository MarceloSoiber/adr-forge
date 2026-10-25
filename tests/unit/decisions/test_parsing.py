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


def test_parser_restores_source_context_and_flattens_constraint_objects() -> None:
    import json

    payload = _valid_payload()
    payload["context"] = []
    payload["constraints"] = [
        {"id": "constraint:0", "text": "Integridade financeira é obrigatória."},
        "O lançamento deve ocorrer em oito semanas.",
    ]

    result = parse_adr_output(
        json.dumps(payload),
        uuid4(),
        source_context="Escolher a persistência para o serviço de pagamentos.",
    )

    assert result.draft is not None
    assert result.draft.context == ["Escolher a persistência para o serviço de pagamentos."]
    assert result.draft.constraints == [
        "Integridade financeira é obrigatória.",
        "O lançamento deve ocorrer em oito semanas.",
    ]
    normalized_paths = {
        finding.path for finding in result.findings if finding.code == "output.normalized"
    }
    assert {"/context", "/constraints/0"} <= normalized_paths


def test_parser_converts_qualitative_assumption_confidence() -> None:
    import json

    payload = _valid_payload()
    assumptions = payload["assumptions"]
    assert isinstance(assumptions, list)
    assert isinstance(assumptions[0], dict)
    assumptions[0]["confidence"] = "high"

    result = parse_adr_output(json.dumps(payload), uuid4())

    assert result.draft is not None
    assert result.draft.assumptions[0].confidence == 0.75


def test_parser_accepts_constraint_rationale_from_model_output() -> None:
    import json

    payload = _valid_payload()
    payload["rationale"] = [
        {
            "claim": "A solução preserva a integridade financeira.",
            "evidence_kind": "constraint",
            "evidence_id": "constraint:0",
        }
    ]

    result = parse_adr_output(json.dumps(payload), uuid4())

    assert result.draft is not None
    assert not any(finding.severity == "error" for finding in result.findings)


def test_parser_does_not_recreate_an_answered_assumption_question() -> None:
    import json

    payload = _valid_payload()
    answered = "A premissa a seguir está correta? O volume continuará moderado."
    payload["unresolved_questions"] = [
        {"id": "q1", "question": answered, "impact": "Pode exigir revisão futura."}
    ]

    result = parse_adr_output(
        json.dumps(payload),
        uuid4(),
        answered_questions=[answered],
    )

    assert result.draft is not None
    assert result.draft.unresolved_questions[0].id == "missing-alternatives"
    assert result.draft.unresolved_questions[0].question != answered
    assert "unresolved_questions.already_answered" not in {
        finding.code for finding in result.findings
    }


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

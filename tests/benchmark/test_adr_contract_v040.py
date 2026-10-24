"""Holdout contract cases derived from observed local-model failures."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

import pytest

from adr_forge.decisions.parsing import parse_adr_output

CASES = [
    json.loads(line)
    for line in Path("datasets/evaluation/v0.4.0-contract.jsonl")
    .read_text(encoding="utf-8")
    .splitlines()
]


def _provisional_payload() -> dict[str, object]:
    return {
        "schema_version": "adr-v1",
        "title": "Persistência de pagamentos",
        "status": "provisional",
        "context": ["Pagamentos exigem integridade e auditoria."],
        "facts": ["A equipe opera PostgreSQL."],
        "assumptions": [
            {
                "id": "a1",
                "statement": "O serviço gerenciado atende à operação.",
                "impact": "Define o esforço operacional.",
                "confidence": 0.5,
            }
        ],
        "unresolved_questions": [
            {
                "id": "q1",
                "question": "Serviço gerenciado é permitido?",
                "impact": "Define a topologia operacional.",
            }
        ],
        "constraints": ["Integridade financeira é obrigatória."],
        "alternatives": [],
        "decision": None,
        "rationale": [
            {
                "claim": "A equipe conhece PostgreSQL.",
                "evidence_kind": "fact",
                "evidence_id": "fact:0",
            }
        ],
        "positive_consequences": [],
        "negative_consequences": [],
        "risks": [
            {
                "description": "A carga pode crescer.",
                "likelihood": "medium",
                "impact": "high",
                "mitigation": "Monitorar capacidade.",
            }
        ],
        "review_triggers": [
            {"metric": "latencia_p95", "operator": "gte", "threshold": 200, "unit": "ms"}
        ],
        "confidence": 0.5,
        "reference_ids": [],
    }


def _mutate(payload: dict[str, object], mutation: str) -> list[str]:
    answered: list[str] = []
    if mutation == "context_empty":
        payload["context"] = []
    elif mutation == "assumption_confidence_label":
        payload["assumptions"][0]["confidence"] = "high"  # type: ignore[index]
    elif mutation == "question_extra_confidence":
        payload["unresolved_questions"][0]["confidence"] = 0.6  # type: ignore[index]
    elif mutation == "extra_alternative_ids":
        payload["alternative_ids"] = []
    elif mutation == "numeric_risk":
        payload["risks"][0]["likelihood"] = 0.4  # type: ignore[index]
    elif mutation == "symbolic_operator":
        payload["review_triggers"][0]["operator"] = ">"  # type: ignore[index]
    elif mutation == "answered_question":
        answered = ["Serviço gerenciado é permitido?"]
    else:  # pragma: no cover - fixture and dispatcher evolve together
        raise AssertionError(f"unknown mutation: {mutation}")
    return answered


@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
def test_v040_holdout_contract_case(case: dict[str, str]) -> None:
    payload = deepcopy(_provisional_payload())
    answered = _mutate(payload, case["mutation"])

    result = parse_adr_output(
        json.dumps(payload, ensure_ascii=False),
        uuid4(),
        answered_questions=answered,
    )

    matching = [finding for finding in result.findings if finding.path == case["expected_path"]]
    if case["expected"] == "invalid":
        assert result.draft is None
        assert any(finding.severity == "error" for finding in matching)
    else:
        assert result.draft is not None
        assert not any(finding.severity == "error" for finding in result.findings)
        assert any(finding.code == "output.normalized" for finding in matching)

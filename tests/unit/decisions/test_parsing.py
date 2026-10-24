from __future__ import annotations

from uuid import uuid4

from adr_forge.decisions.parsing import parse_adr_output


def test_schema_findings_identify_missing_and_unexpected_fields() -> None:
    result = parse_adr_output('{"schema_version":"adr-v1","unexpected":true}', uuid4())

    findings = {(finding.path, finding.message) for finding in result.findings}

    assert ("/title", "Campo obrigatório ausente.") in findings
    assert (
        "/unexpected",
        "Campo não permitido. Valor recebido: true.",
    ) in findings

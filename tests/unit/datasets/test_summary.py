from __future__ import annotations

import hashlib
import json
from pathlib import Path

from adr_forge.datasets.summary import read_dataset_records, read_dataset_summary


def test_read_dataset_summary_reports_real_artifact_values(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    training = tmp_path / "training.jsonl"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": "v1",
                "version": "v0.4.0-adr-dialogue",
                "output_format": "adr-json-v2",
                "sources": ["one.jsonl", "two.jsonl"],
            }
        ),
        encoding="utf-8",
    )
    row = {
        "example_id": "example:1",
        "prompt": "Escolha uma persistência.",
        "completion": json.dumps(
            {"title": "Persistência SQL", "status": "proposed"}, ensure_ascii=False
        ),
    }
    second_row = {
        **row,
        "example_id": "example:2",
        "completion": json.dumps(
            {
                "title": "Integração assíncrona",
                "status": "provisional",
                "context": ["O processamento pode durar quinze minutos."],
                "decision": None,
                "confidence": 0.6,
            },
            ensure_ascii=False,
        ),
    }
    training.write_text(
        "\n".join((json.dumps(row, ensure_ascii=False), json.dumps(second_row, ensure_ascii=False)))
        + "\n",
        encoding="utf-8",
    )

    summary = read_dataset_summary(manifest, training)

    assert summary.version == "v0.4.0-adr-dialogue"
    assert summary.record_count == 2
    assert summary.source_count == 2
    assert summary.total_bytes == len(training.read_bytes())
    assert summary.artifact_sha256 == hashlib.sha256(training.read_bytes()).hexdigest()
    assert summary.records[0].title == "Persistência SQL"
    assert summary.records[0].domain == "Dados"
    assert summary.records[0].context_excerpt == "Escolha uma persistência."
    assert summary.records[0].decision_excerpt is None
    assert summary.status_counts == {"proposed": 1, "provisional": 1}
    assert summary.domain_counts == {"Dados": 1, "Integração": 1}

    page = read_dataset_records(training, offset=1, limit=1)

    assert page.total == 2
    assert page.offset == 1
    assert page.items[0].id == "example:2"
    assert page.items[0].decision_excerpt is None

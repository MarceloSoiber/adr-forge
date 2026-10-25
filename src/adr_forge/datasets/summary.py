"""Read-only projections for the currently configured training dataset."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict


class DatasetRecordSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    domain: str
    status: str
    tokens: int
    context_excerpt: str
    decision_excerpt: str | None
    confidence: float | None


class DatasetRecordPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[DatasetRecordSummary]
    total: int
    offset: int
    limit: int


class DatasetSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    output_format: str
    schema_version: str
    record_count: int
    source_count: int
    total_bytes: int
    approximate_tokens: int
    manifest_sha256: str
    artifact_sha256: str
    generated_at: datetime
    records: list[DatasetRecordSummary]
    status_counts: dict[str, int]
    domain_counts: dict[str, int]


def read_dataset_summary(
    manifest_path: Path, training_path: Path, *, sample_size: int = 5
) -> DatasetSummary:
    """Build a factual summary without mutating governed dataset artifacts."""
    manifest_bytes = manifest_path.read_bytes()
    artifact_bytes = training_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    rows = [json.loads(line) for line in artifact_bytes.splitlines() if line.strip()]

    all_records = [_record_summary(row) for row in rows]

    return DatasetSummary(
        version=str(manifest["version"]),
        output_format=str(manifest.get("output_format") or "não informado"),
        schema_version=str(manifest["schema_version"]),
        record_count=len(rows),
        source_count=len(manifest.get("sources", [])),
        total_bytes=len(artifact_bytes),
        approximate_tokens=sum(record.tokens for record in all_records),
        manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
        artifact_sha256=hashlib.sha256(artifact_bytes).hexdigest(),
        generated_at=datetime.fromtimestamp(training_path.stat().st_mtime, tz=UTC),
        records=all_records[:sample_size],
        status_counts=_count_by(all_records, "status"),
        domain_counts=_count_by(all_records, "domain"),
    )


def read_dataset_records(
    training_path: Path, *, offset: int = 0, limit: int = 12
) -> DatasetRecordPage:
    """Return a bounded, factual page of records from the configured JSONL artifact."""
    artifact_bytes = training_path.read_bytes()
    rows = [json.loads(line) for line in artifact_bytes.splitlines() if line.strip()]
    records = [_record_summary(row) for row in rows]
    return DatasetRecordPage(
        items=records[offset : offset + limit],
        total=len(records),
        offset=offset,
        limit=limit,
    )


def _record_summary(row: dict[str, object]) -> DatasetRecordSummary:
    completion = json.loads(str(row["completion"]))
    title = str(completion.get("title") or "ADR sem título")
    context = completion.get("context")
    context_text = context[0] if isinstance(context, list) and context else row.get("prompt", "")
    decision = completion.get("decision")
    confidence = completion.get("confidence")
    return DatasetRecordSummary(
        id=str(row["example_id"]),
        title=title,
        domain=_domain_from_title(title),
        status=str(completion.get("status") or "desconhecido"),
        tokens=max(1, (len(str(row["prompt"])) + len(str(row["completion"]))) // 4),
        context_excerpt=_excerpt(str(context_text)),
        decision_excerpt=_excerpt(str(decision)) if decision else None,
        confidence=float(confidence) if isinstance(confidence, int | float) else None,
    )


def _excerpt(value: str, *, limit: int = 220) -> str:
    normalized = " ".join(value.split())
    return normalized if len(normalized) <= limit else f"{normalized[: limit - 1].rstrip()}…"


def _count_by(records: list[DatasetRecordSummary], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        value = str(getattr(record, field))
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _domain_from_title(title: str) -> str:
    normalized = title.casefold()
    if "sql" in normalized or "persist" in normalized:
        return "Dados"
    if "assíncron" in normalized or "sincron" in normalized:
        return "Integração"
    if "monólito" in normalized or "microsserv" in normalized:
        return "Estrutura"
    if "runtime" in normalized or "execução" in normalized:
        return "Operação"
    return "Arquitetura"

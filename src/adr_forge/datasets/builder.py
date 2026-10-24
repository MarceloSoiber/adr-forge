"""Canonical, policy-aware construction of completion-only SFT datasets."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from adr_forge.datasets.governance import validate_example
from adr_forge.datasets.models import DatasetExample
from adr_forge.decisions.schemas import ADRDraft
from adr_forge.decisions.validation import validate_adr_draft
from adr_forge.shared.adr_prompt import build_adr_prompt
from adr_forge.shared.hashing import canonical_json


@dataclass(frozen=True, slots=True)
class DatasetFinding:
    code: str
    example_id: str
    detail: str
    blocking: bool = True


@dataclass(frozen=True, slots=True)
class DatasetValidation:
    source_bytes: bytes
    records: tuple[dict[str, Any], ...]
    examples: tuple[DatasetExample, ...]
    findings: tuple[DatasetFinding, ...]
    output_format: str = "completion-v1"

    @property
    def valid(self) -> bool:
        return not any(finding.blocking for finding in self.findings)


def load_and_validate_manifest(path: Path) -> DatasetValidation:
    """Load a portable manifest and return all deterministic policy findings."""
    raw = path.read_bytes()
    document = json.loads(raw)
    if not isinstance(document, dict) or document.get("schema_version") != "v1":
        raise ValueError("manifest must be a v1 JSON object")
    output_format = document.get("output_format", "completion-v1")
    if output_format not in {"completion-v1", "adr-json-v1", "adr-json-v2"}:
        raise ValueError("manifest output_format is unsupported")
    records = document.get("examples")
    if records is None and isinstance(document.get("sources"), list):
        records = []
        public_root = path.parent.parent / "public"
        for source_name in document["sources"]:
            if not isinstance(source_name, str) or Path(source_name).name != source_name:
                raise ValueError("manifest source must be a public filename")
            source = public_root / source_name
            try:
                records.extend(
                    json.loads(line) for line in source.read_text(encoding="utf-8").splitlines()
                )
            except (OSError, json.JSONDecodeError) as exc:
                raise ValueError(f"cannot load manifest source: {source_name}") from exc
    if not isinstance(records, list) or not all(isinstance(record, dict) for record in records):
        raise ValueError("manifest must contain an examples list")

    examples: list[DatasetExample] = []
    findings: list[DatasetFinding] = []
    for record in records:
        record_id = str(record.get("id", "unknown"))
        try:
            example = _to_example(record)
        except (ValidationError, ValueError) as exc:
            findings.append(DatasetFinding("invalid_example", record_id, str(exc)))
            continue
        examples.append(example)
        findings.extend(
            DatasetFinding(str(finding.code), str(example.id), finding.detail, finding.blocking)
            for finding in validate_example(example)
        )

    return DatasetValidation(
        source_bytes=raw,
        records=tuple(records),
        examples=tuple(examples),
        findings=tuple(
            sorted(findings, key=lambda item: (item.example_id, item.code, item.detail))
        ),
        output_format=output_format,
    )


def build_training_dataset(validation: DatasetValidation, output: Path) -> dict[str, object]:
    """Atomically create canonical JSONL without overwriting an existing artifact."""
    if output.exists():
        raise FileExistsError(f"refusing to overwrite immutable artifact: {output}")
    if not validation.valid:
        raise ValueError("dataset has blocking findings")

    rows = [
        row
        for example in sorted(validation.examples, key=lambda item: str(item.id))
        for row in _training_rows(example, validation.output_format)
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as artifact:
            for row in rows:
                artifact.write(canonical_json(row))
                artifact.write("\n")
            artifact.flush()
            os.fsync(artifact.fileno())
        temporary.replace(output)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise

    payload = output.read_bytes()
    source_hash = hashlib.sha256(validation.source_bytes).hexdigest()
    output_hash = hashlib.sha256(payload).hexdigest()
    return {
        "status": "built",
        "manifest_hash": source_hash,
        "output_hash": output_hash,
        "included": [
            str(example.id)
            for example in sorted(validation.examples, key=lambda item: str(item.id))
        ],
        "exclusions": [],
        "row_count": len(rows),
    }


def validation_report(validation: DatasetValidation) -> dict[str, object]:
    excluded = {finding.example_id for finding in validation.findings}
    return {
        "status": "valid" if validation.valid else "invalid",
        "findings": [asdict(finding) for finding in validation.findings],
        "included": [
            record for record in validation.records if str(record.get("id")) not in excluded
        ],
        "exclusions": [asdict(finding) for finding in validation.findings],
    }


def _to_example(record: dict[str, Any]) -> DatasetExample:
    source = dict(record)
    target = source.pop("target", {})
    content = source.pop("content", None)
    prompt = source.pop("prompt", content if content is not None else "")
    completion = source.pop("completion", json.dumps(target, ensure_ascii=False, sort_keys=True))
    return DatasetExample.model_validate({**source, "prompt": prompt, "completion": completion})


def _training_rows(
    example: DatasetExample, output_format: str = "completion-v1"
) -> list[dict[str, object]]:
    if output_format == "adr-json-v2":
        return _structured_training_rows_v2(example)
    if output_format == "adr-json-v1":
        return [_structured_training_row(example)]
    return [
        {
            "schema_version": "v1",
            "example_id": str(example.id),
            "lineage_parent_ids": [str(parent) for parent in example.lineage_parent_ids],
            "prompt": example.prompt,
            "completion": example.completion,
            "loss_scope": "completion_only",
        }
    ]


def _training_row(
    example: DatasetExample, output_format: str = "completion-v1"
) -> dict[str, object]:
    """Backward-compatible single-row helper for callers and older tests."""
    return _training_rows(example, output_format)[0]


def _structured_training_row(example: DatasetExample) -> dict[str, object]:
    """Teach a valid provisional ADR without fabricating missing source facts."""
    prompt = build_adr_prompt(example.prompt, [], [], [])
    completion = {
        "schema_version": "adr-v1",
        "title": "Decisão de arquitetura pendente",
        "status": "provisional",
        "context": [example.prompt],
        "facts": [],
        "assumptions": [
            {
                "id": "assumption:context-incomplete",
                "statement": (
                    "O contexto não contém fatos e restrições suficientes "
                    "para uma decisão conclusiva."
                ),
                "impact": "A recomendação precisa ser validada após esclarecer o cenário.",
                "confidence": 0.5,
            }
        ],
        "unresolved_questions": [
            {
                "id": "question:missing-context",
                "question": (
                    "Quais fatos, restrições e alternativas precisam orientar esta decisão?"
                ),
                "impact": (
                    "Sem essas informações, uma decisão conclusiva pode "
                    "introduzir risco técnico indevido."
                ),
            }
        ],
        "constraints": [],
        "alternatives": [],
        "decision": None,
        "rationale": [],
        "positive_consequences": [],
        "negative_consequences": [],
        "risks": [],
        "review_triggers": [],
        "confidence": 0.5,
        "reference_ids": [],
    }
    return {
        "schema_version": "v1",
        "example_id": str(example.id),
        "lineage_parent_ids": [str(parent) for parent in example.lineage_parent_ids],
        "prompt": prompt,
        "completion": canonical_json(completion),
        "loss_scope": "completion_only",
    }


_ALTERNATIVES = {
    "sql_vs_nosql": ("SQL relacional", "NoSQL"),
    "sync_vs_async": ("Processamento síncrono", "Processamento assíncrono"),
    "modular_monolith_vs_microservices": ("Monólito modular", "Microsserviços"),
    "containers_vs_serverless_vs_traditional": (
        "Contêineres",
        "Serverless ou infraestrutura tradicional",
    ),
}

_QUESTIONS = {
    "sql_vs_nosql": (
        "Quais garantias de consistência e padrões de consulta são obrigatórios?",
        "Qual volume, pico de escrita e política de retenção devem ser suportados?",
    ),
    "sync_vs_async": (
        "Qual tempo máximo de resposta e confirmação o usuário aceita?",
        "Quais falhas exigem repetição, idempotência ou compensação?",
    ),
    "modular_monolith_vs_microservices": (
        "Quantas equipes implantarão e operarão o sistema de forma independente?",
        "Quais limites de domínio e necessidades reais de escala isolada existem?",
    ),
    "containers_vs_serverless_vs_traditional": (
        "Qual perfil de carga, duração das tarefas e previsibilidade de tráfego existem?",
        "Quais limites de custo, operação, portabilidade e latência são obrigatórios?",
    ),
}


def _structured_training_rows_v2(example: DatasetExample) -> list[dict[str, object]]:
    """Create varied, contract-validated ADR examples plus clarification continuations."""
    category = example.categories[0].value
    alternatives = _ALTERNATIVES[category]
    prompt_kind = example.prompt.casefold()
    conclusive = "caso completo" in prompt_kind or "caso simples" in prompt_kind
    if conclusive:
        prompt = build_adr_prompt(
            example.prompt,
            [example.prompt],
            ["A decisão deve respeitar os requisitos declarados no cenário."],
            list(alternatives),
        )
        target = _proposed_target(example, alternatives)
        return [_validated_structured_row(example, prompt, target, suffix="decision")]

    question, next_question = _QUESTIONS[category]
    prompt = build_adr_prompt(example.prompt, [], [], list(alternatives))
    provisional = _provisional_target(example, question)
    first = _validated_structured_row(example, prompt, provisional, suffix="clarify-1")
    continuation_prompt = build_adr_prompt(
        example.prompt,
        [],
        [],
        list(alternatives),
        [
            f"Pergunta: {question}\n"
            f"Impacto: Define evidências necessárias para a decisão.\n"
            f"Resposta: {example.completion}"
        ],
    )
    continuation = _provisional_target(example, next_question, continuation=True)
    second = _validated_structured_row(
        example, continuation_prompt, continuation, suffix="clarify-2"
    )
    return [first, second]


def _proposed_target(
    example: DatasetExample, alternatives: tuple[str, str]
) -> dict[str, object]:
    return {
        "schema_version": "adr-v1",
        "title": f"Decisão para {example.categories[0].value.replace('_', ' ')}",
        "status": "proposed",
        "context": [example.prompt],
        "facts": [example.prompt],
        "assumptions": [],
        "unresolved_questions": [],
        "constraints": ["A solução deve atender aos requisitos declarados no cenário."],
        "alternatives": [
            {
                "id": f"alternative:{index}",
                "name": name,
                "summary": f"Avaliar {name} contra o contexto e os requisitos informados.",
                "viable": True,
                "rejection_reason": None,
                "benefits": [f"Permite avaliar {name} de forma explícita."],
                "drawbacks": [f"Exige validar os trade-offs operacionais de {name}."],
                "constraint_ids": ["constraint:0"],
            }
            for index, name in enumerate(alternatives)
        ],
        "decision": example.completion,
        "rationale": [
            {
                "claim": example.completion,
                "evidence_kind": "fact",
                "evidence_id": "fact:0",
            }
        ],
        "positive_consequences": ["A decisão fica alinhada às evidências declaradas."],
        "negative_consequences": ["Os trade-offs devem ser acompanhados durante a operação."],
        "risks": [
            {
                "description": "As premissas do cenário podem mudar após a implantação.",
                "likelihood": "medium",
                "impact": "medium",
                "mitigation": "Revisar a decisão quando as métricas operacionais divergirem.",
            }
        ],
        "review_triggers": [
            {
                "metric": "desvio_da_meta_operacional",
                "operator": "gte",
                "threshold": 20,
                "unit": "percentual",
            }
        ],
        "confidence": 0.82,
        "reference_ids": [],
    }


def _provisional_target(
    example: DatasetExample, question: str, *, continuation: bool = False
) -> dict[str, object]:
    stage = "continuation" if continuation else "initial"
    return {
        "schema_version": "adr-v1",
        "title": "Decisão de arquitetura pendente de evidências",
        "status": "provisional",
        "context": [example.prompt],
        "facts": [],
        "assumptions": [
            {
                "id": f"assumption:{stage}",
                "statement": (
                    "Ainda faltam evidências objetivas para concluir a decisão de arquitetura."
                ),
                "impact": "Uma escolha prematura pode introduzir custo ou risco desnecessário.",
                "confidence": 0.45,
            }
        ],
        "unresolved_questions": [
            {
                "id": f"question:{stage}",
                "question": question,
                "impact": "A resposta pode alterar a alternativa recomendada.",
            }
        ],
        "constraints": [],
        "alternatives": [],
        "decision": None,
        "rationale": [],
        "positive_consequences": [],
        "negative_consequences": [],
        "risks": [],
        "review_triggers": [],
        "confidence": 0.5,
        "reference_ids": [],
    }


def _validated_structured_row(
    example: DatasetExample,
    prompt: str,
    target: dict[str, object],
    *,
    suffix: str,
) -> dict[str, object]:
    draft = ADRDraft.model_validate(
        {**target, "analysis_run_id": "00000000-0000-4000-8000-000000000000"}
    )
    errors = [finding for finding in validate_adr_draft(draft) if finding.severity == "error"]
    if errors:
        details = "; ".join(f"{finding.path}: {finding.message}" for finding in errors)
        raise ValueError(f"generated structured target is invalid: {details}")
    return {
        "schema_version": "v2",
        "example_id": f"{example.id}:{suffix}",
        "lineage_parent_ids": [str(parent) for parent in example.lineage_parent_ids],
        "prompt": prompt,
        "completion": canonical_json(target),
        "loss_scope": "completion_only",
    }

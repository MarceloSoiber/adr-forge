"""CPU-safe deterministic strategy for tests and local demonstrations."""

from __future__ import annotations

import json
from time import perf_counter
from uuid import uuid4

from adr_forge.scenarios.models import ScenarioRevision
from adr_forge.strategies.base import (
    GenerationResult,
    GenerationTelemetry,
    StructuredOutputStrategy,
)
from adr_forge.system.progress import CancellationToken


class FakeStrategy(StructuredOutputStrategy):
    async def generate(
        self, scenario: ScenarioRevision, *, cancellation: CancellationToken
    ) -> GenerationResult:
        cancellation.raise_if_cancelled()
        started = perf_counter()
        alternatives = scenario.candidate_alternatives or ["Opção A", "Opção B"]
        while len(alternatives) < 2:
            alternatives.append("Alternativa adicional")
        facts = scenario.facts
        assumptions = []
        rationale = []
        if facts:
            rationale = [
                {
                    "claim": "A recomendação usa a evidência disponível.",
                    "evidence_kind": "fact",
                    "evidence_id": "fact:0",
                }
            ]
        else:
            assumptions = [
                {
                    "id": "fake-assumption",
                    "statement": "O contexto enviado representa a necessidade inicial.",
                    "impact": "Permite uma análise inicial revisável.",
                    "confidence": 0.5,
                }
            ]
            rationale = [
                {
                    "claim": "A recomendação é uma proposta inicial revisável.",
                    "evidence_kind": "assumption",
                    "evidence_id": "fake-assumption",
                }
            ]
        payload = {
            "id": str(uuid4()),
            "analysis_run_id": str(uuid4()),
            "schema_version": "adr-v1",
            "title": scenario.problem[:200],
            "status": "proposed",
            "context": [scenario.problem],
            "facts": facts,
            "assumptions": assumptions,
            "unresolved_questions": [],
            "constraints": scenario.constraints or ["Operação local e orçamento controlado."],
            "alternatives": [
                {
                    "id": f"alternative-{index}",
                    "name": name,
                    "summary": name,
                    "viable": True,
                    "benefits": ["Opção avaliada."],
                    "drawbacks": ["Exige revisão humana."],
                    "constraint_ids": ["constraint:0"],
                }
                for index, name in enumerate(alternatives[:2])
            ],
            "decision": alternatives[0],
            "rationale": rationale,
            "positive_consequences": ["Mantém a decisão explícita."],
            "negative_consequences": ["Requer validação humana."],
            "risks": [],
            "review_triggers": [
                {"metric": "latencia_p95", "operator": "gt", "threshold": 500, "unit": "ms"}
            ],
            "confidence": 0.5,
            "reference_ids": [],
        }
        return GenerationResult(
            raw_output=json.dumps(payload, ensure_ascii=False),
            telemetry=GenerationTelemetry(latency_ms=int((perf_counter() - started) * 1000)),
        )

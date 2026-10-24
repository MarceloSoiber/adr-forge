"""CPU-safe deterministic strategy for tests and local demonstrations."""

from __future__ import annotations

import json
from time import perf_counter
from uuid import uuid4

from adr_forge.decisions.validation import classify_context
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
        alternatives = list(scenario.candidate_alternatives) or ["Opção A", "Opção B"]
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
        context_findings = classify_context(scenario)
        answered_question_ids = {
            answer.question_id for answer in scenario.clarification_answers
        }
        needs_clarification = (
            (not scenario.facts and "context-scale" not in answered_question_ids)
            or (not scenario.constraints and "context-constraints" not in answered_question_ids)
            or any(
                finding.code == "context.contradictory_constraints"
                for finding in context_findings
            )
        )
        if needs_clarification and not assumptions:
            assumptions = [
                {
                    "id": "fake-clarification-assumption",
                    "statement": (
                        "Os trade-offs restantes dependem dos esclarecimentos solicitados."
                    ),
                    "impact": "Mantém a recomendação explicitamente provisória.",
                    "confidence": 0.5,
                }
            ]
        questions = []
        if needs_clarification:
            if not scenario.facts and "context-scale" not in answered_question_ids:
                questions.append(
                    {
                        "id": "context-scale",
                        "question": "Qual é a escala esperada de uso e dados?",
                        "impact": "Define capacidade e custo operacional.",
                    }
                )
            if not scenario.constraints and "context-constraints" not in answered_question_ids:
                questions.append(
                    {
                        "id": "context-constraints",
                        "question": (
                            "Quais restrições de custo, disponibilidade e operação "
                            "são inegociáveis?"
                        ),
                        "impact": "Evita recomendar uma alternativa incompatível.",
                    }
                )
            if any(item.code == "context.contradictory_constraints" for item in context_findings):
                questions.append(
                    {
                        "id": "context-tradeoff",
                        "question": (
                            "Qual prioridade deve prevalecer entre custo e disponibilidade?"
                        ),
                        "impact": "Resolve o conflito que muda a recomendação.",
                    }
                )
            if not questions:
                questions.append(
                    {
                        "id": "context-priority",
                        "question": "Qual resultado de negócio é mais importante nesta decisão?",
                        "impact": "Orienta o trade-off entre alternativas.",
                    }
                )
        payload = {
            "id": str(uuid4()),
            "analysis_run_id": str(uuid4()),
            "schema_version": "adr-v1",
            "title": scenario.problem[:200],
            "status": "provisional" if needs_clarification else "proposed",
            "context": [scenario.problem],
            "facts": facts,
            "assumptions": assumptions,
            "unresolved_questions": questions[:3],
            "constraints": scenario.constraints,
            "alternatives": [
                {
                    "id": f"alternative-{index}",
                    "name": name,
                    "summary": name,
                    "viable": True,
                    "benefits": ["Opção avaliada."],
                    "drawbacks": ["Exige revisão humana."],
                    "constraint_ids": ["constraint:0"] if scenario.constraints else [],
                }
                for index, name in enumerate(alternatives[:2])
            ],
            "decision": None if needs_clarification else alternatives[0],
            "rationale": rationale,
            "positive_consequences": ["Mantém a decisão explícita."],
            "negative_consequences": ["Requer validação humana."],
            "risks": [],
            "review_triggers": [
                {"metric": "latencia_p95", "operator": "gt", "threshold": 500, "unit": "ms"}
            ],
            "confidence": 0.5 if needs_clarification else 0.75,
            "reference_ids": [],
        }
        return GenerationResult(
            raw_output=json.dumps(payload, ensure_ascii=False),
            telemetry=GenerationTelemetry(latency_ms=int((perf_counter() - started) * 1000)),
        )

    async def repair(
        self,
        scenario: ScenarioRevision,
        raw_output: str,
        findings: list[dict[str, object]],
        *,
        cancellation: CancellationToken,
    ) -> GenerationResult:
        del raw_output, findings
        return await self.generate(scenario, cancellation=cancellation)

"""Lazy Transformers adapter for the pinned Qwen baseline."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from time import perf_counter

from adr_forge.scenarios.models import ScenarioRevision
from adr_forge.strategies.base import (
    GenerationResult,
    GenerationTelemetry,
    StructuredOutputStrategy,
    build_adr_prompt,
)
from adr_forge.system.progress import CancellationToken

QWEN_MODEL_ID = "Qwen/Qwen3-4B-Instruct-2507"


@dataclass(frozen=True, slots=True)
class QwenRuntime(StructuredOutputStrategy):
    revision: str = "main"
    max_new_tokens: int = 1024

    async def generate(
        self, scenario: ScenarioRevision, *, cancellation: CancellationToken
    ) -> GenerationResult:
        cancellation.raise_if_cancelled()
        return await asyncio.to_thread(
            self._generate_blocking, build_adr_prompt(scenario), cancellation
        )

    def _generate_blocking(self, prompt: str, cancellation: CancellationToken) -> GenerationResult:
        cancellation.raise_if_cancelled()
        try:
            from transformers import (  # type: ignore[import-not-found]
                AutoModelForCausalLM,
                AutoTokenizer,
                StoppingCriteria,
                StoppingCriteriaList,
            )
        except ImportError as error:
            raise RuntimeError("Qwen runtime requires the optional 'ml' dependencies.") from error
        tokenizer = AutoTokenizer.from_pretrained(
            QWEN_MODEL_ID, revision=self.revision, trust_remote_code=False
        )
        model = AutoModelForCausalLM.from_pretrained(
            QWEN_MODEL_ID, revision=self.revision, trust_remote_code=False
        )
        encoded = tokenizer(prompt, return_tensors="pt")
        cancellation.raise_if_cancelled()
        started = perf_counter()

        class _CancellationStoppingCriteria(StoppingCriteria):  # type: ignore[misc]
            def __call__(self, input_ids: object, scores: object, **kwargs: object) -> bool:
                return cancellation.is_cancelled

        output = model.generate(
            **encoded,
            max_new_tokens=self.max_new_tokens,
            stopping_criteria=StoppingCriteriaList([_CancellationStoppingCriteria()]),
        )
        text = tokenizer.decode(output[0][encoded.input_ids.shape[1] :], skip_special_tokens=True)
        cancellation.raise_if_cancelled()
        return GenerationResult(
            raw_output=text,
            telemetry=GenerationTelemetry(
                input_tokens=int(encoded.input_ids.shape[1]),
                output_tokens=int(output.shape[1] - encoded.input_ids.shape[1]),
                latency_ms=int((perf_counter() - started) * 1000),
            ),
        )

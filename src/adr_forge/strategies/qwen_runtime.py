"""Lazy Transformers adapter for the pinned Qwen baseline."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

from adr_forge.scenarios.models import ScenarioRevision
from adr_forge.shared.chat_prompt import render_assistant_prompt
from adr_forge.shared.model_identity import require_immutable_model_revision
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
    revision: str
    max_new_tokens: int = 1024
    adapter_path: Path | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "revision", require_immutable_model_revision(self.revision))

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
            from transformers import (
                AutoModelForCausalLM,
                AutoTokenizer,
                BitsAndBytesConfig,
                StoppingCriteriaList,
            )
        except ImportError as error:
            raise RuntimeError("Qwen runtime requires the optional 'ml' dependencies.") from error
        tokenizer = AutoTokenizer.from_pretrained(
            QWEN_MODEL_ID, revision=self.revision, trust_remote_code=False
        )
        quantization = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
        )
        model: Any = AutoModelForCausalLM.from_pretrained(
            QWEN_MODEL_ID,
            revision=self.revision,
            trust_remote_code=False,
            device_map="auto",
            quantization_config=quantization,
        )
        if self.adapter_path is not None:
            try:
                from peft import PeftModel
            except ImportError as error:
                raise RuntimeError(
                    "Qwen adapter runtime requires the optional 'ml' dependencies."
                ) from error
            model = PeftModel.from_pretrained(model, str(self.adapter_path))
        tokenized = tokenizer(render_assistant_prompt(tokenizer, prompt), return_tensors="pt")
        encoded = {name: value.to(model.device) for name, value in tokenized.items()}
        input_ids = encoded["input_ids"]
        cancellation.raise_if_cancelled()
        started = perf_counter()

        class _CancellationStoppingCriteria:
            def __call__(self, input_ids: object, scores: object, **kwargs: object) -> bool:
                return cancellation.is_cancelled

        output: Any = model.generate(
            **encoded,
            max_new_tokens=self.max_new_tokens,
            stopping_criteria=StoppingCriteriaList([_CancellationStoppingCriteria()]),
        )
        text = tokenizer.decode(output[0][input_ids.shape[1] :], skip_special_tokens=True)
        cancellation.raise_if_cancelled()
        return GenerationResult(
            raw_output=text,
            telemetry=GenerationTelemetry(
                input_tokens=int(input_ids.shape[1]),
                output_tokens=int(output.shape[1] - input_ids.shape[1]),
                latency_ms=int((perf_counter() - started) * 1000),
            ),
        )

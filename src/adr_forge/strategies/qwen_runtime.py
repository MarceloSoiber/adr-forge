"""Lazy Transformers adapter for the pinned Qwen baseline."""

from __future__ import annotations

import asyncio
import gc
from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter
from typing import Any

from adr_forge.scenarios.models import ScenarioRevision
from adr_forge.shared.adr_prompt import build_adr_repair_prompt
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


@dataclass(slots=True)
class QwenRuntime(StructuredOutputStrategy):
    revision: str
    max_new_tokens: int = 1024
    adapter_path: Path | None = None
    _tokenizer: Any | None = field(default=None, init=False, repr=False)
    _model: Any | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self.revision = require_immutable_model_revision(self.revision)

    async def generate(
        self, scenario: ScenarioRevision, *, cancellation: CancellationToken
    ) -> GenerationResult:
        cancellation.raise_if_cancelled()
        return await asyncio.to_thread(
            self._generate_blocking, build_adr_prompt(scenario), cancellation
        )

    async def repair(
        self,
        scenario: ScenarioRevision,
        raw_output: str,
        findings: list[dict[str, Any]],
        *,
        cancellation: CancellationToken,
    ) -> GenerationResult:
        return await asyncio.to_thread(
            self._generate_blocking,
            build_adr_repair_prompt(build_adr_prompt(scenario), raw_output, findings),
            cancellation,
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
        if self._tokenizer is None or self._model is None:
            self._tokenizer = AutoTokenizer.from_pretrained(
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
            self._model = model
        tokenizer = self._tokenizer
        model = self._model
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

    def close(self) -> None:
        """Release loaded model resources when a new analysis session starts."""
        self._model = None
        self._tokenizer = None
        gc.collect()
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass

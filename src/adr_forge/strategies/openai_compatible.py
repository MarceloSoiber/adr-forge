"""OpenAI-compatible local inference adapter (including LM Studio)."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any

import httpx

from adr_forge.scenarios.models import ScenarioRevision
from adr_forge.shared.adr_prompt import build_adr_repair_prompt
from adr_forge.strategies.base import (
    GenerationResult,
    GenerationTelemetry,
    build_adr_prompt,
)
from adr_forge.system.progress import CancellationToken


@dataclass(frozen=True, slots=True)
class OpenAICompatibleStrategy:
    """Generate structured ADR output through an explicitly configured endpoint."""

    base_url: str
    model_id: str
    timeout_seconds: int = 120
    api_key: str | None = None

    async def generate(
        self, scenario: ScenarioRevision, *, cancellation: CancellationToken
    ) -> GenerationResult:
        cancellation.raise_if_cancelled()
        return await self._complete(build_adr_prompt(scenario), cancellation=cancellation)

    async def repair(
        self,
        scenario: ScenarioRevision,
        raw_output: str,
        findings: list[dict[str, Any]],
        *,
        cancellation: CancellationToken,
    ) -> GenerationResult:
        return await self._complete(
            build_adr_repair_prompt(build_adr_prompt(scenario), raw_output, findings),
            cancellation=cancellation,
        )

    async def _complete(self, prompt: str, *, cancellation: CancellationToken) -> GenerationResult:
        cancellation.raise_if_cancelled()
        started = perf_counter()
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        payload = {
            "model": self.model_id,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "max_tokens": 1024,
            "stream": False,
        }
        endpoint = f"{self.base_url.rstrip('/')}/v1/chat/completions"
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(endpoint, json=payload, headers=headers)
            response.raise_for_status()
            document: dict[str, Any] = response.json()
            content = document["choices"][0]["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise ValueError("completion content is empty")
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            # Do not include response bodies: providers may reflect prompts or credentials.
            raise RuntimeError("OpenAI-compatible local inference failed") from exc
        cancellation.raise_if_cancelled()
        usage = document.get("usage", {})
        return GenerationResult(
            raw_output=content,
            telemetry=GenerationTelemetry(
                input_tokens=_usage_value(usage, "prompt_tokens"),
                output_tokens=_usage_value(usage, "completion_tokens"),
                latency_ms=int((perf_counter() - started) * 1000),
            ),
        )


def _usage_value(usage: Any, key: str) -> int | None:
    value = usage.get(key) if isinstance(usage, dict) else None
    return value if isinstance(value, int) and value >= 0 else None

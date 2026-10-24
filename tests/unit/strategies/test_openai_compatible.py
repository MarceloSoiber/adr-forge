"""Contract tests for the explicit OpenAI-compatible local runtime."""

from __future__ import annotations

import httpx
import pytest
import respx

from adr_forge.scenarios.models import DecisionCategory, DecisionScenario, ScenarioRevision
from adr_forge.strategies.openai_compatible import OpenAICompatibleStrategy
from adr_forge.system.progress import CancellationToken

BASE_URL = "http://192.168.15.111:1234"


def _scenario() -> ScenarioRevision:
    scenario = DecisionScenario(title="Persistência local")
    return ScenarioRevision(
        scenario_id=scenario.id,
        revision_number=1,
        problem="Precisamos escolher uma persistência transacional para o catálogo local.",
        facts=["O catálogo possui relações entre produtos e estoque."],
        constraints=["A avaliação deve permanecer local."],
        categories=[DecisionCategory.SQL_VS_NOSQL],
        candidate_alternatives=["PostgreSQL", "MongoDB"],
    )


@pytest.mark.asyncio
@respx.mock
async def test_openai_compatible_runtime_posts_structured_request_and_maps_usage() -> None:
    route = respx.post(f"{BASE_URL}/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"title": "ADR"}'}}],
                "usage": {"prompt_tokens": 17, "completion_tokens": 9},
            },
        )
    )
    result = await OpenAICompatibleStrategy(
        base_url=BASE_URL, model_id="qwen_qwen3-4b-instruct-2507"
    ).generate(_scenario(), cancellation=CancellationToken())

    assert result.raw_output == '{"title": "ADR"}'
    assert result.telemetry.input_tokens == 17
    assert result.telemetry.output_tokens == 9
    request = route.calls[0].request
    assert request.content
    assert b'"model":"qwen_qwen3-4b-instruct-2507"' in request.content
    assert b'"stream":false' in request.content


@pytest.mark.asyncio
@respx.mock
async def test_openai_compatible_runtime_hides_provider_response_details_on_failure() -> None:
    respx.post(f"{BASE_URL}/v1/chat/completions").mock(
        return_value=httpx.Response(503, text="prompt-and-token-must-not-leak")
    )

    with pytest.raises(RuntimeError, match="OpenAI-compatible local inference failed") as error:
        await OpenAICompatibleStrategy(base_url=BASE_URL, model_id="qwen").generate(
            _scenario(), cancellation=CancellationToken()
        )
    assert "prompt-and-token" not in str(error.value)


@pytest.mark.asyncio
async def test_openai_compatible_runtime_honours_preexisting_cancellation() -> None:
    cancellation = CancellationToken()
    cancellation.request_cancel()

    with pytest.raises(InterruptedError):
        await OpenAICompatibleStrategy(base_url=BASE_URL, model_id="qwen").generate(
            _scenario(), cancellation=cancellation
        )


@pytest.mark.asyncio
@respx.mock
async def test_openai_compatible_runtime_sends_raw_output_and_findings_for_one_repair() -> None:
    route = respx.post(f"{BASE_URL}/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"title": "ADR"}'}}]},
        )
    )

    await OpenAICompatibleStrategy(base_url=BASE_URL, model_id="qwen").repair(
        _scenario(),
        '{"status":"provisional","unresolved_questions":[]}',
        [
            {
                "code": "unresolved_questions.required",
                "path": "/unresolved_questions",
                "severity": "error",
                "message": "A provisional ADR requires one to three unresolved questions.",
            }
        ],
        cancellation=CancellationToken(),
    )

    content = route.calls[0].request.content.decode()
    assert "unresolved_questions.required" in content
    assert "nunca retorne unresolved_questions vazio" in content
    assert '"id\\\":\\\"pergunta-1\\\"' in content

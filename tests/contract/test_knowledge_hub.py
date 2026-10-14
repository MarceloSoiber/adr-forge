"""Contract coverage for the bounded Knowledge Hub retrieval adapter."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from adr_forge.retrieval.knowledge_hub import KnowledgeHubClient, KnowledgeHubError
from adr_forge.retrieval.models import RetrievalFilters, RetrievalRequest

BASE_URL = "http://knowledge-hub.test"
TOKEN = "secret-token"  # noqa: S105 - controlled fake credential for redaction coverage


async def _no_sleep(_: float) -> None:
    return None


def _payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "query": "Quais restrições favorecem processamento assíncrono?",
        "limit": 8,
        "provider_version": "knowledge-hub-search-v1",
        "embedding": {"model": "pinned-embedding-model", "version": "revision-1"},
        "results": [
            {
                "id": 42,
                "source_id": "source-uuid",
                "source_title": "Architecture reference",
                "source_type": "document",
                "uri": "local://reference",
                "location": {"chunk_index": 3, "page": 7, "section": "Trade-offs"},
                "content": "Exact retrieved text",
                "score": 0.82,
                "metadata": {},
                "match_reasons": ["vector", "text"],
            }
        ],
    }
    payload.update(overrides)
    return payload


def _request() -> RetrievalRequest:
    return RetrievalRequest(
        query="Quais restrições favorecem processamento assíncrono?",
        filters=RetrievalFilters(limit=8, category_ids=[1]),
    )


@pytest.mark.asyncio
@respx.mock
async def test_search_sends_closed_request_and_returns_validated_provider_response() -> None:
    route = respx.post(f"{BASE_URL}/api/v1/knowledge/search").mock(
        return_value=httpx.Response(200, json=_payload())
    )
    async with httpx.AsyncClient() as http_client:
        result = await KnowledgeHubClient(
            http_client=http_client, base_url=BASE_URL, bearer_token=TOKEN
        ).search(_request())

    assert route.called
    sent = route.calls.last.request
    assert sent.headers["Authorization"] == f"Bearer {TOKEN}"
    assert json.loads(sent.content) == {
        "query": _request().query,
        "limit": 8,
        "category_ids": [1],
        "tag_ids": None,
        "project_ids": None,
        "min_score": None,
        "include_match_reasons": True,
    }
    assert result.provider_version == "knowledge-hub-search-v1"
    assert result.embedding.model == "pinned-embedding-model"
    assert result.results[0].score == pytest.approx(0.82)


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [408, 429, 500, 503])
@respx.mock
async def test_search_retries_exactly_once_for_retryable_statuses(status: int) -> None:
    route = respx.post(f"{BASE_URL}/api/v1/knowledge/search").mock(
        side_effect=[httpx.Response(status), httpx.Response(200, json=_payload())]
    )
    async with httpx.AsyncClient() as http_client:
        result = await KnowledgeHubClient(
            http_client=http_client,
            base_url=BASE_URL,
            bearer_token=TOKEN,
            sleep=_no_sleep,
            jitter=lambda: 0,
        ).search(_request())

    assert result.results
    assert route.call_count == 2


@pytest.mark.asyncio
@respx.mock
async def test_search_retries_one_connect_failure_without_leaking_bearer_token() -> None:
    route = respx.post(f"{BASE_URL}/api/v1/knowledge/search").mock(
        side_effect=[httpx.ConnectError("connection refused"), httpx.Response(200, json=_payload())]
    )
    async with httpx.AsyncClient() as http_client:
        result = await KnowledgeHubClient(
            http_client=http_client,
            base_url=BASE_URL,
            bearer_token=TOKEN,
            sleep=_no_sleep,
            jitter=lambda: 0,
        ).search(_request())

    assert result.results
    assert route.call_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [400, 401, 403, 404])
@respx.mock
async def test_search_does_not_retry_auth_or_other_non_retryable_client_failures(
    status: int,
) -> None:
    route = respx.post(f"{BASE_URL}/api/v1/knowledge/search").mock(
        return_value=httpx.Response(status, json={"detail": f"token={TOKEN}"})
    )
    async with httpx.AsyncClient() as http_client:
        with pytest.raises(KnowledgeHubError) as raised:
            await KnowledgeHubClient(
                http_client=http_client, base_url=BASE_URL, bearer_token=TOKEN
            ).search(_request())

    assert route.call_count == 1
    assert TOKEN not in str(raised.value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid_response",
    [
        b"not-json",
        _payload(provider_version=None),
        _payload(embedding={"model": "only-model"}),
        _payload(results=[{**_payload()["results"][0], "content": None}]),  # type: ignore[index]
        (
            b'{"provider_version":"knowledge-hub-search-v1",'
            b'"embedding":{"model":"pinned-embedding-model","version":"revision-1"},'
            b'"results":[{"id":42,"source_id":"source-uuid",'
            b'"source_title":"Architecture reference","source_type":"document",'
            b'"uri":"local://reference","location":{"chunk_index":3},'
            b'"content":"Exact retrieved text","score":Infinity,"metadata":{},'
            b'"match_reasons":[]}]}'
        ),
    ],
)
@respx.mock
async def test_search_fails_closed_on_malformed_or_incomplete_provider_payload(
    invalid_response: bytes | dict[str, object],
) -> None:
    route = respx.post(f"{BASE_URL}/api/v1/knowledge/search")
    if isinstance(invalid_response, bytes):
        route.mock(return_value=httpx.Response(200, content=invalid_response))
    else:
        route.mock(return_value=httpx.Response(200, json=invalid_response))

    async with httpx.AsyncClient() as http_client:
        with pytest.raises(KnowledgeHubError):
            await KnowledgeHubClient(
                http_client=http_client, base_url=BASE_URL, bearer_token=TOKEN
            ).search(_request())

    assert route.call_count == 1


@pytest.mark.asyncio
@respx.mock
async def test_search_fails_when_one_retry_cannot_fit_inside_total_deadline() -> None:
    route = respx.post(f"{BASE_URL}/api/v1/knowledge/search").mock(
        return_value=httpx.Response(429, headers={"Retry-After": "20"})
    )
    async with httpx.AsyncClient() as http_client:
        with pytest.raises(KnowledgeHubError, match="deadline"):
            await KnowledgeHubClient(
                http_client=http_client,
                base_url=BASE_URL,
                bearer_token=TOKEN,
                clock=iter([0.0, 0.0, 15.0]).__next__,
                sleep=_no_sleep,
                jitter=lambda: 0,
            ).search(_request())

    assert route.call_count == 1

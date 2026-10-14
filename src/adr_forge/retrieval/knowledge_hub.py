"""Fail-closed HTTP adapter for the Knowledge Hub search projection."""

from __future__ import annotations

import asyncio
import json
import random
import time
from collections.abc import Awaitable, Callable
from inspect import isawaitable
from typing import Any

import httpx

from adr_forge.retrieval.models import (
    EmbeddingIdentity,
    RetrievalChunk,
    RetrievalFilters,
    RetrievalRequest,
    RetrievalSnapshot,
)
from adr_forge.shared.config import Settings
from adr_forge.shared.errors import PreconditionFailedError


class KnowledgeHubError(Exception):
    """Sanitized integration failure; it never includes bearer credentials."""


class KnowledgeHubClient:
    def __init__(
        self,
        *,
        http_client: httpx.AsyncClient,
        base_url: str,
        bearer_token: str,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None] | None] = asyncio.sleep,
        jitter: Callable[[], float] = random.random,
    ) -> None:
        self._client, self._base_url, self._token = http_client, base_url.rstrip("/"), bearer_token
        self._clock, self._sleep, self._jitter = clock, sleep, jitter

    async def search(self, request: RetrievalRequest) -> RetrievalSnapshot:
        started = self._clock()
        payload = {"query": request.query, **request.filters.model_dump(mode="json")}
        for attempt in range(2):
            try:
                response = await self._client.post(
                    f"{self._base_url}/api/v1/knowledge/search",
                    json=payload,
                    headers={"Authorization": f"Bearer {self._token}"},
                    timeout=httpx.Timeout(15, connect=2),
                )
                if response.status_code in {408, 429} or response.status_code >= 500:
                    if attempt == 0:
                        retry_after = float(response.headers.get("Retry-After", "0"))
                        if retry_after >= 15 - (self._clock() - started):
                            raise KnowledgeHubError("Knowledge Hub retry exceeds deadline")
                        await self._pause(
                            min(0.5 + self._jitter() * 0.5, 15 - (self._clock() - started))
                        )
                        continue
                    raise KnowledgeHubError("Knowledge Hub unavailable")
                if response.status_code >= 400:
                    raise KnowledgeHubError(
                        f"Knowledge Hub rejected request ({response.status_code})"
                    )
                return self._parse(response.json(), request)
            except (httpx.ConnectError, httpx.TimeoutException):
                if attempt == 0:
                    await self._pause(0)
                    continue
                raise KnowledgeHubError("Knowledge Hub connection failed") from None
            except (ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
                raise KnowledgeHubError("Knowledge Hub returned invalid response") from error
        raise KnowledgeHubError("Knowledge Hub unavailable")

    async def _pause(self, delay: float) -> None:
        result = self._sleep(delay)
        if isawaitable(result):
            await result

    @staticmethod
    def _parse(payload: Any, request: RetrievalRequest) -> RetrievalSnapshot:
        results = payload["results"]
        return RetrievalSnapshot(
            provider="knowledge_hub",
            provider_version=payload["provider_version"],
            query=request.query,
            filters=request.filters,
            embedding_model=payload["embedding"]["model"],
            embedding_version=payload["embedding"]["version"],
            chunks=[RetrievalChunk(rank=index + 1, **item) for index, item in enumerate(results)],
        )


class KnowledgeHubProvider:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._client = client

    async def retrieve(
        self, query: str, *, filters: RetrievalFilters | None = None
    ) -> RetrievalSnapshot:
        selected = filters or RetrievalFilters()
        payload = {"query": query, **selected.model_dump(mode="json")}
        headers: dict[str, str] = {}
        if self._settings.knowledge_hub_token is not None:
            headers["Authorization"] = (
                f"Bearer {self._settings.knowledge_hub_token.get_secret_value()}"
            )
        timeout = httpx.Timeout(15.0, connect=2.0)
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=timeout)
        started = time.monotonic()
        try:
            for attempt in range(2):
                try:
                    response = await client.post(
                        "/api/v1/knowledge/search", json=payload, headers=headers
                    )
                    if response.status_code in {408, 429} or response.status_code >= 500:
                        if attempt == 0:
                            await self._backoff(started)
                            continue
                        raise PreconditionFailedError("Knowledge Hub is temporarily unavailable.")
                    response.raise_for_status()
                    return self._parse(response.json(), query, selected)
                except (httpx.ConnectError, httpx.TimeoutException):
                    if attempt == 0:
                        await self._backoff(started)
                        continue
                    raise PreconditionFailedError("Knowledge Hub request timed out.") from None
                except httpx.HTTPStatusError as error:
                    raise PreconditionFailedError(
                        f"Knowledge Hub rejected the request ({error.response.status_code})."
                    ) from None
        finally:
            if owns_client:
                await client.aclose()
        raise AssertionError("unreachable")

    async def _backoff(self, started: float) -> None:
        remaining = 15.0 - (time.monotonic() - started)
        delay = min(0.25 + random.random() * 0.25, max(0.0, remaining))  # noqa: S311
        if delay <= 0:
            raise PreconditionFailedError("Knowledge Hub request timed out.")
        await asyncio.sleep(delay)

    @staticmethod
    def _parse(payload: Any, query: str, filters: RetrievalFilters) -> RetrievalSnapshot:
        try:
            embedding = EmbeddingIdentity.model_validate(payload["embedding"])
            results = payload["results"]
            if not isinstance(results, list) or not results:
                raise ValueError("results must be a non-empty list")
            chunks = [RetrievalChunk(rank=index + 1, **item) for index, item in enumerate(results)]
            return RetrievalSnapshot(
                provider="knowledge_hub",
                provider_version=str(payload["provider_version"]),
                query=query,
                filters=filters,
                embedding_model=embedding.model,
                embedding_version=embedding.version,
                chunks=chunks,
            )
        except (KeyError, TypeError, ValueError) as error:
            raise PreconditionFailedError(
                "Knowledge Hub returned an invalid retrieval response."
            ) from error

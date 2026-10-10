# Knowledge Hub Retrieval Contract

## Purpose

ADR Forge uses Knowledge Hub only to retrieve evidence. It does not call Knowledge Hub answer
generation, so the ADR Forge model, prompt, schema, and strategy remain controlled variables.

## Endpoint

```http
POST {KNOWLEDGE_HUB_BASE_URL}/api/v1/knowledge/search
Authorization: Bearer {KNOWLEDGE_HUB_TOKEN}
Content-Type: application/json
```

## Request

```json
{
  "query": "Quais restrições favorecem processamento assíncrono?",
  "limit": 8,
  "category_ids": [1],
  "tag_ids": null,
  "project_ids": null,
  "min_score": null,
  "include_match_reasons": true
}
```

Rules inherited from Knowledge Hub:

- `query` is non-empty.
- `limit` is between 1 and 50.
- Score filters are between 0.0 and 1.0.
- Category, tag, and project identifiers are positive integers when present.

## Required Response Projection

```json
{
  "query": "...",
  "limit": 8,
  "results": [
    {
      "id": 42,
      "source_id": "source-uuid",
      "source_title": "Architecture reference",
      "source_type": "document",
      "uri": "local://...",
      "location": {
        "chunk_index": 3,
        "page": 7,
        "section": "Trade-offs"
      },
      "content": "Exact retrieved text",
      "score": 0.82,
      "metadata": {},
      "match_reasons": ["vector", "text"]
    }
  ]
}
```

ADR Forge ignores unknown additional fields but fails closed when a required identity, location, or
content field is absent.

## Timeout and Retry

- Connect timeout: 2 seconds.
- Total request timeout: 15 seconds.
- Retry count: one.
- Retry only connection failures, 408, 429, and 5xx responses.
- Use bounded exponential backoff with jitter.
- Never retry 400, 401, 403, 404, or schema-invalid responses.

## Failure Behavior

- Mark the Knowledge Hub integration unavailable with a sanitized reason.
- Disable RAG-dependent strategies for that operation.
- Keep non-RAG strategies available.
- Never replace missing retrieval with an empty context while labeling the run as RAG.
- Never include the bearer token in errors, logs, run artifacts, or diagnostics.

## Snapshot Rules

One successful response is canonicalized and written as an immutable retrieval snapshot before any
comparable strategy runs. The snapshot records request, ordered results, exact content, ranks,
scores, source locations, match reasons, embedding identity when available, provider version,
timestamp, and SHA-256 hashes. Every RAG-enabled run in the experiment references that snapshot.

## Test Contract

Contract tests use captured, reviewed fixtures and an HTTP mock. Live Knowledge Hub tests are
opt-in integration tests and MUST NOT run in default CI.

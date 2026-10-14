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
  "provider_version": "knowledge-hub-search-v1",
  "embedding": {
    "model": "pinned-embedding-model",
    "version": "immutable-revision"
  },
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

ADR Forge ignores unknown additional fields but fails closed when a required provider, embedding,
source/chunk identity, location, finite score, rankable result, or content field is absent. A
deployment whose Knowledge Hub version does not return provider and embedding identity must supply
those values through pinned, validated integration configuration; ADR Forge never guesses them.

## Timeout and Retry

- Connect timeout: 2 seconds.
- Total wall-clock budget: 15 seconds across both attempts and their backoff.
- Retry count: one.
- Retry only connection failures, 408, 429, and 5xx responses.
- Use bounded exponential backoff with jitter.
- Never retry 400, 401, 403, 404, or schema-invalid responses.
- Honor `Retry-After` only when it fits inside the remaining total budget; otherwise fail with a
  sanitized timeout reason.

## Failure Behavior

- Mark the Knowledge Hub integration unavailable with a sanitized reason.
- Disable RAG-dependent strategies for that operation.
- Keep non-RAG strategies available.
- Never replace missing retrieval with an empty context while labeling the run as RAG.
- Never include the bearer token in errors, logs, run artifacts, or diagnostics.

## Snapshot Rules

One successful response is canonicalized and written as an immutable retrieval snapshot before any
comparable strategy runs. The versioned canonical document records the normalized request,
provider and embedding identity, and ordered results with exact content, ranks, finite scores,
source locations, ordered match reasons, and per-chunk SHA-256 hashes. Every RAG-enabled run in the
comparison cohort references that snapshot.

The snapshot `content_hash` includes the canonical schema version, provider/embedding identity,
query, filters, and every ordered chunk field. It excludes the snapshot/database ID, artifact path,
and creation timestamp. Equal hashes must have byte-identical canonical JSON; otherwise ADR Forge
reports an integrity failure rather than reusing the row.

## Test Contract

Contract tests use captured, reviewed fixtures and an HTTP mock. Live Knowledge Hub tests are
opt-in integration tests and MUST NOT run in default CI.

# ADR-004 — Reuse Knowledge Hub search through REST

- Status: accepted
- Date: 2026-10-10
- Decisors: Marcelo Soiber

## Context

Knowledge Hub already provides authenticated hybrid search, pgvector, source metadata, filters, and
local embeddings.

## Decision

Implement a retrieval port whose live adapter calls `POST /api/v1/knowledge/search`. ADR Forge owns
generation and does not call Knowledge Hub answer generation.

## Alternatives considered

- Duplicate retrieval inside ADR Forge: unnecessary ownership and drift.
- MCP as primary contract: more protocol surface for one fixed operation.
- Knowledge Hub answer endpoint: confounds generator and prompt comparisons.

## Consequences

RAG strategies depend on Knowledge Hub availability and a bearer token, while non-RAG strategies
continue independently. Contract tests require captured response fixtures.

## Review triggers

Add an MCP adapter when agent interoperability is itself a tested requirement. Extract a shared
package only after repeated code-level reuse appears.

# ADR-005 — Freeze retrieval snapshots for comparative experiments

- Status: accepted
- Date: 2026-10-10
- Decisors: Marcelo Soiber

## Context

Live retrieval can change after content edits, reindexing, embedding updates, or ranking changes.

## Decision

Retrieve once and persist exact ordered content, source locations, scores, match reasons, query,
filters, provider/embedding versions, timestamp, and hashes. Comparable RAG strategies receive the
same snapshot.

## Alternatives considered

- Retrieve independently per strategy: experimentally unfair.
- Save source IDs only: does not reproduce mutable content.

## Consequences

Experiments use more local storage and snapshots may contain sensitive text; only authorized public
snapshots may be published.

## Review triggers

Revisit storage representation when snapshots dominate the 50 GB budget or a content-addressed
shared snapshot store becomes necessary.

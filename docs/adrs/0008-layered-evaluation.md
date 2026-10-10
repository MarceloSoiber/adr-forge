# ADR-008 — Use layered evaluation with blind human authority

- Status: accepted
- Date: 2026-10-10
- Decisors: Marcelo Soiber

## Context

ADR structure has objective properties, but architectural judgment cannot be reduced to exact text
or an unvalidated judge model.

## Decision

Use shared deterministic validators, blinded human rubric evaluation, and optional labeled
LLM-assisted evaluation. Human review is authoritative for nuanced comparison.

## Alternatives considered

- Exact snapshots: penalize valid wording variation.
- LLM judge only: bias and weak ground truth.
- Human review only: too slow for regression feedback.

## Consequences

The UI must preserve blinding and evaluation immutability. Reports show disagreements and judge
identity rather than collapsing them into one opaque score.

## Review triggers

Revise rubric weights and anchors when inter-rater agreement remains low across a meaningful sample.

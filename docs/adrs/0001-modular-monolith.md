# ADR-001 — Use a local-first modular monolith

- Status: accepted
- Date: 2026-10-10
- Decisors: Marcelo Soiber

## Context

ADR Forge has one user, one GPU, one owner, and shared domain rules across web and CLI workflows.

## Decision

Use one Python application package with capability modules, FastAPI and Typer delivery adapters,
and a separate React build containing no domain policy.

## Alternatives considered

- Notebook-only: insufficient contracts and product demonstration.
- Microservices: no independent ownership, scale, or deployment need.
- Multiple Python services: extra failure and synchronization modes without value.

## Consequences

Deployment and local operation stay simple; module discipline must be enforced through imports and
tests. A long GPU task can affect the single process, so training remains CLI-only.

## Review triggers

Extract a component only when it needs independent deployment, ownership, scaling, or failure
isolation demonstrated by measurements or repeated incidents.

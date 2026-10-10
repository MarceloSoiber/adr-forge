# ADR-009 — Bind the MVP to localhost without authentication

- Status: accepted
- Date: 2026-10-10
- Decisors: Marcelo Soiber

## Context

One trusted local user operates the MVP. Authentication would not address the dominant dataset,
model, artifact, and retrieval threats.

## Decision

Bind API and web to loopback, restrict CORS, keep integration tokens in the environment, and treat
any non-loopback exposure as unsupported without authentication and TLS.

## Alternatives considered

- Token authentication now: cost without a remote client.
- LAN binding without authentication: unacceptable exposure.

## Consequences

Remote VM testing uses fake/snapshot workflows until a separate deployment decision adds identity,
TLS, secrets, backup, and rollback.

## Review triggers

Any request for LAN, VM, shared, or public access requires a superseding ADR before implementation.

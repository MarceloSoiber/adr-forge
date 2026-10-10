# ADR-007 — Run GPU workflows natively and automation CPU-safe

- Status: accepted
- Date: 2026-10-10
- Decisors: Marcelo Soiber

## Context

The project prioritizes learning and local iteration. Containerized CUDA adds driver and cache
complexity, while shared CI and the future GitLab VM have no confirmed GPU.

## Decision

Use `uv` native Python environments for API, inference, training, and benchmarks. Build Docker
artifacts for CPU reproduction and run fakes/snapshots in CI.

## Alternatives considered

- GPU container first: higher setup cost without a second training host.
- Live model in default CI: unavailable, slow, and nondeterministic.

## Consequences

Lockfiles and environment diagnostics are critical. GPU validation remains an explicit local gate.

## Review triggers

Containerize GPU training when a second machine or confirmed GPU runner must reproduce the run.

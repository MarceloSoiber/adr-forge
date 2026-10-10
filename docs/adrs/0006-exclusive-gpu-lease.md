# ADR-006 — Treat the GPU as an exclusive leased resource

- Status: accepted
- Date: 2026-10-10
- Decisors: Marcelo Soiber

## Context

The workstation has 12 GB VRAM and LM Studio GPT-OSS can consume most of it. Concurrent Qwen work
would fail unpredictably or offload excessively.

## Decision

Permit one ADR Forge GPU workload after preflight and exclusive lease acquisition. Report blockers
and active processes, but never kill or unload external processes automatically.

## Alternatives considered

- Optimistic concurrent loading: unstable and hard to reproduce.
- Automatic process termination: destructive and outside application authority.
- GPU broker service: unjustified for one user.

## Consequences

Work is sequential and queued. Training requires GPT-OSS to be unloaded; Knowledge Hub retrieval
continues with CPU embeddings.

## Review triggers

Add a resource scheduler only when multiple GPUs, multiple users, or concurrent experiment demand
is confirmed.

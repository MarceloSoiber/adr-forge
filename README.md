# ADR Forge

ADR Forge is a fine-tuning laboratory for architecture decision analysis and Architecture Decision Record (ADR) generation.

The project investigates whether a fine-tuned language model can produce more consistent, traceable, and useful ADR drafts than prompting or retrieval alone. It is designed for experienced software architects and keeps final decision accountability with the human reviewer.

## Initial scope

- SQL versus NoSQL
- Synchronous versus asynchronous processing
- Modular monolith versus microservices
- Containers versus serverless versus traditional execution

The laboratory will compare baseline, structured-prompt, retrieval-assisted, fine-tuned, and hybrid strategies using reproducible benchmarks, deterministic validation, and blind human evaluation.

## Status

Early design phase. The initial product specification is available in [`specs/001-architecture-decision-lab/spec.md`](specs/001-architecture-decision-lab/spec.md).

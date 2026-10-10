# Implementation Plan: Architecture Decision Lab

**Branch**: `main` | **Date**: 2026-10-10 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-architecture-decision-lab/spec.md`

## Summary

Build ADR Forge as a local-first modular monolith for experienced architects. A React client and
FastAPI API share a Python application core with a Typer CLI. The system versions scenarios,
generates structured ADR drafts through pluggable analysis strategies, reuses the existing
Knowledge Hub search API for RAG, freezes retrieval snapshots for fair comparisons, fine-tunes
Qwen3-4B-Instruct-2507 with QLoRA, and evaluates outputs through deterministic checks and blind
human review. SQLite stores local metadata; Git versions public datasets and manifests; large or
private artifacts remain in a local filesystem catalog.

## Technical Context

**Language/Version**: Python 3.12; TypeScript 5.x

**Primary Dependencies**: FastAPI, Pydantic, SQLAlchemy, Alembic, Typer, httpx, Transformers,
Datasets, TRL, PEFT, bitsandbytes, Accelerate, PyTorch; React, Vite, TanStack Query

**Storage**: SQLite in WAL mode for metadata; local filesystem for models and run artifacts; Git
for public datasets, manifests, rubrics, configurations, and published reports; existing Knowledge
Hub PostgreSQL/pgvector for retrieval

**Testing**: Pytest, pytest-asyncio, Hypothesis, respx; Vitest, Testing Library, Playwright;
GPU-dependent Pytest marker excluded from default CI

**Target Platform**: Ubuntu Linux workstation, one local user, NVIDIA RTX 3060 with 12 GB VRAM;
future CPU-only GitLab test VM

**Project Type**: Local web application plus CLI and ML experimentation pipeline

**Performance Goals**: Acknowledge analysis creation within 1 second; expose continuous progress;
allow long local inference with a documented initial p95 target of 90 seconds rather than a hard
timeout; run deterministic validation reproducibly; retrieve Knowledge Hub context within 15
seconds including one transient retry

**Constraints**: Localhost only; no authentication in MVP; one exclusive GPU workload; 50 GB
artifact budget with warning at 40 GB; QLoRA rather than full-parameter tuning; no live model
requirement in default CI; no proprietary, personal, payment, employer-confidential, or production
data in public artifacts

**Scale/Scope**: One concurrent user and GPU run; 100 initial reviewed examples balanced across
four categories; support up to 5,000 examples and 100 scenarios per standard benchmark; five
analysis strategy types; Brazilian Portuguese UI and datasets

## Constitution Check

*GATE: Passed before Phase 0 research and re-checked after Phase 1 design.*

| Principle | Design evidence | Status |
| --- | --- | --- |
| Evidence Before Claims | Versioned scenario facts, assumptions, questions, references, alternatives, confidence, and review triggers are first-class data | PASS |
| Reproducible and Honest Experiments | Immutable runs, raw output preservation, frozen retrieval snapshots, pinned revisions, and complete failure accounting | PASS |
| Dataset Integrity and Human Review | Provenance, review workflow, immutable published versions, and contamination checks are modeled | PASS |
| Contracts and Tests | OpenAPI, CLI, state-machine, retrieval contracts, shared deterministic validators, and explicit test layers | PASS |
| Local-First Security and Resource Safety | Localhost binding, secret isolation, untrusted retrieval content, GPU preflight, exclusive lease, and explicit cleanup | PASS |
| Simplicity With Measured Evolution | Modular monolith, SQLite, filesystem artifacts, native GPU execution, and no broker or separate vector database | PASS |

Post-design review found no constitutional violations. The React application is a client artifact,
not a second backend; all business rules remain in the Python application core. The external
Knowledge Hub is reused behind one port because rebuilding its retrieval stack would duplicate an
existing owned capability.

## Project Structure

### Documentation (this feature)

```text
specs/001-architecture-decision-lab/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── api.openapi.yaml
│   ├── cli.md
│   └── knowledge-hub.md
└── tasks.md
```

### Source Code (repository root)

```text
apps/
├── api/
│   └── main.py
└── web/
    ├── package.json
    └── src/
        ├── app/
        ├── components/
        ├── features/
        ├── pages/
        └── services/

src/adr_forge/
├── scenarios/
├── decisions/
├── strategies/
├── retrieval/
├── datasets/
├── training/
├── experiments/
├── evaluation/
├── artifacts/
├── system/
├── persistence/
├── api/
├── cli/
└── shared/

datasets/
├── public/
├── fixtures/
├── manifests/
└── schemas/

configs/
├── models/
├── training/
└── evaluation/

tests/
├── unit/
├── contract/
├── integration/
├── benchmark/
└── fixtures/

docs/
├── architecture/
├── adrs/
└── experiments/

var/                       # ignored: databases, models, adapters, caches, private artifacts
```

**Structure Decision**: Use one Python package for domain, application, infrastructure ports, API,
and CLI so the browser and CLI share the same use cases. Keep the React client under `apps/web`
because it has an independent build toolchain, not because it owns business logic. Modules are
organized by capability; infrastructure implementations depend inward on typed ports.

## Module Boundaries

| Module | Owns | May depend on |
| --- | --- | --- |
| `scenarios` | Scenario identity, revisions, facts, constraints, clarification answers | `shared` |
| `decisions` | ADR schema, rendering, structural validation | `scenarios`, `shared` |
| `strategies` | Strategy registry and orchestration ports | `decisions`, `retrieval`, `system` |
| `retrieval` | Knowledge Hub adapter and immutable snapshots | `shared` |
| `datasets` | Examples, provenance, splits, review, contamination | `scenarios`, `decisions`, `shared` |
| `training` | SFT/QLoRA configuration and execution | `datasets`, `artifacts`, `system` |
| `experiments` | Immutable run and experiment lifecycle | `strategies`, `datasets`, `evaluation` |
| `evaluation` | Deterministic rules, rubrics, blind comparisons | `decisions`, `experiments` |
| `artifacts` | Artifact metadata, hashes, quotas, safe paths | `shared` |
| `system` | GPU preflight, exclusive lease, progress, health | `shared` |
| `persistence` | SQLAlchemy repositories and transaction boundaries | All domain ports, never domain policy |
| `api` / `cli` | Input/output adapters | Application use cases only |

## Runtime Topology

- The API process owns a single in-process inference executor guarded by an async GPU semaphore.
- Blocking model work runs outside the event loop and emits persisted status snapshots plus
  best-effort server-sent progress events.
- Cancellation is cooperative. A cancelled run remains immutable and records partial artifacts.
- Training and full benchmarks run through the CLI as separate foreground processes after GPU
  preflight. They do not run inside HTTP requests.
- On API startup, any metadata run left in `running` becomes `interrupted`.
- The Knowledge Hub may remain running, but GPT-OSS must be unloaded before Qwen inference or
  training. Query embeddings should run on CPU.

## Data and Transaction Boundaries

- Creating a scenario and its first revision is one transaction.
- Adding clarification answers creates a new immutable scenario revision in one transaction.
- Creating a run reserves identity and initial status in one transaction; model execution is
  outside the transaction; terminal state and artifact references commit atomically.
- Publishing a dataset version validates provenance, review state, partition contamination, and
  manifest hashes before one immutable publication transaction.
- Submitting a blind evaluation records scores and preference before strategy identities can be
  revealed.
- Files are written to a temporary location, hashed, atomically moved into the artifact store, and
  only then referenced by committed metadata.

## Interfaces

- REST and SSE contracts are defined in `contracts/api.openapi.yaml`.
- CLI commands and exit semantics are defined in `contracts/cli.md`.
- The Knowledge Hub request, response, retry, snapshot, and failure contract is defined in
  `contracts/knowledge-hub.md`.
- ADR, dataset, rubric, and training configuration schemas are versioned under `datasets/schemas`
  and `configs` during implementation.

## Testing Strategy

1. Unit and property tests cover state transitions, invariants, hashing, schema validation,
   contamination, scoring, and artifact path safety without I/O.
2. Repository integration tests use temporary SQLite databases with migrations applied.
3. Contract tests validate OpenAPI payloads, Knowledge Hub responses through respx, CLI exit codes,
   and SSE state snapshots.
4. Frontend component tests cover scenario input, progress, ADR display, and blind evaluation;
   Playwright covers one fake-model vertical slice.
5. Snapshot benchmarks use stored retrieval and model outputs to verify deterministic evaluation.
6. Tests marked `gpu` run manually and record hardware, model revision, parameters, duration, and
   peak VRAM.

## Security and Privacy

- Bind API and web development server to `127.0.0.1` by default.
- Reject non-loopback production-style binding unless authentication and TLS are explicitly added.
- Load the Knowledge Hub bearer token and optional Hugging Face token from environment variables;
  redact known secret fields from logs and diagnostic output.
- Treat retrieved text as untrusted quoted evidence; never concatenate it into privileged
  instructions or execute tools from it.
- Enforce request, context, token, artifact-path, and upload-size limits.
- Default model loading to safe tensor formats and `trust_remote_code=false`; pin model revision.
- Scan Git history candidates for secrets and public datasets for suspected sensitive data.

## Observability and Recovery

- Structured logs include `run_id`, `experiment_id`, stage, duration, strategy version, and
  sanitized error class; full prompts and retrieved content are excluded by default.
- Persist run stage, timestamps, token counts, latency, validation status, and available GPU
  telemetry.
- The UI reconnects to SSE by first reading current run state; event delivery itself is not a
  durable queue.
- Git provides zero-RPO recovery after commit for public datasets and configuration. SQLite and
  private experiment metadata target daily backup, RPO 24 hours, and RTO 4 hours.
- Artifact deletion is explicit and two-step: remove logical references, then prune unreferenced
  files after confirmation.

## Delivery and Evolution

- GitHub Actions is the initial CPU-only CI. The future GitLab VM repeats CPU-safe gates and runs
  snapshot/fake-model smoke tests.
- Docker builds package the API and web client for reproducibility; native host execution remains
  the supported GPU path.
- Add authentication and TLS before any non-loopback exposure.
- Add an external worker only when the web UI can initiate long-running training or concurrent
  jobs are required.
- Move metadata to PostgreSQL only when multiple writers or users make SQLite contention visible.
- Add a dedicated vector store only after 50,000 reference chunks, retrieval over 500 ms, or
  complex concurrent filtering.

## Complexity Tracking

No constitution violations or unjustified distributed components are present.

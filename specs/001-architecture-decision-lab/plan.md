# Implementation Plan: Architecture Decision Lab

**Branch**: `feat/3-phase-2-foundational-components` | **Date**: 2026-10-12 | **Spec**: [spec.md](spec.md)

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

## Phase 2 Development Plan — Foundational Components

### Outcome and Boundary

Phase 2 delivers the shared foundation required by every user story: deterministic identity and
hashing, validated local configuration, transactional SQLite persistence, safe artifact storage,
resource diagnostics and GPU exclusion, progress primitives, stable ports, system endpoints, and
the read-only `doctor` command. It covers tasks T011–T027 from [tasks.md](tasks.md).

This phase does not implement scenarios, ADR generation, model loading, Knowledge Hub calls,
training, benchmarks, or the web experience. Integration status may report configuration and
availability, but live integration behavior remains in its owning later phase.

### Delivery Sequence

| Wave | Tasks | Deliverable | Entry dependency | Exit evidence |
| --- | --- | --- | --- | --- |
| 1 — Shared contracts | T011, T012, T015, T016, T025 | Typed configuration, deterministic helpers, safe errors/logs, and dependency-inversion ports | Phase 1 setup complete | Unit tests prove canonical hashing, timezone-aware clocks, loopback rejection, redaction, and stable problem codes |
| 2 — Persistence kernel | T013, T014 | Async SQLite engine, WAL, sessions, unit of work, and initial Alembic revision | Wave 1 configuration and time helpers | A temporary database migrates from empty to head; transaction commit/rollback and WAL behavior pass without global state |
| 3 — Resource coordination | T021–T024 | Sanitized host probes, exclusive cross-process GPU lease, progress snapshots, and cooperative cancellation | Wave 1 settings and resource ports | CPU fixtures prove insufficient-VRAM diagnostics, external-process reporting, lease exclusion, cancellation idempotence, and secret-free output |
| 4 — Artifact subsystem | T017–T020 | Artifact catalog, migration, content-addressed store, quota accounting, and prune/list services | Waves 1–3; T017 may start after Wave 2 | Property and integration tests prove traversal rejection, atomic cleanup, hash stability, reference-safe deletion, and 40/50 GB thresholds |
| 5 — Delivery shells | T026, T027 | FastAPI factory/system routes and Typer `doctor` in human and JSON modes | Waves 1–4 | OpenAPI/CLI contract tests pass; readiness and doctor expose consistent sanitized state and documented exit codes |
| 6 — Foundation gate | T011–T027 | Integrated CPU-only foundation ready for user-story work | Waves 1–5 | Full Python quality gate, migration smoke test, API/CLI contract suite, and temporary-root integration suite pass with CUDA and live integrations disabled |

Tasks marked `[P]` may be developed concurrently only inside their wave and only when they do not
edit the same shared contract. Database migrations remain serialized. Each wave lands with its own
tests and keeps the repository runnable; no later wave may compensate for a failing earlier gate.
T019 and T023 tests may be authored against agreed interfaces in parallel, but merge with the
implementations they verify rather than being treated as independently complete deliverables.

### Dependency Rules

- Configuration is the composition root: persistence, artifact storage, resource probes, API, and
  CLI receive validated settings rather than reading environment variables throughout the code.
- T025 precedes infrastructure implementations: repository, transaction, disk-capacity,
  reference-query, progress, and diagnostic ports must be usable by fakes without importing
  FastAPI, SQLAlchemy, or model libraries.
- Persistence exposes session and unit-of-work boundaries before any repository-backed service is
  added. Alembic owns schema evolution; application startup does not create tables implicitly.
- Artifact metadata is committed only after a temporary file is completely written, hashed, and
  atomically moved under the configured root. Failed metadata commits leave no published reference.
- Artifact quota uses both catalog totals and host free-disk reserve. The 40 GB warning is
  observable; the 50 GB limit is a hard precondition failure.
- Resource probes return typed, sanitized observations. Probe failure is data in the result, not a
  reason to crash health endpoints, and ADR Forge never terminates an external GPU process.
- The GPU lease is exclusive across processes and released on normal exit, cancellation, and
  exceptions. Progress publication and cancellation remain runtime-agnostic for later model and
  training adapters.
- API and CLI are adapters over the same services. They must not reimplement validation, quota,
  readiness, error-code, or redaction rules.

### Resolved Foundation Decisions

- Canonical JSON uses UTF-8, sorted object keys, compact separators, normalized supported scalar
  encodings, and explicit serializers for timezone-aware UTC datetimes and finite decimals. It
  rejects naive datetimes, non-finite numbers, and unsupported values instead of hashing a lossy
  representation.
- `artifact_free_disk_reserve_bytes` is a typed setting with a 5 GiB default. Configuration
  validates a positive reserve and `warning_bytes < limit_bytes`; the initial warning and limit
  remain 40 GB and 50 GB.
- T025 defines a `DiskCapacityProbe`; T021 implements it and T020 receives it by injection. This
  preserves the rule that `artifacts` does not depend on `system` infrastructure.
- T017 adds an `ArtifactReference` registry linked to the artifact and an owning entity identity.
  Artifact-owning services add or remove references in the same unit of work as their metadata;
  delete and prune query this registry rather than guessing future foreign-key relationships.
- Physical objects use a hash-derived canonical relative path. Multiple logical records that share
  the path count once toward quota; deletion requires no artifact record or retained reference to
  need that physical object.
- Startup artifact reconciliation removes only stale temporary files. Missing referenced files and
  unregistered finalized objects are reported as readiness/doctor findings; finalized objects are
  never silently deleted.
- The GPU lease uses a non-blocking operating-system file lock under a configured local lock
  directory. PID, process start time, and an ownership token are diagnostic metadata; the kernel
  releases the lock after a crash, and only the owning handle can release it.
- Alembic's `alembic_version` is the sole schema-version table. T014 must not introduce a second
  application-owned schema counter.
- Readiness depends on valid configuration, a reachable/migrated SQLite database, and a writable
  artifact root with required reserve. Missing GPU, model files, or optional Knowledge Hub access
  are sanitized capability findings and do not make the base API unready.
- `doctor` checks model availability from configured local/cache metadata without downloading,
  validates tracked dataset schemas, and uses a bounded Knowledge Hub health probe rather than the
  retrieval endpoint. Its tests use a fake HTTP transport; unavailability maps to the documented
  integration exit code without exposing credentials.

### Test-First Work per Wave

Before implementation in each wave, add failing tests for the invariant being introduced. Use
temporary directories, temporary SQLite databases, fake clocks/probes, and injected settings; the
default suite must not require a GPU, network, Knowledge Hub, or model download.

Required suites:

- `tests/unit/shared/`: identity, canonical JSON/hash, settings, problem details, and redaction;
- `tests/integration/persistence/`: migration-to-head, WAL, commit, rollback, and session cleanup;
- `tests/unit/artifacts/test_store.py`: the T019 property tests plus quota/prune service cases;
- `tests/unit/system/test_gpu_preflight.py`: the T023 CPU fixtures plus lease cleanup and progress
  cancellation cases, including a real local multiprocess lease exclusion test;
- `tests/contract/test_system_api.py`: health, readiness, resources, CORS, request IDs, and
  `application/problem+json` responses;
- `tests/contract/test_doctor_cli.py`: human/JSON schema, exit codes, read-only behavior, and secret
  redaction.

### Completion Gate

Phase 2 is complete only when all T011–T027 acceptance evidence passes and the following conditions
hold together:

1. A clean temporary database upgrades to Alembic head and supports a committed and rolled-back
   unit of work.
2. An artifact can be written, deduplicated by hash, listed, protected while referenced, and
   pruned after it becomes eligible; partial writes and traversal attempts publish nothing.
3. Fake resource probes produce stable readiness, resource, lease, and diagnostic results without
   exposing tokens, prompts, retrieved content, or unrestricted filesystem paths.
4. `/health`, `/readiness`, `/system/resources`, integration status, and `adr-forge doctor` agree
   on shared state and match the documented API and CLI contracts.
5. Formatting, linting, strict type checking, and all tests excluding `gpu` and
   `live_integration` pass on CPU only.

### Risks and Controls

| Risk | Control |
| --- | --- |
| Async SQLAlchemy sessions leak or cross task boundaries | One session per unit of work, explicit transaction ownership, rollback tests, and deterministic disposal |
| Path normalization differs across platforms | Resolve against the configured root, reject absolute/traversing paths before I/O, and cover generated adversarial paths |
| Filesystem and metadata diverge after failure | Temporary write plus atomic move, narrow transaction boundary, cleanup on failure, and reconciliation-ready lookup semantics |
| GPU diagnostics are unavailable on CPU CI | Injectable probes and fixture-driven results; live GPU validation remains explicitly marked |
| Health endpoints expose secrets or become expensive | Sanitized DTOs, redaction tests, bounded probes, and no model loading or live inference |
| API and CLI behavior drift | Reuse the same application services and assert both adapters against stable contracts |
| Generic artifact references lose integrity | Enforce owner type/identity validation in the reference service and require reference updates in the owner's unit of work |
| Concurrent writers exceed artifact quota | Reserve or revalidate capacity immediately before publication and test concurrent writers against one temporary root |

## Complexity Tracking

No constitution violations or unjustified distributed components are present.

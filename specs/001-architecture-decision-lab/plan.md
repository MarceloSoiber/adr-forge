# Implementation Plan: Architecture Decision Lab

**Branch**: `feat/8-phase-7-curate-trustworthy-experiment-data` | **Date**: 2026-10-15 | **Spec**: [spec.md](spec.md)

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

- The API process owns a single in-process inference queue. GPU-backed jobs additionally acquire
  the cross-process operating-system GPU lease; CPU fake jobs do not require GPU state.
- Blocking model work runs outside the event loop and emits persisted status snapshots plus
  best-effort server-sent progress events.
- Cancellation is cooperative. A cancelled run remains immutable and records partial artifacts.
- Training and full benchmarks run through the CLI as separate foreground processes after GPU
  preflight. They do not run inside HTTP requests.
- On API startup, any metadata run left in `pending`, `waiting_resources`, or `running` becomes
  `interrupted`; the in-memory queue is never treated as durable.
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

## Phase 3 Development Plan — Architecture Decision Analysis MVP

### Outcome and Boundary

Phase 3 delivers the first complete product slice for tasks T028–T049: create and classify an
immutable Portuguese scenario, execute a selected baseline through a recoverable local run,
preserve and validate model output, show persisted progress, review a structured ADR, and export
stable Markdown. The required completion path uses the fake runtime and must pass without network,
Knowledge Hub, CUDA, or the `ml` dependency group. A pinned Qwen baseline is an opt-in GPU path
behind the same runtime port.

This phase does not implement clarification-answer revisions, retrieval, multi-strategy
experiments, blind comparison, datasets, training, or benchmarks. It may preserve a structurally
valid provisional ADR when the supplied context is insufficient; malformed or structurally invalid
model content terminates as `invalid_output`. The interactive clarification workflow remains Phase 4.
The strategy registry is intentionally minimal: Phase 3 exposes fake and Qwen baseline entries;
Phase 5 extends the same registry with prompted, RAG, and fine-tuned strategies.

No `NEEDS CLARIFICATION` items remain. Phase-specific decisions are recorded in
[research.md](research.md), and the hardened nested schemas and run evidence are defined in
[data-model.md](data-model.md) and [contracts/api.openapi.yaml](contracts/api.openapi.yaml).

### Delivery Sequence

| Wave | Tasks | Deliverable | Entry dependency | Exit evidence |
| --- | --- | --- | --- | --- |
| 0 — Contract alignment | Supports T030, T039, T047, T048 | `/api/v1` router boundary, RFC 9457 validation errors, closed ADR schemas, progress event, strategy summary, export semantics | Phase 2 gate passed | OpenAPI parses; existing system routes and new contract fixtures agree on prefix, media types, IDs, categories, states, and nested values |
| 1 — Domain specifications | T028, T029, T033, T036–T039, T042 | Immutable scenario/revision and run models, ADR value schemas, validation findings, renderers, strategy configuration, exact transition matrix | Wave 0 contracts frozen | Unit/property tests prove normalized hashes, category values, list bounds, terminal immutability, proposed/provisional invariants, evidence links, negative consequences, and measurable triggers |
| 2 — Persistence kernel | T034, T035, T043 | Scenario/revision, analysis-run, ADR, artifact/reference catalog repositories and migrations `0003`/`0004`; deterministic classifier | Wave 1 models stable | Migration-to-head and repository tests prove first-revision atomicity, uniqueness, JSON validation, short UoWs, terminal constraints, UTC normalization, and restart interruption |
| 3 — Generation boundary | T040, T041 | Minimal registry, structured baseline prompt, deterministic fake, lazy Qwen runtime, typed generation telemetry, one repair attempt with separate artifacts/findings | Waves 1–2 schemas and artifact catalog | CPU tests import and run fake without ML extras; parser preserves original output, attempts at most one repair, and reports original/repaired validation independently; optional GPU test proves pinning and cooperative stop |
| 4 — Execution and use cases | T044, T045 | Single in-process queue, persist-first progress adapter, selective GPU lease, cancellation, recovery, create/execute/get/cancel/export services | Waves 2–3 | Service tests prove enqueue-after-commit, no long transaction during generation, legal cancellation, terminal persistence, safe artifacts, and interruption of every orphaned non-terminal run |
| 5 — HTTP and SSE | T030, T046, T047 | Scenario, minimal strategy-list, run, ADR, cancel, export, and SSE routes mounted under `/api/v1` | Wave 4 services | Contract tests use temporary SQLite/artifacts; every error is problem details; SSE begins with persisted state, sequences events, closes on terminal, and cleans up disconnects |
| 6 — Web analysis flow | T032, T048, T049 | Typed client, problem parsing, controlled EventSource reconnect, Portuguese scenario form, strategy picker, progress/cancel view, complete ADR view, accountability notice, Markdown download | Wave 5 API contract stable; T032 authored before implementation | Vitest covers submission, 422 and invalid-output failures, state-before-stream reconnect, terminal close, all ADR sections, unmount cleanup, and export; TypeScript, lint, and build pass |
| 7 — Vertical-slice gate | T031 plus checkpoint | Fake-runtime API flow and browser smoke from scenario to Markdown; opt-in Qwen smoke | Waves 1–6 | Full CPU-only quality gate passes with no network/model import; fresh database migrates to head; fake run survives refresh/reconnect; optional `gpu` test records pinned revision, hardware, duration, tokens, and peak VRAM |

Tasks marked `[P]` may proceed concurrently only after Wave 0 freezes shared contracts. Within
Wave 1, scenario models, ADR schemas, strategy configuration, and run state can be developed in
parallel because they own separate modules. Migrations remain ordered (`0003_scenarios` before
`0004_analysis_runs`), and the API/web waves do not begin against provisional response shapes.

### Domain and Contract Rules

- `DecisionScenario` is stable identity; `ScenarioRevision` is immutable evidence. The first
  revision and scenario row commit together. Classification is injected, deterministic in Phase 3,
  completed before hashing, and always returns one or more contract enum values.
- Canonical revision hashes cover normalized content and categories, exclude identity/timestamps,
  preserve user list order, and are unique within one scenario. Later clarification revisions use
  compare-and-swap on the current revision; Phase 3 establishes the aggregate rule but does not
  expose the revision-creation endpoint.
- `ADRDraft` nested values are closed Pydantic schemas. The shared validator returns ordered,
  stable findings and is the only implementation of provisional/conclusive rules. Renderers accept
  a validated draft and never add defaults, facts, rationale, or consequences.
- Generated statuses are only `proposed` and `provisional`. A model cannot mark its own draft
  accepted, rejected, or superseded.
- The Phase 3 registry contains configuration and runner objects but no database table. The fake
  and Qwen baseline use the same prompt contract; only runtime generation differs. `GET
  /strategies` exposes the minimal registry now, while Phase 5 expands availability checks.
- The runtime port returns generated text and optional token, latency, and VRAM telemetry.
  `transformers` and `torch` imports are lazy so default CI and API import work without ML extras.
- API payload validation and domain failures share the versioned problem-details envelope. All
  feature and system endpoints are mounted under `/api/v1`, matching the OpenAPI server URL.

### Persistence and Transaction Boundaries

1. Scenario creation classifies and validates outside a transaction, then inserts scenario and
   revision in one short UoW.
2. Run creation validates scenario/strategy, persists `pending`, commits, and only then enqueues the
   run. Enqueue failure moves the durable run to `failed`; it never leaves an invisible job.
3. The worker persists `waiting_resources` and `running` snapshots in short UoWs. GPU preflight,
   lease waiting, prompt construction, generation, parsing, rendering, and filesystem writes occur
   outside database transactions.
4. The original output is written atomically and cataloged before parsing. An optional repair
   output is a second immutable artifact. Artifact metadata, owner references, validation attempt
   summaries, valid ADR metadata, and the terminal run state commit together after the physical
   objects exist. A crash between file publication and metadata commit leaves a reported orphan,
   never silent deletion.
5. Progress sequence and stage are committed before publishing the matching in-process event.
   Startup changes every `pending`, `waiting_resources`, or `running` run to `interrupted` because
   the queue and model call are not durable.
6. Cancellation of `pending` or `waiting_resources` work is immediately terminal. Cancellation of
   `running` work requests the thread-safe token; the worker records `cancelled` only after the
   runtime cooperates. Repeated or terminal cancellation returns a stable conflict.

### Executor, Progress, and SSE Design

- One application-owned `asyncio.Queue` and one worker serialize inference. The fake runner skips
  resource preflight and GPU locking; GPU-backed runners preflight, then acquire the existing
  cross-process file lease before model allocation.
- Blocking Qwen work executes off the event loop. Its stopping criteria checks the shared
  thread-safe cancellation token. Application shutdown requests cancellation, stops accepting
  work, bounds the worker drain, and disposes the async SQLAlchemy engine.
- The current synchronous progress publisher remains the safe bridge from worker threads. An async
  subscription adapter owns one bounded queue per SSE client and unregisters it on disconnect.
  Slow subscribers may miss intermediate events because persisted state is authoritative.
- SSE registers its bounded subscriber first, then reads and emits the durable snapshot. It drains
  only queued events whose sequence is newer than that snapshot, closing the read/subscribe race.
  Each payload carries run ID, status, sanitized stage, optional percentage, monotonic sequence,
  optional terminal failure, and update time. The stream sends heartbeats as transport comments
  and closes on a terminal state.
- The browser disables native duplicate retry behavior by closing a failed `EventSource`; after
  bounded backoff it performs `GET /analysis-runs/{id}` and opens one new stream only if the run is
  still non-terminal. Disposal prevents reconnect or state updates after unmount.

### Test-First Work per Wave

- Create shared fixtures for a migrated temporary SQLite database, temporary artifact root,
  injected clock/UUID factory, fixed classifier, deterministic fake runtime, and an app constructed
  without GPU or live integrations.
- T028 covers revision construction, normalization, hash stability, per-scenario duplicate
  rejection, and one/multiple/unsupported classifications. Optimistic creation of later revisions
  remains covered by the Phase 4 stale-base contract tests.
- T029 generates valid and invalid proposed/provisional drafts and asserts finding codes rather
  than brittle prose. Property tests cover question limits, viable alternatives, finite trigger
  thresholds, consequence requirements, and evidence-link integrity.
- T030 validates status, headers, media type, problem shape, and payloads against the checked-in
  OpenAPI schema. Add a development-only OpenAPI validator if direct schema validation cannot be
  achieved with existing dependencies; do not duplicate schemas in tests.
- T031 uses only the fake registry entry and temporary storage. It creates a scenario, creates a
  run, observes persisted/SSE progress, fetches the ADR, exports Markdown, and asserts original
  output plus validation evidence exist.
- T032 mocks `fetch` and `EventSource` at service boundaries, uses an isolated QueryClient with
  retries disabled, and covers both request `422` and terminal `invalid_output` behavior.
- The optional GPU smoke is marked `gpu`, never imported by default CI, and records the exact model
  revision and environment rather than asserting variable natural-language output.

### Phase 3 Constitution Check

| Principle | Phase 3 design evidence | Status |
| --- | --- | --- |
| Evidence Before Claims | Closed ADR values, evidence-linked rationale, shared conclusive/provisional validation, immutable original output, and human-accountability UI notice | PASS |
| Reproducible and Honest Experiments | Strategy/model/prompt/generation versions, separate original/repair evidence, terminal failure visibility, and no silent retries | PASS |
| Dataset Integrity and Human Review | Phase 3 introduces no published dataset; tests use authored synthetic fixtures and keep final accountability human | PASS |
| Contracts and Tests | OpenAPI, exact state transitions, stable findings, test-first waves, fake vertical slice, and optional marked GPU smoke | PASS |
| Local-First Security and Resource Safety | `/api/v1` remains loopback-only, errors are sanitized, ML imports are lazy, cancellation is cooperative, and GPU work uses preflight plus the OS lease | PASS |
| Simplicity With Measured Evolution | One process, one queue, SQLite, filesystem artifacts, in-memory registry, and best-effort SSE; no broker, worker service, or new database | PASS |

Post-design review found no constitutional violation. The minimal strategy endpoint and async SSE
adapter complete existing Phase 3 contracts without adding a new service or persistence model.

### Completion Gate

Phase 3 is complete only when all T028–T049 evidence and these conditions hold together:

1. A fresh database migrates through `0004`, creates a classified scenario and first immutable
   revision atomically, and rejects invalid, duplicate, or stale aggregate operations.
2. The fake baseline runs from `pending` to a valid terminal state without ML extras, network, GPU,
   or Knowledge Hub. Refresh/reconnect recovers from persisted state rather than event replay.
3. Original output is always retained. At most one repair output exists, both validation attempts
   remain distinguishable, and an invalid repair ends visibly as `invalid_output` with no ADR.
4. A completed run exposes a validated structured ADR and byte-stable JSON/Markdown rendering that
   does not invent content. A generated draft is never self-declared accepted.
5. API and web use the same `/api/v1` contract, problem details, category/status enums, nested ADR
   shapes, progress fields, and export semantics.
6. Python formatting, linting, strict typing, migration tests, unit/property tests, contract tests,
   fake integration tests, frontend tests/typecheck/build, secret scanning, and dependency checks
   pass CPU-only. The optional Qwen GPU smoke is reported separately.

### Risks and Controls

| Risk | Control |
| --- | --- |
| Progress protocol and synchronous publisher drift | Define one persisted progress DTO and isolate callback-to-async adaptation behind the SSE publisher adapter |
| Artifact rows/references are missing despite Phase 2 tables | Add the minimal catalog/reference repository before run persistence and test the owner registry with `analysis_run` and `adr_draft` |
| Queue accepts work before the run commit | Enqueue only after a successful UoW; persist a stable failure if enqueue itself fails |
| Long generation holds a SQLite transaction | Assert transaction boundaries in service tests and run every model/filesystem operation outside UoWs |
| Repair obscures poor raw model behavior | Separate immutable artifacts and validation summaries, permit one repair only, and expose terminal invalid output |
| Fake path accidentally requires CUDA or ML imports | Lazy-import ML libraries and test package/app import with only base dependencies installed |
| Strategy picker depends on Phase 5 work | Deliver the minimal registry/list route in Phase 3; reserve retrieval/adapter availability expansion for T071 |
| OpenAPI and running FastAPI paths diverge | Mount a single `/api/v1` parent router and assert every Phase 3 operation in contract tests |
| SSE reconnect duplicates streams or regresses terminal state | Persist-first sequencing, one owned EventSource, explicit close/dispose, GET-before-reconnect, and monotonic sequence checks |
| Classification keyword rules overstate certainty | Keep the classifier injectable, return the ordered specific matches or exactly `[unsupported]`, and never use classification as architectural recommendation evidence |

## Complexity Tracking

No constitution violations or unjustified distributed components are present. Phase 3 adds one
in-process queue, one async SSE adapter, and one in-memory strategy registry because each is needed
by the published vertical-slice contract; none introduces a separately deployed component.

## Phase 4 Development Plan — Context Clarification

### Outcome and Boundary

Phase 4 delivers tasks T050–T058 and closes User Story 2. An incomplete or contradictory scenario
finishes its first run with a valid provisional ADR and no more than three impact-aware questions.
The architect can either keep that explicitly provisional result or answer one or more questions;
accepted answers create a new immutable scenario revision, from which a new analysis run can be
started without changing the source revision, source run, provisional ADR, or validation evidence.

The required path remains CPU-only and deterministic with the fake strategy. This phase does not
add retrieval, multi-strategy comparison, automatic merging of free-text answers into facts or
constraints, collaborative editing, or a human ADR lifecycle. It reuses the Phase 3 queue, run
state machine, artifact catalog, RFC 9457 errors, and `/api/v1` boundary. No database migration is
required because `scenario_revisions.clarification_answers_json` and the scenario head pointer
already exist.

No `NEEDS CLARIFICATION` items remain. Phase-specific decisions are recorded in
[research.md](research.md), value objects and invariants in [data-model.md](data-model.md), the
revision command in [contracts/api.openapi.yaml](contracts/api.openapi.yaml), and executable
acceptance evidence in [quickstart.md](quickstart.md).

### Delivery Sequence

| Wave | Tasks | Deliverable | Entry dependency | Exit evidence |
| --- | --- | --- | --- | --- |
| 0 — Contract freeze | Supports T051, T053, T056, T058 | Authoritative question IDs, source-run linkage, closed answer schema, `stale_revision` problem, and revision response shape | Phase 3 merged and OpenAPI parses | Contract examples distinguish 404, 409, and 422; generated and handwritten clients agree on fields |
| 1 — Tests first | T050–T052 | Adversarial benchmark fixtures, stale-base API tests, and clarification UI tests | Wave 0 response shapes frozen | Tests fail only for missing Phase 4 behavior and cover every US2 acceptance scenario |
| 2 — Domain policy | T053–T055 | Frozen clarification value objects, deterministic provisional rules, fake/prompt behavior, terminal-state mapping, source-run validation, and compare-and-swap revision service | Wave 1 tests present | Unit/property tests prove limits, ownership, immutability, confidence ceiling, no invented defaults, correct terminal state, duplicate rejection, and one-winner concurrency |
| 3 — Persistence and HTTP | T055–T056 | Atomic revision append and `POST /scenarios/{scenarioId}/revisions` | Wave 2 policy stable | Repository/contract tests prove inherited content, monotonic revision numbers, rollback, `409 stale_revision`, and unchanged prior evidence |
| 4 — Portuguese evidence and UI | T057–T058 | Reviewed JSONL cases and an accessible clarification panel integrated into `AnalysisFlow` | Wave 3 endpoint stable | Four categories cover missing and contradictory context; Vitest proves answer/resubmit and provisional paths |
| 5 — Independent vertical-slice gate | Checkpoint | Complete US1 path plus incomplete US2 path using the fake strategy | Waves 1–4 | CPU gate passes; answering creates revision N+1 and a new run while revision N, its run, and ADR remain byte-stable |

Tasks T050–T052 are authored before their corresponding implementation. T050, T051, T052, and
T057 may proceed in parallel after Wave 0 because they own separate test or fixture files. Domain,
repository, route, and UI implementation remain ordered so no layer is built against a provisional
command shape.

### Clarification and Validation Rules

- A clarification question is identified by its immutable ADR question ID and belongs to exactly
  one terminal source run. The server resolves the question text and impact from the stored ADR;
  client-supplied prose is never treated as authoritative evidence.
- A clarification answer contains `question_id`, non-blank `answer`, and `source_run_id`. A request
  contains one to three answers with unique question IDs. Every source run must belong to the base
  revision, be in `needs_clarification`, have a stored provisional ADR, and expose the referenced
  unresolved question.
- A provisional ADR contains one to three unique, impact-aware unresolved questions, at least one
  explicit assumption, no unsupported conclusive decision, and confidence no greater than `0.60`.
  Missing critical context produces `context.missing_critical`, contradictory constraints produce
  `context.contradictory_constraints`, excessive provisional confidence produces
  `confidence.provisional_too_high`, and a forced technology preference produces the warning
  `context.forced_preference`. The preference is evidence to challenge, not an accepted decision.
- Strategy prompts and the deterministic fake do not manufacture a fallback constraint to make an
  incomplete scenario look complete. A structurally valid `provisional` draft maps the run to
  `needs_clarification`; only a valid `proposed` draft maps it to `completed`.
- Choosing not to answer does not create or mutate anything. The existing provisional ADR remains
  reviewable and exportable with its assumptions, questions, and reduced confidence visible.
- Answers are appended as immutable snapshots containing the authoritative question text and
  impact. The new revision inherits the base problem, facts, constraints, desired qualities,
  alternatives, and category order; the strategy receives the appended answers as additional
  user evidence on the next run.

### Optimistic Revision Transaction

1. Load the scenario, requested base revision, source runs, and source ADRs; validate ownership,
   terminal state, question IDs, limits, and request size before opening a write transaction.
2. Construct revision `base_revision_number + 1`, append normalized answers, and calculate the
   canonical content hash without changing the base object.
3. In one short transaction, conditionally advance `decision_scenarios.current_revision_number`
   only when it still equals `base_revision_number`, then insert the new revision. A zero-row
   compare-and-swap raises `409` with code `stale_revision`; any insert failure rolls back the head
   update.
4. Return the committed revision. Starting its analysis is a separate existing command, so an
   enqueue failure cannot roll back or obscure the architect's answers.
5. Concurrent requests against the same base have exactly one winner. Retrying the losing request
   requires reading the current scenario and deliberately rebasing; the service never merges
   answers silently.

### API and Web Flow

- `POST /api/v1/scenarios/{scenarioId}/revisions` accepts the base revision number and one to three
  answer references. It returns `201` with the immutable revision, `404` for unknown scenario/run,
  `409 stale_revision` for an outdated head, and `422` for ownership, state, question, duplicate,
  or limit violations.
- `ScenarioRevision` responses expose the stored clarification-answer snapshots so clients and
  tests can verify provenance. Existing scenario and run endpoints remain unchanged.
- `AnalysisFlow` renders `ClarificationPanel` whenever a terminal `needs_clarification` run has a
  provisional ADR. The panel labels why each answer matters, permits one to three selected
  answers, announces validation/errors accessibly, and keeps the explicit action to continue with
  the provisional ADR.
- On successful revision creation, the browser starts a new run with the same selected strategy
  and its current version, replaces the active subscription safely, and retains navigation context
  for the previous provisional result. A `409` refreshes the current scenario and preserves typed
  answers for deliberate resubmission; it never auto-rebases.

### Test-First Work per Wave

- T050 uses reviewed pt-BR inputs for missing scale, cost-versus-availability conflict, forced
  technology preference, and unanswered questions. Assertions target structured question count,
  impact, status, assumptions, and confidence rather than brittle full prose.
- T051 posts valid, duplicate, cross-scenario, non-terminal-source, unknown-question, oversized,
  and stale-base requests. A two-writer test proves one `201` and one `409`, and rereads every old
  revision/run/ADR to prove immutability.
- T052 mocks the typed API and run-event boundary. It covers question impact rendering, keyboard
  and label accessibility, partial answers, client validation, provisional continuation, new-run
  subscription cleanup, `409` preservation, and non-Phase-4 US1 regression.
- Property tests generate one to three unique answers and invalid zero, four, duplicate, blank,
  mismatched-run, and mismatched-scenario cases. Stable finding/error codes are asserted instead of
  localized messages.
- T057 fixtures include both missing and contradictory cases across all four categories, authored
  in Brazilian Portuguese with `id`, category, input, expected issue kind, expected impact area,
  review status, and reviewer note. They contain no production, personal, payment, or confidential
  data and are not promoted into a published dataset by this phase.

### Phase 4 Constitution Check

| Principle | Phase 4 design evidence | Status |
| --- | --- | --- |
| Evidence Before Claims | Authoritative source-run questions, provisional status, explicit assumptions, impact, reduced confidence, and no silent conversion of answers into facts | PASS |
| Reproducible and Honest Experiments | Source revision/run linkage and immutable old runs, ADRs, outputs, validation findings, and answer snapshots | PASS |
| Dataset Integrity and Human Review | Reviewed synthetic pt-BR fixtures remain test evidence and are not silently promoted to training data | PASS |
| Contracts and Tests | OpenAPI-first command, stable errors/findings, tests before implementation, CAS concurrency proof, and independent US1/US2 gates | PASS |
| Local-First Security and Resource Safety | CPU-only fake path, bounded bodies and answer counts, no new external service, and no client-authoritative evidence | PASS |
| Simplicity With Measured Evolution | Existing SQLite JSON column, repository, queue, routes, and React flow are extended without a broker, new service, or migration | PASS |

Post-design review found no constitutional violation. A dedicated clarification value-object module
is justified by provenance and validation rules shared by persistence, API, prompts, and tests; it
does not introduce a new runtime component.

### Completion Gate

Phase 4 is complete only when T050–T058 and all conditions below hold together:

1. Incomplete and contradictory pt-BR scenarios yield a valid provisional ADR with one to three
   relevant questions, explicit assumptions, and confidence at or below `0.60`; complete Phase 3
   scenarios still complete without entering clarification.
2. Valid answers create exactly one new immutable revision whose provenance points to the source
   run and question. The base revision, source run, ADR, raw outputs, and findings remain unchanged.
3. Stale concurrent writers produce one success and one `409 stale_revision`; invalid ownership,
   state, question IDs, duplicates, limits, and request sizes cannot advance the scenario head.
4. The browser can show why each question matters, continue with the provisional result, submit
   answers, start the next run, recover from a stale base without losing input, and close the prior
   EventSource before subscribing again.
5. OpenAPI parsing, Python formatting/lint/type checks, unit/property/contract/benchmark tests,
   frontend tests/typecheck/build, secret scanning, and the fake US1/US2 vertical slices pass
   CPU-only without network, model packages, GPU, or Knowledge Hub.

### Risks and Controls

| Risk | Control |
| --- | --- |
| Client changes question prose or answers a question from another run | Accept IDs, resolve authoritative snapshots server-side, and verify run/revision/scenario ownership |
| Two tabs overwrite the current revision | Atomic compare-and-swap on the scenario head and a stable `409 stale_revision` response |
| Answer prose is silently promoted to fact | Preserve it as a clarification answer; only a later explicit user edit may change facts or constraints |
| Provisional output appears conclusive | Enforce question/assumption requirements, confidence ceiling, visible status, and provisional UI action |
| Text heuristics create brittle tests | Assert structured kinds, impact, provenance, and stable findings; keep natural-language matching limited to reviewed fixtures |
| New run hides prior evidence | Separate revision creation from run creation and retain immutable source links and prior result context |
| Clarification breaks complete-scenario MVP | Keep US1 regression as an independent checkpoint and render the panel only for `needs_clarification` |

## Phase 5 Development Plan — Modeling Strategy Comparison

### Outcome and Boundary

Phase 5 delivers tasks T059–T076 and closes User Story 3. A practitioner can freeze one exact
retrieval result, execute equivalent scenario inputs through the available baseline, prompted,
RAG, and configured fine-tuned strategy compositions, and compare two or more completed ADRs under
randomized labels. Strategy and run identities remain undisclosed until an immutable rubric
evaluation is committed.

The required CI path is CPU-only: Knowledge Hub is mocked, retrieval can be replayed from a fixture,
and generation uses deterministic fake runtimes. Live Knowledge Hub and GPU-backed Qwen checks are
explicit opt-in validations. This phase does not train an adapter, run a benchmark matrix, publish a
dataset, add authentication, or introduce a worker/broker. Fine-tuned entries may be registered but
must report unavailable until a valid adapter artifact and compatible runtime are configured.

No `NEEDS CLARIFICATION` items remain. Phase-specific decisions are recorded in
[research.md](research.md), canonical entities and invariants in [data-model.md](data-model.md),
HTTP and retrieval boundaries in [contracts/](contracts/), and executable evidence in
[quickstart.md](quickstart.md).

### Resolved Dependencies and Task Mapping

- T065 and T073 use `0007_retrieval_snapshots.py` and `0008_blind_evaluation.py`; the filenames in
  [tasks.md](tasks.md) are superseded because `0005` and `0006` already contain merged run-event and
  telemetry migrations. The future experiment migration advances to the next free revision.
- T064–T068 include a shared snapshot-creation application service and a thin
  `POST /retrieval-snapshots` adapter so the browser/tests can create or reuse a snapshot. A CLI
  wrapper may call the same service, but no second retrieval implementation is permitted.
- T069–T071 also extend `AnalysisRun`, migration/repository mappings, and the run executor with
  retrieval snapshot and generation-configuration provenance. The existing request fields cannot
  remain ignored, and execution must resolve the registered concrete strategy instead of always
  instantiating `FakeStrategy`.
- T072–T075 bring forward the minimum immutable rubric model, repository, and tracked `adr-v1`
  definition needed by User Story 3. Phase 6 extends rubric/experiment administration rather than
  creating the first evaluable rubric.
- T075 defines dedicated blinded and revealed DTOs. The normal `ADRDraft` response is not reused
  before evaluation because it contains `analysis_run_id` and other provenance.

### Delivery Sequence

| Wave | Tasks | Deliverable | Entry dependency | Exit evidence |
| --- | --- | --- | --- | --- |
| 0 — Contract freeze | Supports T059–T076 | Canonical snapshot envelope, comparison eligibility, evaluation correction semantics, stable problem codes, and blinded/revealed response shapes | Phase 4 merged; OpenAPI and Knowledge Hub contracts parse | Contract examples expose no identity before submission and define every fail-closed integration case |
| 1 — Tests first | T059–T063 | Knowledge Hub, snapshot, equivalence, blinding, and React comparison tests | Wave 0 shapes frozen | Tests fail only for missing Phase 5 behavior and require no network, model package, GPU, or live service |
| 2 — Retrieval domain and fixture provider | T064, T067 | Frozen snapshot/chunk models, canonical serializer/hash, and file-backed provider | Wave 1 canonicalization tests present | Reordered chunks or changed request/provider/embedding metadata change the hash; identical fixtures replay byte-for-byte |
| 3 — Retrieval persistence and live adapter | T065–T068 | Migration, repository, artifact ownership, bounded Knowledge Hub adapter, and atomic create-or-reuse service | Wave 2 models stable | Contract/integration tests prove one retry policy, 15-second wall-clock budget, token redaction, fail-closed schemas, rollback, and concurrent reuse |
| 4 — Comparable strategy composition | T069–T071 | Common generation input, prompted/RAG/fine-tuned-RAG composition, expanded registry, and request-aware availability | Wave 3 snapshot service stable | Equivalent RAG runs receive the same snapshot ID, ordered evidence, scenario revision, and generation settings; unavailable dependencies are never silently substituted |
| 5 — Blind evaluation domain and persistence | T072–T074 | Randomized label mapping, immutable submission/correction records, migrations, repositories, and reveal gate | Wave 4 produces completed comparable runs | Unit/integration tests prove eligibility, unpredictable labels, submit-before-reveal, duplicate conflict, explicit supersession, and immutable history |
| 6 — HTTP and web flow | T075–T076 | Comparison create/get/evaluate/reveal routes and accessible Portuguese comparison page | Wave 5 service contract stable | OpenAPI and Vitest prove rubric scoring, preference/tie, 5,000-character notes, failure recovery, post-submit reveal, and no pre-submit identity leakage |
| 7 — Independent US3 gate | Checkpoint | Stored fixture → one snapshot → equivalent runs → blinded evaluation → reveal | Waves 1–6 | Full CPU gate passes and all stored scenario, snapshot, run, mapping, rubric, and evaluation identities are traceable |

Tasks marked `[P]` may proceed concurrently only after Wave 0 freezes their shared shapes. The
retrieval and evaluation migrations remain serialized. Each implementation wave lands with its
own tests; the browser is not allowed to compensate for a missing server invariant.

### Retrieval Snapshot and Adapter Rules

- A snapshot canonical document contains `schema_version`, provider identity/version, normalized
  query, validated filters, embedding identity, and chunks in provider-returned rank order. Each
  chunk contains source/chunk identity, title, URI, structured location, exact content, finite
  score, ordered match reasons, rank, and its own content hash.
- `created_at`, database IDs, artifact paths, and transport-only fields are excluded from the
  canonical content hash. Query, filters, provider/embedding identity, chunk order, and every exact
  chunk field are included. Canonical JSON uses the existing shared hashing rules.
- The exact canonical JSON is published through the artifact store before metadata references it.
  Metadata plus `ArtifactReference(owner_type="retrieval_snapshot")` commit atomically. A unique
  content hash makes identical successful retrievals converge on one snapshot; a uniqueness race
  rereads the winner instead of duplicating metadata or leaking an orphaned reference.
- A file-backed provider validates the same closed snapshot schema as live retrieval. It never
  repairs, reorders, or enriches fixture content, so tests and benchmark replay observe the stored
  evidence exactly.
- The Knowledge Hub adapter receives an injected `httpx.AsyncClient` and clock/backoff boundary.
  One 15-second wall-clock budget covers all attempts and backoff; each connection attempt has a
  2-second connect limit. Only connection failures, 408, 429, and 5xx may receive one retry.
  Authentication, other 4xx, schema errors, and exhausted time fail immediately with sanitized
  stable errors.
- A missing required identity, location, content, embedding identity, non-finite score, duplicate
  rank, or inconsistent echoed query fails closed. RAG strategies become unavailable for that
  operation; non-RAG strategies remain usable. Empty or partial context is never labeled as RAG.

### Comparable Strategy Rules

- Extend `StructuredOutputStrategy.generate` to receive one frozen `StrategyInput` containing the
  immutable scenario revision, optional retrieval snapshot, and one versioned generation
  configuration. Strategies do not perform retrieval themselves.
- The Phase 3 baseline remains backward compatible. The prompted strategy owns a separate prompt
  version. RAG and fine-tuned-RAG share one evidence renderer that quotes chunks as untrusted
  reference material, assigns stable reference IDs, and places evidence outside privileged
  instructions.
- A strategy that requires retrieval rejects a missing or unknown snapshot before a run is queued.
  A strategy that does not use retrieval rejects an unexpected snapshot, preventing misleading
  provenance.
- Comparable RAG runs for one scenario revision must reference the same snapshot ID and generation
  configuration hash. Snapshot creation is a separate explicit operation and never occurs once per
  strategy.
- Registry availability is derived from enabled configuration plus required runtime/model,
  adapter artifact, retrieval provider, and request-specific snapshot checks. Stable unavailable
  reason codes accompany localized display text. No strategy silently falls back to a baseline,
  another model, or empty context.
- `GET /strategies` returns the full configured projection and performs no live Knowledge Hub call.
  Global availability reflects local configuration/runtime dependencies; snapshot ownership and
  operational retrieval failures are validated by snapshot/run creation with stable errors.
- Fine-tuned and fine-tuned-RAG definitions are valid compositions in this phase, but remain
  unavailable when the adapter is absent. Phase 7 supplies the trained adapter lifecycle.

### Blind Comparison and Evaluation Rules

- Creation accepts two or more distinct terminal `completed` runs. Every run must belong to the
  same immutable scenario revision, have a stored ADR, and reference a configured rubric version.
  RAG runs in the same comparison must satisfy the shared-snapshot equivalence rule.
- The service uses an injected cryptographically secure shuffler to assign opaque labels that do
  not encode insertion order, strategy, run ID, or model. The label-to-run mapping is stored once
  and never returned by create/get before a valid evaluation exists.
- Blinded responses contain only label, ADR content, rubric, and evaluation state. They omit run,
  strategy, model, prompt, adapter, snapshot, artifact, timing, and resource identities that could
  reveal the source.
- Submission validates a complete integer score for every rubric dimension and label, a preference
  naming one label or `tie`, evaluator type, pseudonymous evaluator ID, and notes of at most 5,000
  characters. The evaluation and comparison head update commit atomically.
- The first submission is immutable. A repeated submission without an explicit current
  `supersedes_evaluation_id` returns `409 evaluation_already_submitted`. A correction creates a new
  immutable result that points to the current result; stale or cross-comparison supersession
  returns `409`. Historical results remain queryable to application services and reports.
- Reveal succeeds only after submission and returns the anonymous label mapped to run and strategy
  identity plus the current evaluation ID. Before submission it returns `409
  evaluation_required`; reads and failed submissions cannot change reveal eligibility.

### Test-First Work per Wave

- T059 uses `respx` and a fake clock/backoff to cover success, connect failure, 408, 429, 5xx,
  non-retryable 4xx, auth failure, malformed JSON, missing required fields, non-finite scores,
  deadline exhaustion, and bearer-token absence from exceptions/log capture.
- T060 uses permutations and property tests to prove that object-key formatting is irrelevant but
  result order, exact text, query, filters, scores, match reasons, provider, and embedding identity
  are hash-significant. It also proves artifact bytes and stored models are not mutated on reuse.
- T061 records the `StrategyInput` observed by fake prompted/RAG runtimes and compares scenario,
  snapshot, evidence order, prompt/generation versions, and configuration hash rather than natural
  language output.
- T062 uses deterministic shufflers for assertions while production uses secure randomness. It
  covers ineligible runs, identity-bearing field absence, incomplete scores, invalid preference,
  duplicate submission, stale correction, cross-comparison correction, reveal-before-submit, and
  immutable history.
- T063/T076 test by accessible role and label in Portuguese. They cover stable randomized labels,
  every rubric dimension, keyboard operation, preference/tie, note limits, disabled/double submit,
  server failure without accidental reveal, correction, and identity reveal only after success.
- Repository tests apply migrations through the new heads on temporary SQLite databases and prove
  foreign keys, unique hashes, transaction rollback, artifact references, indexes, and immutable
  evaluation chains.

### Phase 5 Constitution Check

| Principle | Phase 5 design evidence | Status |
| --- | --- | --- |
| Evidence Before Claims | RAG cites frozen exact chunks as untrusted evidence; empty or invalid retrieval cannot masquerade as grounded output | PASS |
| Reproducible and Honest Experiments | Shared snapshot/configuration identity, immutable runs and evaluations, explicit correction chains, and post-submit reveal | PASS |
| Dataset Integrity and Human Review | Phase 5 adds no training publication; reviewed fixtures remain test artifacts and human rubric judgment stays authoritative | PASS |
| Contracts and Tests | Closed snapshot/OpenAPI schemas, stable errors, test-first waves, migration tests, equivalence proofs, and a CPU-only vertical slice | PASS |
| Local-First Security and Resource Safety | Token redaction, bounded deadlines, loopback integration, untrusted evidence quoting, no live dependency in CI, and existing GPU lease | PASS |
| Simplicity With Measured Evolution | Existing modular monolith, SQLite, artifact store, registry, executor, and React client are extended without a broker or new service | PASS |

Post-design review found no constitutional violation. Two migrations are justified because frozen
retrieval provenance and immutable evaluation history have different ownership and lifecycle.
Knowledge Hub remains the existing external provider behind one adapter; no retrieval stack is
duplicated inside ADR Forge.

### Completion Gate

Phase 5 is complete only when T059–T076 and all conditions below hold together:

1. One mocked or fixture retrieval creates a canonical, content-addressed snapshot whose exact
   ordered chunks can be replayed; concurrent identical creation returns one metadata identity and
   leaves no orphaned artifact reference.
2. Every RAG run rejects absent/mismatched retrieval and every comparable RAG run uses the same
   scenario revision, snapshot, evidence order, and generation configuration. Missing adapters or
   providers appear as unavailable rather than being substituted.
3. A comparison accepts only eligible completed runs from one scenario revision. Before evaluation,
   no API or UI representation contains strategy/run/model/snapshot identity or order leakage.
4. A valid complete evaluation is immutable, unlocks reveal atomically, and can only be corrected
   through an explicit one-parent supersession chain; duplicate and stale submissions remain
   visible conflicts.
5. The Portuguese UI supports accessible scoring, preference/tie, bounded notes, failure recovery,
   and post-submit reveal within the published contract.
6. OpenAPI parsing, migrations, Python formatting/lint/strict typing, unit/property/contract/
   integration tests, frontend tests/typecheck/build, secret scanning, and the fake US3 vertical
   slice pass CPU-only without network, model packages, GPU, or live Knowledge Hub.

### Risks and Controls

| Risk | Control |
| --- | --- |
| Knowledge Hub changes between strategy runs | Retrieve once, hash exact ordered content, and pass only the stored snapshot to strategies |
| Retry policy exceeds the advertised timeout | Wrap all attempts and backoff in one 15-second wall-clock budget with an injected test clock |
| Retrieved prompt injection changes privileged instructions | Render chunks as quoted untrusted evidence with stable references and no tool execution |
| Fine-tuned strategy is selected before Phase 7 adapter exists | Request-aware availability and fail-closed adapter artifact validation |
| Anonymous labels leak insertion order or provenance | Secure shuffle, opaque labels, dedicated blinded DTO, and forbidden identity fields in contract tests |
| Partial rubric scores unlock reveal | Validate the complete rubric matrix and commit evaluation plus reveal eligibility atomically |
| A correction overwrites the first judgment | Append-only superseding result with one current head and stale-parent conflict |
| Snapshot metadata commits without durable bytes | Publish/hash artifact first, then commit metadata/reference; reconcile abandoned unreferenced bytes safely |

## Phase 7 Development Plan — Trustworthy Dataset Curation and QLoRA Training

### Outcome and Boundary

Phase 7 delivers tasks T094–T116 and closes User Story 5. A practitioner can validate and publish
an immutable, reviewed Portuguese dataset whose provenance, licensing, lineage, partitions, and
content hashes are auditable; build canonical completion-only SFT input; train or resume one local
Qwen3-4B QLoRA adapter through a guarded foreground CLI; and register the resulting adapter as an
available fine-tuned strategy only after its manifest and base-model compatibility are verified.

The required CI path remains CPU-only. Dataset policy, schemas, canonical building, CLI behavior,
training configuration, checkpoint/resume orchestration, manifest hashing, cleanup, and adapter
verification use fixtures and a fake trainer. Actual model loading and one QLoRA smoke run are
explicit local `gpu` gates. This phase does not add dataset editing UI, remote training, model
download automation, a GPU container, a worker/broker, semantic embedding infrastructure, or a
second metadata store.

No `NEEDS CLARIFICATION` items remain. The accepted QLoRA stack and local execution constraints are
recorded in [research.md](research.md) and ADRs
[0003](../../docs/adrs/0003-qwen-qlora.md),
[0006](../../docs/adrs/0006-exclusive-gpu-lease.md), and
[0007](../../docs/adrs/0007-native-gpu-execution.md). Dataset entities and invariants are defined
in [data-model.md](data-model.md), CLI behavior in [contracts/cli.md](contracts/cli.md), and runnable
evidence in [quickstart.md](quickstart.md).

### Existing Baseline and Task Mapping

- T094–T098 and T100–T104, T106, and T113 already have partial code or tests in the working
  branch. Their presence is not completion evidence. Wave 0 audits them against the specification,
  closes false-positive/false-negative behavior, and keeps the tasks open until their exit evidence
  passes.
- T102 is the contract authority for T100–T106 and T111. The JSON Schemas freeze the portable Git
  representation; Pydantic models may be stricter internally but may not accept a published
  document rejected by the versioned schema or emit fields absent from it.
- T102 also creates `datasets/schemas/training-v1.json`. The task names four schema files while
  requiring five formats; this additional file resolves the training-data contract instead of
  leaving the canonical builder output implicit.
- T105 owns canonical transformation and exclusion accounting. T106 is a Typer adapter over the
  same validation/build services and must not duplicate governance or contamination policy.
- T107–T110 may be authored in parallel only after the example and ADR schemas are frozen. T111 is
  a separate human review/publication gate and cannot be inferred from schema validity or generated
  automatically.
- T112 freezes model identity and effective configuration before T113–T115. Configuration names
  such as `smoke` and `full` describe intent, not verified capacity; measured hardware, duration,
  peak VRAM, and outcome are recorded by the smoke run rather than predicted in YAML comments.
- T113 owns framework-specific construction and completion-only loss semantics. T114 owns resource
  preflight, exclusive lease, cancellation, staging, artifact publication, and cleanup. T115 only
  translates CLI input, progress, result, and stable exit semantics.
- T116 consumes the final adapter manifest through the existing strategy registry boundary. It
  does not teach the registry how to train, scan directories, or repair incompatible artifacts.
- Dataset publication remains Git-manifest based in this phase, as required by the constitution.
  `DatasetVersion` and membership are immutable domain/manifest values; no new SQLite migration or
  repository is introduced without a consumer requiring concurrent mutable persistence.

### Delivery Sequence

| Wave | Tasks | Deliverable | Entry dependency | Exit evidence |
| --- | --- | --- | --- | --- |
| 0 — Contract and baseline audit | Supports T094–T116 | Frozen example, ADR, manifest, rubric, training-row, adapter-manifest, finding, and CLI shapes; gap report for existing partial code | Phase 6 complete; current schemas, CLI contract, ADRs, and partial tests inspected | Every task maps to one contract and owner; fixtures parse; existing code is classified as reusable, incomplete, or superseded without marking tasks complete |
| 1 — Tests first | T094–T099 | Domain/state, contamination, governance, dataset CLI, mocked SFT, cleanup/resume, and opt-in GPU tests | Wave 0 shapes frozen | CPU tests fail only for missing Phase 7 behavior; GPU test is collected but skipped by default and declares all required telemetry |
| 2 — Dataset contracts and policy | T100–T104 | Immutable examples/versions/memberships, versioned JSON Schemas, governance findings, duplicate/lineage analysis, and semantic-review candidates | Wave 1 policy tests present | Schema and property tests prove review transitions, publication immutability, exact split membership, deterministic hashes, fail-closed provenance, sensitive-data review, and cross-split blocking |
| 3 — Canonical builder and CLI | T105–T106 | One validation pipeline, canonical completion-only JSONL builder, immutable build manifest, complete inclusion/exclusion report, and Typer commands | Wave 2 schemas and findings stable | Contract tests prove deterministic bytes/hashes, no overwrite, no mutation of source manifests, stable exit codes, atomic output, and zero duplicated policy in CLI code |
| 4 — Curated corpus and publication | T107–T111 | Four balanced 25-example Portuguese source files, independent review records, fixed evaluation families, and `v0.1.0` manifest | Wave 3 validator/build command passes; category authors use frozen schemas | Exactly 100 candidates are accounted for as included or rejected; every published member is approved/licensed; hashes resolve; no exact, normalized, confirmed-semantic, or lineage family leaks into evaluation |
| 5 — Training configuration and runtime | T112–T113 | Pinned base-model descriptor, smoke/full configs, lazy canonical TRL/PEFT/bitsandbytes trainer, completion-only masking, effective config, checkpoints/resume, and canonical adapter manifest | Wave 3 training-row schema stable; Wave 4 published train/validation splits available for the real run | Fake-trainer tests prove configuration rejection, mask boundaries, deterministic input identity, exact checkpoint selection, resume, multi-file adapter hashing, and failure cleanup without importing ML packages |
| 6 — Guarded training application | T114–T115 | Disk/GPU preflight, exclusive lease, cancellable foreground service, atomic artifact lifecycle, progress stream, and human/JSON CLI | Wave 5 runtime factory stable; foundational artifact/resource services available | CPU integration/CLI tests prove preflight-before-allocation, one lease, no external process termination, atomic final publication, resumable complete checkpoints, cleanup of incomplete staging, redaction, and documented exits |
| 7 — Adapter activation | T116 | Verified adapter-manifest loader and fine-tuned/fine-tuned-RAG registry availability | Wave 6 final adapter contract stable | Contract tests reject missing/tampered files, aggregate-hash drift, unsafe paths, wrong model ID/revision, and incomplete manifests; a valid manifest activates only its compatible strategies |
| 8 — Independent US5 gate | Checkpoint | Published manifest → canonical build → mocked SFT → verified registration, followed by one opt-in local QLoRA smoke | Waves 1–7 | Full CPU gate passes; planted leakage blocks publication; smoke run records pinned inputs, hardware, effective config, duration, peak VRAM, checkpoints, adapter file hashes, and aggregate identity |

Tasks marked `[P]` may proceed concurrently only after Wave 0 freezes their shared formats. The four
category files have separate owners, while schema, manifest, CLI registration, and strategy
registry changes remain serialized. Real GPU training starts only after the published dataset gate
passes; a successful fake trainer run is not evidence that the 12 GB GPU can execute the selected
configuration.

### Dataset Contract and Governance Rules

- The example schema records stable ID, scenario/target content, source type, source URI when
  applicable, license or explicit usage authorization, creation method, `pt-BR`, one or more
  supported categories, all known lineage parents, review status, reviewer/timestamp for terminal
  reviews, and canonical content hash. Unknown fields fail closed.
- Native authored examples follow `draft → under_review → approved|rejected`. Terminal review
  records are immutable. Import compatibility may report malformed legacy records as findings, but
  may not weaken the native domain constructor or silently promote them into a published version.
- Canonical hashes are computed from the versioned semantic payload, excluding storage paths,
  timestamps, reviewer identity, and formatting-only JSON differences. The schema version and hash
  algorithm are explicit so future formats can coexist without reinterpretation.
- The manifest assigns each included example exactly once to `train`, `validation`, or fixed
  `evaluation`; records one lineage group; references exact source-file and target hashes; and
  freezes its own canonical hash on publication. Rebuilding the same inputs produces byte-identical
  training rows and identities.
- Missing/unauthorized license, incomplete provenance, non-approved membership, unreviewed
  synthetic content, hash mismatch, unresolved sensitive-content finding, or schema failure is
  blocking. Suspected sensitive data requires human disposition; an automated pattern match never
  becomes silent approval or silent deletion.
- Exact and normalized duplicates are deterministic. They block publication when the same content
  or family crosses into fixed evaluation and are reported within a split for curator cleanup.
  Lineage is evaluated transitively, not only from direct parents, and cycles or missing parents
  are blocking manifest defects.
- Semantic similarity only creates review candidates in this phase; it never silently rejects an
  example. Publication remains blocked while a cross-split candidate is unresolved. A reviewer
  either links the examples into one lineage family and repartitions them or records an auditable
  non-duplicate disposition.
- Fixed evaluation families are selected before any synthetic expansion. Later derived examples
  inherit their family and cannot enter training or validation when that family is reserved for
  evaluation.

### Canonical Build and Publication Rules

- `dataset validate` executes schema, hash, review, provenance/license, privacy, duplicate,
  lineage, partition, and unresolved-semantic-review checks through one application service. It
  returns all findings in deterministic order instead of stopping at the first invalid example.
- `dataset build` accepts only a validation-clean, immutable manifest. It emits canonical JSONL
  containing the declared prompt/chat representation, assistant completion, schema version,
  example and lineage identities, and assistant-only loss metadata. Rejected or ineligible records
  remain visible in a separate exclusion report.
- Output is written to a sibling temporary path, flushed, hashed, and atomically renamed. Existing
  output is never overwritten. Failure removes incomplete temporary files while leaving the source
  manifest untouched.
- The build manifest records source dataset version/hash, schema versions, ordered member IDs,
  split counts, included/excluded identities and reasons, exact output-file hashes, builder version,
  and creation command inputs. Paths are project-relative where practical and never escape the
  configured roots.
- The 100 candidates are balanced across the four initial categories: each category starts with
  five complete, five incomplete, five contradictory, five simple-wins, and five adversarial
  cases. The initial split target is 20 train, 2 validation, and 3 evaluation candidates per
  category, subject to moving an entire lineage family together. Rejected candidates remain in
  accounting and are not backfilled silently; balance is reported after review and never overrides
  lineage isolation or human rejection.

### QLoRA Runtime and Artifact Rules

- Model configuration pins `Qwen/Qwen3-4B-Instruct-2507` plus one immutable, resolvable revision,
  safe tensor loading, and `trust_remote_code=false`. Training configuration validates every value
  before importing Torch or allocating GPU memory and captures the fully resolved effective config.
- The production trainer is loaded lazily behind the existing narrow trainer boundary. It uses
  Transformers, TRL `SFTTrainer`, PEFT LoRA, bitsandbytes 4-bit loading, Accelerate, deterministic
  seeds where supported, and a collator/mask whose loss applies only to assistant completion
  tokens. Prompt and padding tokens must be demonstrably ignored in tests.
- The service validates dataset/build hashes and available disk, performs sanitized GPU preflight,
  then acquires the existing exclusive lease before model allocation. It reports external blockers
  but never downloads a model implicitly, kills a process, unloads LM Studio, or weakens the lease.
- A training run uses a unique staging directory. Effective config and input identities are written
  before execution. Checkpoints become resumable only after their trainer state and file hashes are
  complete; incomplete checkpoint directories are ignored and removed during reconciliation.
- Cancellation is cooperative. Failure or cancellation removes incomplete adapter staging and
  preserves only complete checkpoints and sanitized diagnostics permitted by retention policy.
  Final adapter publication occurs only after all files are closed, individually hashed, and moved
  atomically through the artifact service.
- The adapter manifest includes schema version, base model ID/revision, dataset/build/manifest
  identities, effective training config hash, code revision, ordered relative adapter files with
  sizes and SHA-256 hashes, aggregate canonical hash, timestamps, duration, terminal outcome, and
  measured hardware/peak VRAM when available. Hashing only the first adapter file is invalid.
- Resume requires the same base model, dataset build, effective configuration, and code-compatible
  checkpoint contract. A mismatch fails before training; `--resume` never silently starts a new run
  or overwrites a completed adapter.

### Fine-Tuned Strategy Registration Rules

- The manifest loader validates the closed schema, normalized paths under the artifact root, every
  declared file size/hash, aggregate hash, and artifact retention before exposing adapter identity.
- The configured runtime base model ID and immutable revision must exactly match the adapter
  manifest. Missing revision, aliases, or a GGUF with merely a similar display name do not count as
  compatible.
- Registry availability is derived from enabled configuration, verified adapter artifact, matching
  base runtime, and existing retrieval requirements. Stable reason codes distinguish absent,
  malformed, tampered, incompatible, and runtime-unavailable adapters.
- Fine-tuned and fine-tuned-RAG strategies reuse the existing generation and retrieval contracts.
  Registration adds adapter loading/composition only; it does not bypass `StrategyInput`, snapshot
  equivalence, raw-output preservation, validation, telemetry, or blind comparison rules.

### Test-First Work per Wave

- T094 exercises legal and illegal review/version transitions, reviewer metadata, category and
  language bounds, unique membership, publication hash requirements, terminal immutability, and
  round trips through every versioned schema.
- T095 uses generated permutations and planted fixtures for exact and normalization-equivalent
  content, transitive lineage, cycles, missing parents, same-split duplicates, and train/validation
  versus evaluation leaks. Finding order and blocking severity are deterministic.
- T096 covers authored, synthetic, and public-derived provenance; missing or incompatible licenses;
  unreviewed synthetic data; representative CPF/payment/secret/confidential indicators; false-
  positive disposition; and absence of sensitive values from logs and CLI details.
- T097 invokes the real Typer application and asserts human/JSON output, stable exit codes
  `0/2/3/4/1`,
  complete findings, exclusions, atomic build behavior, immutable inputs/outputs, canonical bytes,
  and repeatable hashes.
- T098 injects a fake trainer/resource/artifact boundary to cover config parsing, lazy imports,
  completion masks, checkpoint completeness and ordering, resume compatibility, cancellation,
  multi-file adapter manifests, atomic publication, and cleanup after each failure point.
- T099 is marked `gpu`, opt-in, and excluded from default CI. It uses only the smoke config, records
  exact model revision and dataset/config hashes, and fails honestly with actionable preflight
  evidence when local capacity is insufficient.
- Dataset/training CLI semantics retain the shared contract: `0` success, `2` invalid input or
  schema/configuration, `3` failed policy/resource precondition, `4` unavailable model/integration,
  and `1` execution failure or a cooperatively handled cancellation. Progress stays on stderr and
  the final JSON value on stdout.
- Schema tests validate both accepted fixtures and deliberately incompatible future/unknown fields.
  Corpus tests validate every one of the 100 records without requiring a model or network access.

### Phase 7 Constitution Check

| Principle | Phase 7 design evidence | Status |
| --- | --- | --- |
| Evidence Before Claims | Curated targets retain facts/assumptions and review metadata; capacity and quality claims require measured smoke/benchmark evidence | PASS |
| Reproducible and Honest Experiments | Immutable dataset/build/config/model/code identities, complete adapter file hashes, effective config, checkpoints, telemetry, and explicit failures | PASS |
| Dataset Integrity and Human Review | Approval/license/provenance gates, fixed evaluation families, transitive lineage isolation, sensitive-data disposition, and immutable publication | PASS |
| Contracts and Tests | Versioned closed schemas, shared validators/builders, stable CLI findings/exits, fake-trainer tests, corpus validation, and opt-in GPU smoke | PASS |
| Local-First Security and Resource Safety | Native local execution, lazy model load after disk/GPU preflight and exclusive lease, safe paths, redaction, and no external process termination | PASS |
| Simplicity With Measured Evolution | Git manifests remain the dataset authority; existing artifact/resource/strategy boundaries are reused without a database, broker, remote trainer, or semantic store | PASS |

Post-design review found no constitutional violation. Human semantic review remains intentionally
manual because automating it would add an unproven model dependency to the publication gate. The
GPU smoke remains opt-in, but all configuration, policy, artifact, and registration behavior is
covered by the mandatory CPU-safe gate.

### SOLID Design Review

| Principle | Status | Evidence and proportional decision |
| --- | --- | --- |
| SRP | Atendido | Dataset policy stays in `datasets`, ML construction in `training.sft`, resource/artifact orchestration in `training.service`, and presentation in Typer adapters; changes have distinct actors and test boundaries |
| OCP | Atendido | Versioned schemas/configuration and the existing trainer/strategy boundaries cover the demonstrated variations—fake versus TRL trainer and baseline versus adapter—without a new generic plugin framework |
| LSP | Atendido with contract gate | Fake and production trainers must satisfy the same train/save/resume/cancel observable contract; shared contract tests prevent production-only strengthening or silent fallback |
| ISP | Atendido | Dataset commands consume validation/build capabilities, training consumes only resource/artifact/trainer capabilities, and strategy registration consumes only verified adapter metadata |
| DIP | Atendido | Domain governance is framework-free; high-level training orchestration receives trainer, resource, lease, clock/progress, and artifact boundaries while Torch/TRL/filesystem details stay at the edge |

The proportional recommendation is to keep the existing modular boundaries and complete their
contracts. Do not add repositories, factories, or provider hierarchies solely for this phase. The
material correction is to move direct output-directory publication out of the SFT core into the
artifact-aware training service and to keep CLI policy-free.

### Completion Gate

Phase 7 is complete only when T094–T116 and all conditions below hold together:

1. The published `v0.1.0` manifest and every referenced example/target validate against versioned
   schemas; all 100 candidates are explicitly approved/included or rejected/excluded with source,
   authorization, category, language, creation method, lineage, and reviewer evidence.
2. Exact, normalized, confirmed-semantic, and transitive lineage families cannot cross into fixed
   evaluation. A planted leak, unresolved semantic candidate, missing parent, cycle, hash mismatch,
   unreviewed synthetic record, or unresolved sensitive-content finding blocks publication.
3. A clean manifest builds byte-identical completion-only training artifacts and manifests on
   repeated CPU runs. Invalid records and exclusions remain visible, sources are unchanged, and no
   partial or pre-existing output is overwritten.
4. The mocked SFT pipeline validates pinned inputs before ML import/allocation, masks prompt tokens,
   resumes only a compatible complete checkpoint, responds to cancellation, publishes all adapter
   files atomically, and preserves a canonical manifest with no secret or unsafe path.
5. A fine-tuned strategy remains unavailable until every adapter file/hash and exact base model
   revision verify. Tampering or mismatch produces a stable unavailable reason and never falls back
   to another strategy.
6. Formatting, linting, strict typing, schema validation, dataset/corpus validation, unit/property/
   contract/integration tests, secret scanning, and the published-manifest-to-fake-adapter vertical
   slice pass CPU-only without network, model packages, GPU, or live Knowledge Hub.
7. One opt-in local smoke either completes and records model/dataset/config/code identities,
   checkpoints, duration, hardware, peak VRAM, and final adapter manifest, or fails at preflight with
   honest diagnostics. A capacity failure does not invalidate the CPU implementation gate and is
   not reported as a successful training result.

### Risks and Controls

| Risk | Control |
| --- | --- |
| Existing partial files are mistaken for completed tasks | Audit every T094–T116 item against its exit evidence and keep task state tied to passing behavior, not file presence |
| Evaluation contamination hides behind paraphrase or indirect ancestry | Normalize deterministically, traverse lineage transitively, require semantic-candidate disposition, and reserve evaluation families before expansion |
| Automated privacy scan creates false confidence | Treat patterns as review triggers, require human disposition, and block unresolved findings without claiming exhaustive detection |
| Four parallel authors drift from the contract or category balance | Freeze schemas first, validate each file independently, report balance, and centralize final review/publication in T111 |
| Training configuration exceeds 12 GB VRAM | Validate before allocation, use a small opt-in smoke config, acquire the exclusive lease, measure peak VRAM, and make no unmeasured capacity promise |
| Optional ML imports break CPU development or CI | Lazy-load the production trainer and exercise orchestration through fakes with ML extras absent |
| Resume mixes incompatible inputs or silently starts over | Bind checkpoints to exact model, dataset build, config, and code-compatible contract; fail closed on mismatch |
| Multi-file adapter is only partially hashed or published | Hash every file, derive one canonical aggregate identity, stage under a unique path, and publish atomically through the artifact service |
| Tampered or wrong-base adapter becomes selectable | Verify closed manifest, safe paths, file sizes/hashes, aggregate hash, retention, and exact model revision before registry activation |
| CLI, builder, and domain validators diverge | One application validation/build pipeline supplies CLI and tests; adapters contain no governance policy |

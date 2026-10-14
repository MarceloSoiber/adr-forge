# Tasks: Architecture Decision Lab

**Input**: Design documents from `specs/001-architecture-decision-lab/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`

**Tests**: Required by the project constitution and the user-requested automated validation. Write
story tests first and confirm they fail before implementing the story.

**Organization**: Tasks are grouped by user story and ordered by dependency. Each task names its
primary output path.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Safe to execute in parallel with adjacent tasks because it targets different files and
  does not depend on unfinished work.
- **[Story]**: Maps to a prioritized user story in `spec.md`.

## Phase 1: Setup

**Tracking**: GitHub issue [#1](https://github.com/MarceloSoiber/adr-forge/issues/1)

**Purpose**: Establish the reproducible Python, TypeScript, test, and CPU-build toolchains.

- [X] T001 Create the planned package, app, dataset, config, test, and local-runtime directory structure with package markers under `src/adr_forge/`, `apps/api/`, `apps/web/`, `datasets/`, `configs/`, `tests/`, and `var/.gitkeep`
- [X] T002 Configure Python 3.12, runtime dependencies, `dev` and `ml` optional groups, and the `adr-forge` CLI entry point in `pyproject.toml`
- [X] T003 [P] Generate the React + TypeScript + Vite application and scripts in `apps/web/package.json`, `apps/web/tsconfig.json`, and `apps/web/vite.config.ts`
- [X] T004 [P] Add Python caches, Node artifacts, `.env`, SQLite files, Hugging Face caches, models, adapters, checkpoints, private snapshots, and `var/` outputs to `.gitignore`
- [X] T005 [P] Document loopback, SQLite, artifact quota, Knowledge Hub, Hugging Face, and model settings without real secrets in `.env.example`
- [X] T006 [P] Configure Ruff, mypy, Pytest markers (`gpu`, `live_integration`), coverage, and asyncio behavior in `pyproject.toml`
- [X] T007 [P] Configure ESLint, Prettier, Vitest, Testing Library, and Playwright in `apps/web/eslint.config.js`, `apps/web/vitest.config.ts`, and `apps/web/playwright.config.ts`
- [X] T008 Add CPU-only quality jobs for Python, frontend, dataset fixtures, secret scanning, and dependency auditing in `.github/workflows/ci.yml`
- [X] T009 [P] Add CPU-safe multi-stage API and static web builds plus loopback defaults in `Dockerfile`, `apps/web/Dockerfile`, and `compose.yaml`
- [X] T010 Update local setup, architecture links, Spec Kit workflow, and no-production warning in `README.md`

**Checkpoint**: Empty application skeleton installs, lints, tests, and builds without downloading a model.

---

## Phase 2: Foundational Components

**Tracking**: GitHub issue [#3](https://github.com/MarceloSoiber/adr-forge/issues/3)

**Purpose**: Implement shared contracts, persistence, artifacts, resource safety, and delivery shells that block every story.

**Critical**: No user story implementation starts before this phase passes CPU-only tests.

- [X] T011 [P] Implement UUID generation, timezone-aware clock, canonical JSON, and SHA-256 helpers in `src/adr_forge/shared/identity.py`, `src/adr_forge/shared/time.py`, and `src/adr_forge/shared/hashing.py`
- [X] T012 [P] Implement environment configuration with loopback-only host validation, 50 GB artifact limit, 40 GB warning, 5 GiB free-disk reserve, secret fields, and typed paths in `src/adr_forge/shared/config.py`
- [X] T013 Implement async SQLite engine, WAL configuration, session factory, and unit-of-work boundaries in `src/adr_forge/persistence/database.py` and `src/adr_forge/persistence/unit_of_work.py`
- [X] T014 Initialize Alembic and establish its `alembic_version` table as the sole schema-version authority in `alembic.ini`, `alembic/env.py`, and `alembic/versions/0001_schema_version.py`
- [X] T015 [P] Implement RFC 9457-style problem details, stable error codes, and exception mapping in `src/adr_forge/shared/errors.py` and `src/adr_forge/api/problem_details.py`
- [X] T016 [P] Implement structured logging with request/run correlation and redaction of tokens, prompts, and retrieved content in `src/adr_forge/shared/logging.py`
- [X] T017 Create the Artifact and ArtifactReference persistence models and migration with registered owner types, `relative_path` constrained under the artifact root, `sha256` exactly 64 lowercase hex characters, `size_bytes` non-negative, and retention in `keep|prunable|temporary` in `src/adr_forge/artifacts/models.py` and `alembic/versions/0002_artifacts.py`
- [X] T018 Implement atomic temporary-write, SHA-256 move, normalized path, reference-registry-safe delete, stale-temporary reconciliation, and lookup behavior in `src/adr_forge/artifacts/store.py`
- [X] T019 [P] Add property tests for path traversal, hash stability, atomic failure cleanup, and referenced deletion refusal in `tests/unit/artifacts/test_store.py`
- [X] T020 Implement artifact quota accounting, warning at 40 GB, hard limit at 50 GB, free-disk reserve, list, and prune use cases in `src/adr_forge/artifacts/service.py`
- [X] T021 [P] Implement sanitized RAM, disk, NVIDIA GPU, VRAM, and active-process probes without terminating processes in `src/adr_forge/system/resources.py`
- [X] T022 Implement the exclusive cross-process GPU lease and preflight result contract in `src/adr_forge/system/gpu_lease.py`
- [X] T023 [P] Add CPU-fixture tests for insufficient VRAM, external LM Studio blocker reporting, lease exclusion, and secret-free diagnostics in `tests/unit/system/test_gpu_preflight.py`
- [X] T024 Implement in-process progress publication, cancellation token, and current-state snapshot interfaces in `src/adr_forge/system/progress.py`
- [X] T025 [P] Define model runtime, retrieval provider, strategy, repository, transaction, disk-capacity, artifact-reference, progress, and diagnostic protocols in `src/adr_forge/shared/ports.py`
- [X] T026 Implement application factory, loopback CORS, request IDs, lifespan reconciliation hook, `/health`, `/readiness`, `/system/resources`, and integration status routes in `apps/api/main.py` and `src/adr_forge/api/routes/system.py`
- [X] T027 Implement the Typer root command and read-only `adr-forge doctor` human/JSON outputs with documented exit codes in `src/adr_forge/cli/main.py` and `src/adr_forge/cli/doctor.py`

**Checkpoint**: Foundation passes with temporary SQLite, temporary artifact roots, fake resource probes, and no live LLM.

---

## Phase 3: User Story 1 — Analyze an architecture decision (P1) MVP

**Tracking**: GitHub issue [#5](https://github.com/MarceloSoiber/adr-forge/issues/5)

**Goal**: Submit a complete scenario, run one baseline strategy with progress, validate a structured ADR, and export Markdown.

**Independent Test**: With a fake model runtime, create a scenario, start a run, observe terminal progress, retrieve a valid ADR, and export it without Knowledge Hub or GPU.

### Tests first

- [X] T028 [P] [US1] Add unit tests for immutable first-revision numbering, canonical hashes, per-scenario duplicate rejection, and one/multiple/unsupported category values in `tests/unit/scenarios/test_scenario.py`
- [X] T029 [P] [US1] Add unit and property tests for provisional versus conclusive ADR invariants, including maximum three questions, at least two viable alternatives, negative consequences, and measurable review triggers in `tests/unit/decisions/test_adr_validation.py`
- [X] T030 [P] [US1] Add contract tests for scenario, run, progress, ADR, problem-details, and export payloads against `contracts/api.openapi.yaml` in `tests/contract/test_analysis_api.py`
- [X] T031 [P] [US1] Add a fake-runtime end-to-end API test from scenario creation through Markdown export in `tests/integration/test_analysis_vertical_slice.py`
- [X] T032 [P] [US1] Add frontend tests for scenario submission, progress reconnect, validation failure, ADR sections, and export action in `apps/web/src/features/analysis/AnalysisFlow.test.tsx`

### Domain and persistence

- [X] T033 [P] [US1] Implement `DecisionScenario` with title 3–200 characters, language initially `pt-BR`, current revision at least 1, and `ScenarioRevision` with problem 20–20,000 characters, item limits from `data-model.md`, unique `(scenario_id, revision_number)`, and immutable `content_hash` in `src/adr_forge/scenarios/models.py`
- [X] T034 [US1] Create scenario and revision tables, indexes, repository, and first-revision transaction in `alembic/versions/0003_scenarios.py` and `src/adr_forge/scenarios/repository.py`
- [X] T035 [US1] Implement scenario creation, supported-category classification contract, retrieval, and current-revision use cases in `src/adr_forge/scenarios/service.py`
- [X] T036 [P] [US1] Implement the versioned `ADRDraft` schema with title 3–200 characters, confidence 0.0–1.0, maximum three unresolved questions, and structured facts, assumptions, alternatives, rationale links, consequences, risks, and metric/operator/threshold review triggers in `src/adr_forge/decisions/schemas.py`
- [X] T037 [US1] Implement shared deterministic ADR rules and machine-readable findings used by the app, CLI, benchmark, and tests in `src/adr_forge/decisions/validation.py`
- [X] T038 [P] [US1] Implement stable JSON and Markdown ADR rendering without adding missing content in `src/adr_forge/decisions/rendering.py`
- [X] T039 [P] [US1] Implement versioned `AnalysisStrategy` configuration and a minimal in-memory registry for fake and Qwen baseline entries with kind, model identity/revision, prompt version, generation-config hash, retrieval requirement, runtime kind, enabled state, and availability in `src/adr_forge/strategies/models.py` and `src/adr_forge/strategies/registry.py`
- [ ] T040 [US1] Implement the structured-output baseline, deterministic fake strategy, and lazy Qwen Transformers runtime adapter with pinned `Qwen/Qwen3-4B-Instruct-2507`, `trust_remote_code=false`, configurable revision, typed generation telemetry, and cooperative stopping criteria in `src/adr_forge/strategies/base.py`, `src/adr_forge/strategies/fake.py`, and `src/adr_forge/strategies/qwen_runtime.py`; add an opt-in `gpu` smoke test in `tests/integration/test_qwen_baseline.py`
- [ ] T041 [US1] Implement raw-output preservation, structured parse, exactly one repair attempt, and distinct original/repaired validation results in `src/adr_forge/decisions/parsing.py`
- [ ] T042 [P] [US1] Implement `AnalysisRun` with the exact state set and legal transitions from `data-model.md`, non-negative telemetry, sanitized failure detail at most 2,000 characters, and immutable terminal state in `src/adr_forge/experiments/run_models.py`
- [ ] T043 [US1] Create run and ADR tables, terminal-state constraints, indexes, repositories, and the minimal SQL artifact/reference catalog required to own original and repaired outputs in `alembic/versions/0004_analysis_runs.py`, `src/adr_forge/experiments/run_repository.py`, and `src/adr_forge/artifacts/repository.py`
- [ ] T044 [US1] Implement one serialized inference executor with off-event-loop generation, persisted state snapshots, an async SSE subscription adapter over progress callbacks, cooperative cancellation, GPU preflight/lease only for GPU-backed runtimes, and startup conversion of abandoned non-terminal records to `interrupted` in `src/adr_forge/strategies/executor.py` and `src/adr_forge/system/progress.py`
- [ ] T045 [US1] Implement create-run, execute-baseline, validate, persist raw output, persist ADR, cancel, and export application use cases in `src/adr_forge/decisions/service.py`

### API and web

- [ ] T046 [US1] Implement `POST /scenarios` and `GET /scenarios/{scenarioId}` in `src/adr_forge/api/routes/scenarios.py`
- [ ] T047 [US1] Mount the versioned `/api/v1` router, normalize request validation as problem details, implement minimal `GET /strategies`, and implement run creation/status/cancel/ADR/export endpoints plus race-free best-effort SSE that subscribes before emitting persisted state in `apps/api/main.py`, `src/adr_forge/api/problem_details.py`, `src/adr_forge/api/routes/strategies.py`, and `src/adr_forge/api/routes/analysis_runs.py`
- [ ] T048 [P] [US1] Implement a typed client with configurable `VITE_API_BASE_URL`, problem handling, and owned EventSource reconnect logic that reads persisted state before reconnecting in `apps/web/src/services/api.ts` and `apps/web/src/services/runEvents.ts`
- [ ] T049 [US1] Implement the Portuguese scenario form, strategy picker, progress panel, ADR review, limitation notice, and Markdown export in `apps/web/src/features/analysis/ScenarioForm.tsx`, `RunProgress.tsx`, and `AdrView.tsx`

**Checkpoint**: MVP demo works with fake runtime in CI and real Qwen through an opt-in local GPU test.

---

## Phase 4: User Story 2 — Clarify insufficient or contradictory context (P1)

**Goal**: Ask focused questions or produce a clearly provisional ADR without mutating prior evidence.

**Independent Test**: Submit an incomplete fixture, receive at most three relevant questions, answer them, and verify a new scenario revision and run while the originals stay unchanged.

### Tests first

- [X] T050 [P] [US2] Add adverse-case tests for missing scale, contradictory cost/availability, forced technology preference, and unanswered questions in `tests/benchmark/test_clarification_cases.py`
- [X] T051 [P] [US2] Add scenario-revision API contract and stale-base conflict tests in `tests/contract/test_scenario_revisions_api.py`
- [X] T052 [P] [US2] Add frontend tests for displaying impact-aware questions, provisional continuation, and revision resubmission in `apps/web/src/features/clarification/ClarificationFlow.test.tsx`

### Implementation

- [X] T053 [US2] Add clarification question and answer value objects with question/answer limits and required source run linkage in `src/adr_forge/scenarios/clarification.py`
- [X] T054 [US2] Extend decision validation to classify missing critical context, contradictory constraints, provisional output, and confidence reduction in `src/adr_forge/decisions/validation.py`
- [X] T055 [US2] Implement immutable clarification-answer revision creation with optimistic base revision checks in `src/adr_forge/scenarios/service.py`
- [X] T056 [US2] Implement `POST /scenarios/{scenarioId}/revisions` and return HTTP 409 for stale bases in `src/adr_forge/api/routes/scenarios.py`
- [X] T057 [P] [US2] Add reviewed incomplete and contradictory Portuguese fixtures for all four categories in `datasets/fixtures/clarification.jsonl`
- [X] T058 [US2] Implement the Portuguese clarification panel, provisional action, and new-revision workflow in `apps/web/src/features/clarification/ClarificationPanel.tsx`

**Checkpoint**: US1 complete scenarios and US2 incomplete scenarios both work independently.

---

## Phase 5: User Story 3 — Compare modeling strategies (P2)

**Goal**: Run equivalent inputs through multiple strategies and perform a blinded human comparison.

**Independent Test**: Use a stored Knowledge Hub fixture to create one retrieval snapshot, run two strategies against identical input, submit rubric scores without identities, then reveal the mapping.

### Tests first

- [X] T059 [P] [US3] Add mocked Knowledge Hub request/response, timeout, retry, auth failure, and schema failure contract tests in `tests/contract/test_knowledge_hub.py`
- [X] T060 [P] [US3] Add snapshot canonicalization tests proving ordered content, hashes, query, filters, scores, match reasons, and embedding identity remain immutable in `tests/unit/retrieval/test_snapshot.py`
- [X] T061 [P] [US3] Add strategy-equivalence tests proving RAG strategies in one comparison receive the same snapshot and generation configuration in `tests/integration/test_strategy_equivalence.py`
- [X] T062 [P] [US3] Add blind-comparison state tests proving identity cannot be revealed before immutable evaluation submission in `tests/unit/evaluation/test_blinding.py`
- [X] T063 [P] [US3] Add frontend comparison tests for randomized labels, rubric scoring, preference/tie, notes, and post-submit reveal in `apps/web/src/features/comparison/BlindComparison.test.tsx`

### Retrieval and strategies

- [X] T064 [P] [US3] Implement `RetrievalSnapshot` with non-empty query, validated filters, provider/embedding identity, canonical content hash, and ordered exact chunk artifact in `src/adr_forge/retrieval/models.py`
- [X] T065 [US3] Create retrieval snapshot table, indexes, artifact reference, and repository in `alembic/versions/0007_retrieval_snapshots.py` and `src/adr_forge/retrieval/repository.py`
- [X] T066 [US3] Implement the Knowledge Hub REST adapter with 2-second connect timeout, 15-second total timeout, one retry only for connection/408/429/5xx, bearer redaction, and fail-closed required fields in `src/adr_forge/retrieval/knowledge_hub.py`
- [ ] T067 [P] [US3] Implement file-backed `SnapshotRetrievalProvider` for tests, CI, and exact experiment replay in `src/adr_forge/retrieval/snapshot_provider.py`
- [ ] T068 [US3] Implement atomic retrieval snapshot creation and reuse use cases in `src/adr_forge/retrieval/service.py`
- [ ] T069 [P] [US3] Extend the Phase 3 baseline for comparable experiment inputs and implement the versioned structured-prompt strategy in `src/adr_forge/strategies/base.py` and `src/adr_forge/strategies/prompted.py`
- [ ] T070 [US3] Implement RAG and fine-tuned-RAG composition that treats chunks as quoted untrusted evidence and requires a snapshot in `src/adr_forge/strategies/rag.py`
- [ ] T071 [US3] Extend the Phase 3 registry and `GET /strategies` behavior with missing-adapter, missing-snapshot, Knowledge Hub, RAG, and fine-tuned availability in `src/adr_forge/strategies/registry.py` and `src/adr_forge/api/routes/strategies.py`

### Blind evaluation

- [ ] T072 [P] [US3] Implement `BlindComparison` and immutable `EvaluationResult` with randomized labels, evaluator type, preference/tie, notes at most 5,000 characters, and rubric linkage in `src/adr_forge/evaluation/models.py`
- [ ] T073 [US3] Create comparison/evaluation tables and repositories in `alembic/versions/0006_blind_evaluation.py` and `src/adr_forge/evaluation/repository.py`
- [ ] T074 [US3] Implement create, retrieve-blinded, submit-once, supersede-correction, and reveal-after-submit services in `src/adr_forge/evaluation/blind_service.py`
- [ ] T075 [US3] Implement comparison create/get/evaluate/reveal endpoints in `src/adr_forge/api/routes/comparisons.py`
- [X] T076 [US3] Implement the blind comparison page, rubric controls, preference, notes, and post-submit identity reveal in `apps/web/src/features/comparison/BlindComparison.tsx`

**Checkpoint**: Two or more strategies are comparable without identity or retrieval-context leakage.

---

## Phase 6: User Story 4 — Run a reproducible benchmark (P2)

**Goal**: Execute and report a fixed scenario-strategy matrix with deterministic and human evidence.

**Independent Test**: Run the same snapshot benchmark twice, reproduce deterministic findings, and account for every expected run as complete, failed, excluded, or missing.

### Tests first

- [ ] T077 [P] [US4] Add experiment lifecycle and complete/partial accounting tests in `tests/unit/experiments/test_experiment.py`
- [ ] T078 [P] [US4] Add deterministic evaluator tests for structure, alternatives, negative consequences, review triggers, assumption labeling, references, and missing-context handling in `tests/unit/evaluation/test_deterministic.py`
- [ ] T079 [P] [US4] Add resume tests proving completed runs are immutable and only missing matrix cells are scheduled in `tests/integration/test_benchmark_resume.py`
- [ ] T080 [P] [US4] Add report tests proving failures, exclusions, latency, resources, model/dataset/rubric/config identities, and unfavorable results are visible in `tests/integration/test_benchmark_report.py`
- [ ] T081 [P] [US4] Add CLI contract tests for benchmark exit codes, progress streams, partial status, and JSON output in `tests/contract/test_benchmark_cli.py`

### Evaluation and experiment model

- [ ] T082 [P] [US4] Implement immutable `RubricVersion` with unique name/version, SHA-256 content hash, integer score anchors, and the nine initial quality dimensions in `src/adr_forge/evaluation/rubric.py`
- [ ] T083 [US4] Implement the shared deterministic evaluator and aggregate finding format in `src/adr_forge/evaluation/deterministic.py`
- [ ] T084 [P] [US4] Implement `Experiment` with name 3–200 characters, frozen code/config/dataset/rubric identities, exact expected-run count, and states `draft|running|completed|partial|failed|cancelled` in `src/adr_forge/experiments/models.py`
- [ ] T085 [US4] Create experiment/rubric tables, matrix indexes, and repositories in `alembic/versions/0007_experiments.py` and `src/adr_forge/experiments/repository.py`
- [ ] T086 [US4] Implement experiment creation that freezes scenario revisions, strategy versions, retrieval snapshots, generation settings, rubric, dataset, and code revision in `src/adr_forge/experiments/service.py`
- [ ] T087 [US4] Implement matrix execution, explicit failure/exclusion records, resume of missing cells, and terminal accounting in `src/adr_forge/experiments/runner.py`
- [ ] T088 [US4] Implement report aggregation, tuned-versus-strongest-baseline comparison, SC-009 decision, and reproducibility manifest in `src/adr_forge/experiments/reporting.py`

### CLI, API, and web

- [ ] T089 [US4] Implement `adr-forge benchmark run` with foreground execution, progress, resume, and complete/partial exit semantics in `src/adr_forge/cli/benchmark_run.py`
- [ ] T090 [P] [US4] Implement `adr-forge benchmark report` with Markdown and JSON outputs in `src/adr_forge/cli/benchmark_report.py`
- [ ] T091 [US4] Implement experiment create/get/runs/report endpoints in `src/adr_forge/api/routes/experiments.py`
- [ ] T092 [P] [US4] Add the versioned default rubric and fake smoke benchmark configuration in `configs/evaluation/architecture-v1.yaml` and `configs/evaluation/smoke.yaml`
- [ ] T093 [US4] Implement experiment status, per-run accounting, metrics, failures, exclusions, and report download UI in `apps/web/src/features/experiments/ExperimentReport.tsx`

**Checkpoint**: Reproducible benchmark reports are possible before fine-tuning exists.

---

## Phase 7: User Story 5 — Curate trustworthy experiment data (P3)

**Goal**: Publish a reviewed, contamination-safe dataset and train a reproducible QLoRA adapter.

**Independent Test**: Build a version from reviewed examples, reject a planted lineage leak, run a mocked SFT pipeline, then complete one opt-in QLoRA smoke run that produces a hashed adapter manifest.

### Tests first

- [ ] T094 [P] [US5] Add schema and state tests for dataset examples, review transitions, published-version immutability, and partition membership in `tests/unit/datasets/test_models.py`
- [ ] T095 [P] [US5] Add hash, exact duplicate, normalized duplicate, lineage-group, and planted cross-split leakage tests in `tests/unit/datasets/test_contamination.py`
- [ ] T096 [P] [US5] Add provenance, missing license, unauthorized source, unreviewed synthetic, and suspected sensitive-content tests in `tests/unit/datasets/test_governance.py`
- [ ] T097 [P] [US5] Add CLI tests for dataset validate/build findings, exclusions, exit codes, and immutable manifests in `tests/contract/test_dataset_cli.py`
- [ ] T098 [P] [US5] Add mocked SFT configuration, completion-only formatting, checkpoint, resume, adapter manifest, and failure cleanup tests in `tests/unit/training/test_sft.py`
- [ ] T099 [P] [US5] Add an opt-in `gpu` smoke test that records hardware, model revision, effective config, duration, and peak VRAM in `tests/integration/test_qwen_qlora_smoke.py`

### Dataset domain and tooling

- [ ] T100 [P] [US5] Implement `DatasetExample` with source type, required license, `pt-BR` language, categories, lineage parents, `draft|under_review|approved|rejected` state, reviewer/time required for terminal review, and content hash in `src/adr_forge/datasets/models.py`
- [ ] T101 [P] [US5] Implement `DatasetVersion` states `building|validating|published|rejected` and membership in exactly one `train|validation|evaluation` split with lineage group in `src/adr_forge/datasets/versioning.py`
- [ ] T102 [US5] Define versioned JSON Schemas for examples, ADR targets, manifests, rubrics, and training data in `datasets/schemas/example-v1.json`, `adr-v1.json`, `manifest-v1.json`, and `rubric-v1.json`
- [ ] T103 [US5] Implement provenance, license, review-state, content-hash, and sensitive-data validators in `src/adr_forge/datasets/governance.py`
- [ ] T104 [US5] Implement exact/normalized duplicate detection and lineage-family split blocking, with semantic candidates reported for human review rather than silently rejected, in `src/adr_forge/datasets/contamination.py`
- [ ] T105 [US5] Implement canonical prompt-completion formatting with assistant-only loss metadata and exclusion reporting in `src/adr_forge/datasets/builder.py`
- [ ] T106 [US5] Implement `adr-forge dataset validate` and `adr-forge dataset build` in `src/adr_forge/cli/dataset.py`
- [ ] T107 [P] [US5] Author 25 Portuguese SQL-versus-NoSQL scenarios containing complete, incomplete, contradictory, simple-wins, and adversarial cases in `datasets/public/sql-vs-nosql.jsonl`
- [ ] T108 [P] [US5] Author 25 Portuguese synchronous-versus-asynchronous scenarios containing complete, incomplete, contradictory, simple-wins, and adversarial cases in `datasets/public/sync-vs-async.jsonl`
- [ ] T109 [P] [US5] Author 25 Portuguese modular-monolith-versus-microservices scenarios containing complete, incomplete, contradictory, simple-wins, and adversarial cases in `datasets/public/monolith-vs-microservices.jsonl`
- [ ] T110 [P] [US5] Author 25 Portuguese containers-versus-serverless-versus-traditional scenarios containing complete, incomplete, contradictory, simple-wins, and adversarial cases in `datasets/public/runtime-options.jsonl`
- [ ] T111 [US5] Review all 100 examples, attach source/license/lineage metadata, approve or reject each, define fixed evaluation families before synthetic expansion, and publish `datasets/manifests/v0.1.0.json`

### QLoRA training

- [ ] T112 [P] [US5] Define pinned model identity and smoke/full QLoRA configurations without guessed capacity claims in `configs/models/qwen3-4b-instruct-2507.yaml`, `configs/training/qwen3-4b-smoke.yaml`, and `configs/training/qwen3-4b-full.yaml`
- [ ] T113 [US5] Implement training configuration validation, effective-config capture, completion-only `SFTTrainer`, PEFT LoRA, 4-bit bitsandbytes loading, checkpoints, resume, and adapter manifest in `src/adr_forge/training/sft.py`
- [ ] T114 [US5] Implement exclusive GPU/disk preflight and atomic training-run artifact lifecycle in `src/adr_forge/training/service.py`
- [ ] T115 [US5] Implement `adr-forge train sft` progress, cancellation handling, human/JSON output, and documented exit codes in `src/adr_forge/cli/train.py`
- [ ] T116 [US5] Register a fine-tuned strategy from a verified adapter manifest and reject base-model/revision mismatches in `src/adr_forge/strategies/fine_tuned.py`

**Checkpoint**: The first adapter, dataset, and benchmark can be reproduced from published manifests.

---

## Phase 8: Polish and Cross-Cutting Validation

**Purpose**: Harden all stories, demonstrate recovery, and prepare honest portfolio evidence.

- [ ] T117 [P] Implement consistent SQLite backup plus schema revision, size, and SHA-256 manifest in `src/adr_forge/cli/database.py`
- [ ] T118 [P] Implement `adr-forge artifacts list|prune --confirm` and audit records for reclaimed bytes in `src/adr_forge/cli/artifacts.py`
- [ ] T119 [P] Add secret redaction, loopback rejection, artifact traversal, prompt-injection isolation, request/context limits, and unsafe model configuration tests in `tests/security/`
- [ ] T120 Add API compatibility validation against `specs/001-architecture-decision-lab/contracts/api.openapi.yaml` to `.github/workflows/ci.yml`
- [ ] T121 [P] Add a CPU-only GitLab test pipeline using fakes and snapshots, with no deployment or production Docker operations, in `.gitlab-ci.yml`
- [ ] T122 Add local performance instrumentation and a 100-scenario fake benchmark for progress, SQLite, report, and artifact overhead in `tests/performance/test_local_benchmark.py`
- [ ] T123 Execute backup/restore, API restart-to-interrupted, SSE reconnect, and safe-prune recovery tests in `tests/integration/test_recovery.py`
- [ ] T124 Run every CPU-safe command in `specs/001-architecture-decision-lab/quickstart.md` and correct documentation or code discrepancies in that file
- [ ] T125 Run the opt-in local Qwen baseline and QLoRA smoke gates, record hardware/config/results without committing private artifacts in `docs/experiments/0001-local-smoke.md`
- [ ] T126 Run the first fixed benchmark, preserve all failures/exclusions, and publish an honest reproducibility report in `docs/experiments/0002-baseline-vs-finetuned.md`
- [ ] T127 Expand `README.md` with architecture diagram, setup, safety boundary, dataset methodology, measured results, limitations, and links to the accepted ADRs and experiment reports

---

## Dependencies and Execution Order

### Phase dependencies

1. Setup has no dependencies.
2. Foundational depends on Setup and blocks all user stories.
3. US1 is the MVP and establishes scenario, run, ADR, executor, API, and UI foundations.
4. US2 depends on US1 scenario revisions and ADR validation.
5. US3 depends on US1 runs/ADRs; its Knowledge Hub work can begin after Foundation, but blind
   comparison integration needs completed run contracts.
6. US4 depends on US3 strategy identities and evaluation records; deterministic evaluator work can
   begin after US1.
7. US5 dataset governance can begin after Foundation, while QLoRA integration depends on US1 model
   runtime and US4 experiment/report contracts.
8. Polish depends on the stories selected for the release; T125–T127 require all stories.

### User story dependency graph

```text
Foundation
   |
   +--> US1 Analyze ADR ----> US2 Clarification
   |          |
   |          +-------------> US3 Strategy comparison ----> US4 Benchmark
   |                                   |                         |
   +--> US5 Dataset governance --------+-------------------------+
                                      QLoRA training/reporting
```

### Within each story

- Add and observe failing tests before implementation.
- Define domain schemas and legal transitions before persistence.
- Implement repositories before application services.
- Implement services before API/CLI/UI adapters.
- Re-run the independent story test at each checkpoint.

## Parallel Opportunities

- Setup T003–T007 and T009 can run in parallel after T001.
- Foundation artifact, resource, logging, and port tasks can run in parallel after configuration.
- US1 test tasks T028–T032 run in parallel; scenario and ADR schema work can run in parallel.
- US2 adverse fixtures, API tests, and frontend tests can run in parallel.
- US3 retrieval contract, snapshot, blinding, and frontend tests can run in parallel.
- US4 evaluator, experiment model, CLI contract, and frontend work can proceed in separate files.
- US5 four category-authoring tasks T107–T110 are deliberately parallel and merge into T111 review.
- Backup, artifact CLI, security tests, GitLab CI, and performance work can run in parallel in Polish.

## Parallel Examples

### US1

```text
T028 Scenario domain tests
T029 ADR invariant tests
T030 API contract tests
T032 Frontend analysis tests
```

### US3

```text
T059 Knowledge Hub contract tests
T060 Snapshot tests
T062 Blind comparison tests
T063 Frontend comparison tests
```

### US5

```text
T107 SQL versus NoSQL examples
T108 Synchronous versus asynchronous examples
T109 Modular monolith versus microservices examples
T110 Runtime deployment examples
```

## Implementation Strategy

### MVP first

1. Complete T001–T027.
2. Complete T028–T049.
3. Stop and validate the independent US1 vertical slice with fake runtime.
4. Run the optional Qwen baseline only after CPU gates pass and GPT-OSS is unloaded.

### Incremental delivery

1. Foundation: reproducible CPU-safe project.
2. US1: demonstrable ADR generation MVP.
3. US2: trustworthy missing-context behavior.
4. US3: RAG reuse and blinded strategy comparison.
5. US4: reproducible benchmark evidence before tuning.
6. US5: governed dataset and QLoRA adapter.
7. Polish: recovery, measured report, and portfolio case study.

## Notes

- The task list authorizes implementation, tests, and local development only; it does not authorize
  deployment to the Proxmox/GitLab VM or any production host.
- Never use the workspace Docker daemon to infer or operate production state.
- Keep model weights, adapters, checkpoints, databases, private snapshots, and tokens outside Git.
- A negative fine-tuning result is a valid project result and MUST NOT be hidden or reclassified.

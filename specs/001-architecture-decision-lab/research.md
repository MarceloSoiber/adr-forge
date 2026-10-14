# Research: Architecture Decision Lab

## Decision 1 — Modular monolith with two delivery adapters

**Decision**: Keep all domain and application behavior in one Python package. Expose it through a
FastAPI HTTP adapter and a Typer CLI; build the React client as a separate static asset toolchain.

**Rationale**: The MVP has one user and one GPU. Shared use cases prevent API/CLI rule drift while
module boundaries isolate volatile model, retrieval, persistence, and evaluation concerns.

**Alternatives considered**:

- Microservices: rejected because there is no independent scale, deployment, ownership, or
  availability requirement.
- Notebook-only lab: rejected because it does not provide a demonstrable product or stable
  contracts, though notebooks may remain disposable exploration tools.
- Next.js full-stack application: rejected because Python must own the ML runtime and domain rules;
  a second server runtime would duplicate orchestration.

## Decision 2 — Qwen3-4B-Instruct-2507 as the first controlled model

**Decision**: Pin the official `Qwen/Qwen3-4B-Instruct-2507` Safetensors revision for training and
in-process inference. Allow a GGUF build of the same model through LM Studio only as an optional
external-inference baseline.

**Rationale**: The 4B instruct model fits the staged learning objective, supports multilingual
instruction following, has an Apache 2.0 license, and is materially more feasible than a 20B model
on 12 GB VRAM. Using the same base identity across baseline and tuned strategies reduces
confounding variables.

**Alternatives considered**:

- Qwen3-VL-4B: rejected because visual inputs are outside MVP and the visual tower adds cost.
- Qwen3 thinking variant: deferred because hidden/extended reasoning complicates structured output
  and cost comparisons.
- GPT-OSS-20B: retained for normal Knowledge Hub use, but rejected for concurrent ADR Forge use;
  the current LM Studio process already occupies most available VRAM.
- Qwen3-8B: deferred until the complete 4B pipeline meets quality gates and measured VRAM allows it.

## Decision 3 — Canonical QLoRA learning stack

**Decision**: Use PyTorch, Transformers, Datasets, TRL `SFTTrainer`, PEFT LoRA, bitsandbytes 4-bit
quantization, and Accelerate. Train only assistant completion tokens with versioned configuration.

**Rationale**: The canonical ecosystem exposes the mechanics the project is intended to teach,
supports reproducible configuration, and keeps adapters interoperable.

**Alternatives considered**:

- Full-parameter tuning: rejected by VRAM, storage, and iteration-time constraints.
- Unsloth-first: deferred; it may become an optimization experiment after a canonical baseline is
  correct and measured.
- Remote managed fine-tuning: rejected for MVP because local learning and data control are goals.

## Decision 4 — SQLite metadata plus content-addressed filesystem artifacts

**Decision**: Use SQLite in WAL mode with SQLAlchemy and Alembic for metadata. Store large artifacts
under `var/artifacts` by validated content hash and record their identity, size, type, and lineage in
SQLite. Version small public data and manifests in Git.

**Rationale**: One user and one writer do not justify PostgreSQL for ADR Forge. Content-addressed
artifacts provide traceability without putting model files into the database or Git.

**Alternatives considered**:

- PostgreSQL: deferred until concurrent writers or a shared deployment exist.
- MLflow as the system of record: deferred because it adds a second metadata model and service
  before the experiment domain stabilizes; export integration remains possible.
- DVC: deferred until dataset or artifact sharing exceeds practical Git and manifest workflows.

## Decision 5 — Reuse Knowledge Hub retrieval through REST

**Decision**: Implement a `RetrievalProvider` port with a Knowledge Hub REST adapter calling
`POST /api/v1/knowledge/search`. Do not call the Knowledge Hub answer endpoint. Preserve an offline
snapshot provider for tests and reproducible benchmarks.

**Rationale**: Knowledge Hub already implements hybrid vector/text search, provenance, filters,
pgvector persistence, and local embeddings. REST is a smaller application-to-application contract
than MCP for this fixed operation. ADR Forge must own prompting and generation to compare
strategies fairly.

**Alternatives considered**:

- Rebuild a local vector index: rejected as duplication.
- Use MCP as the primary runtime contract: deferred for an agent integration demonstration; it
  adds protocol surface without improving fixed search calls.
- Call Knowledge Hub RAG answer: rejected because its generator and prompt would confound ADR Forge
  strategy comparisons.

## Decision 6 — Freeze retrieval before comparative generation

**Decision**: Retrieve once per experiment input, store the exact chunk text plus source identity,
location, ranks, scores, embedding identity, query, filters, hashes, and retrieval time, then provide
the identical snapshot to every RAG-enabled comparable strategy.

**Rationale**: Re-querying can change results after reindexing, content edits, or embedding changes.
Frozen context makes differences attributable to the generation strategy.

**Alternatives considered**:

- Live retrieval per strategy: rejected as experimentally unfair.
- Store only source IDs: rejected because mutable sources would prevent exact reproduction.

## Decision 7 — One in-process inference executor; CLI-only training

**Decision**: The API schedules inference through one executor guarded by an exclusive GPU lease.
It emits server-sent progress and supports cooperative cancellation. Training and full benchmark
runs execute through CLI foreground processes after resource preflight.

**Rationale**: This provides responsive local UX without Redis or a worker service. Keeping
training out of HTTP avoids pretending an in-process background task is durable.

**Alternatives considered**:

- Synchronous HTTP inference: rejected because local generation can exceed 90 seconds.
- Celery/Redis: deferred until the UI launches training or concurrent jobs are needed.
- Separate model server: deferred until multiple clients or throughput justify it.

## Decision 8 — Layered evaluation with human judgment as authority

**Decision**: Reuse one deterministic evaluation engine from application code, CLI, benchmarks,
and Pytest. Add blind human rubric evaluation as the authority for nuanced architectural quality.
Permit LLM-as-judge only as labeled exploratory evidence.

**Rationale**: Structure and invariant checks are objective; recommendation quality is not. Blind
review reduces identity and ordering bias without pretending a judge model is ground truth.

**Alternatives considered**:

- Exact text snapshots: rejected because valid generations vary in wording.
- LLM-as-judge only: rejected because of bias, self-preference, and reproducibility concerns.
- Human review only: rejected because it is slow and cannot replace deterministic regression gates.

## Decision 9 — Localhost security boundary

**Decision**: Bind to loopback without authentication in MVP. Store the Knowledge Hub bearer token
and optional Hugging Face token in environment variables. Treat retrieved text as untrusted data,
pin model revisions, use safe tensor formats, and default `trust_remote_code` to false.

**Rationale**: Authentication would add little value for a loopback-only single-user lab, but its
absence is unsafe once exposed. Explicit trust boundaries address the actual model, retrieval,
dataset, and artifact risks.

**Alternatives considered**:

- Token authentication now: deferred until LAN or VM access is planned.
- Bind to the LAN for convenience: rejected until TLS and authentication exist.

## Decision 10 — Native GPU development and CPU-safe automation

**Decision**: Run API, CLI, training, and inference natively through `uv` on the workstation. Use
Docker for reproducible CPU builds and smoke tests. GitHub Actions and the future GitLab VM run
fakes, snapshots, and CPU-safe checks only.

**Rationale**: Native CUDA access minimizes driver/container friction during learning. Default CI
must remain fast and available without specialized hardware.

**Alternatives considered**:

- GPU containers from day one: deferred until cross-machine training reproduction is required.
- GPU runner in CI: rejected because of cost and lack of a confirmed runner.

## Resolved Technical Unknowns

- Long inference is acceptable when progress and cancellation are visible.
- Artifact budget is 50 GB with warning at 40 GB.
- The live product is Portuguese-first; code and contracts use English.
- GPT-OSS is not part of ADR Forge generation and must be unloaded before Qwen GPU work.
- The Proxmox GitLab VM is a later CPU-only test target until its capacity is verified.
- No unresolved `NEEDS CLARIFICATION` items remain for implementation planning.

## Phase 2 Foundation Refinements

### Decision 11 — Inject resource and reference queries through shared ports

**Decision**: Define disk-capacity and artifact-reference query ports beside the existing repository
and transaction ports. The system module implements host probes; the artifact module consumes the
ports without importing host-infrastructure code.

**Rationale**: Artifact quota and safe deletion need information owned outside the artifact store.
Explicit ports preserve module boundaries and make CPU-only fixtures deterministic.

**Alternatives considered**:

- Read disk state directly inside the artifact service: rejected because it couples policy to the
  host and makes race and threshold tests harder.
- Discover artifact references by inspecting future tables: rejected because it is fragile and
  cannot guarantee deletion safety.

### Decision 12 — Register artifact ownership and reconcile conservatively

**Decision**: Add an `ArtifactReference` registry maintained in the owner's unit of work. Startup
reconciliation removes stale temporary files but only reports missing referenced files and
unregistered finalized objects.

**Rationale**: Later capabilities need a stable way to protect artifacts before all owner tables
exist. Conservative reconciliation avoids turning crash recovery into an implicit destructive
cleanup operation.

**Alternatives considered**:

- Generic owner IDs stored only in artifact metadata: rejected because multiple owners and safe
  removal are not enforceable.
- Delete every unregistered file at startup: rejected because a crash between atomic move and
  metadata commit could destroy recoverable work.

### Decision 13 — Use an operating-system file lock for the GPU lease

**Decision**: Use a non-blocking local file lock with diagnostic ownership metadata. Kernel lock
ownership, rather than PID-only checks, provides cross-process exclusion and crash release.

**Rationale**: API, benchmark, and training processes must coordinate without a broker. An OS lock
fits the single-host boundary and is testable with local subprocesses on CPU-only CI.

**Alternatives considered**:

- In-process semaphore: rejected because separate CLI and API processes could both enter GPU work.
- PID file alone: rejected because stale files and PID reuse do not provide reliable ownership.

### Decision 14 — Keep readiness local and capability-aware

**Decision**: Readiness requires valid configuration, migrated SQLite, and safe writable artifact
storage. GPU, model, and Knowledge Hub state are capability findings; `doctor` reports them with
documented exit semantics, but their absence does not make the base API unready.

**Rationale**: The local application must remain usable for CPU-only and non-RAG paths while still
giving actionable diagnostics for unavailable optional capabilities.

**Alternatives considered**:

- Require every integration for readiness: rejected because optional service or GPU downtime would
  disable unrelated local features.
- Always return ready after process startup: rejected because an invalid database or unwritable
  artifact root blocks every meaningful workflow.

## Phase 3 MVP Refinements

### Decision 15 — Ship a minimal strategy registry with the first vertical slice

**Decision**: Phase 3 owns a small in-memory registry containing a deterministic fake strategy and
one versioned Qwen baseline strategy. It exposes `GET /strategies` for the web picker. The baseline
strategy owns prompt construction and structured-output instructions; the model runtime only owns
generation. Phase 5 extends this registry with prompted, RAG, and fine-tuned availability rules.

**Rationale**: The Phase 3 web flow and API contract already require strategy discovery, while a
runtime adapter alone is not an executable analysis strategy. Keeping configuration in memory
avoids a strategy table before mutable strategy administration is required.

**Alternatives considered**:

- Hard-code the baseline in the browser: rejected because it duplicates server configuration and
  cannot report an unavailable model or fake-only test environment.
- Defer `GET /strategies` until Phase 5: rejected because the Phase 3 vertical slice and strategy
  picker would be incomplete.
- Persist strategy configuration in SQLite now: rejected because Phase 3 has no authoring or
  mutation workflow for strategies.

### Decision 16 — Serialize all inference, but lease the GPU only for GPU-backed runtimes

**Decision**: A single in-process queue serializes fake and real analysis jobs. GPU-backed jobs also
perform preflight and acquire the cross-process OS lease; the fake runtime remains CPU-only and
does neither. Blocking generation runs in a worker thread and returns a typed result containing
text and optional telemetry. On startup, every persisted non-terminal run becomes `interrupted`
because the in-memory queue cannot be recovered safely.

**Rationale**: The fake vertical slice must run in CPU-only CI, while real inference must remain
exclusive across API and CLI processes. Marking all orphaned non-terminal work as interrupted is
honest and avoids silently losing queued jobs after a restart.

**Alternatives considered**:

- Acquire the GPU lease for the fake runtime: rejected because it makes the default tests depend
  on local GPU configuration.
- Re-enqueue pending records automatically: rejected because process state, cancellation intent,
  and exact runtime availability are not durable enough for safe implicit replay.
- Add a durable broker: rejected by the single-user local boundary and constitution.

### Decision 17 — Preserve both generation attempts and their validation evidence

**Decision**: Persist the original model output before parsing. If JSON or ADR validation fails,
allow exactly one model-assisted repair using the original output, schema version, and
machine-readable findings. Persist the repair output separately and record immutable validation
attempt summaries for `original` and `repaired`. Never fill or rewrite missing ADR content in
application code. A second failure terminates the run as `invalid_output` without an ADR.

**Rationale**: Separate artifacts and findings make repair observable and reproducible while
honoring the requirement to retain raw output before normalization. A one-attempt limit bounds
latency and prevents hidden iterative prompt tuning.

**Alternatives considered**:

- Overwrite the original output: rejected because it destroys evidence.
- Repair JSON locally by inventing defaults: rejected because it can silently manufacture facts or
  architectural content.
- Retry until valid: rejected because it is unbounded and obscures the actual model failure rate.

### Decision 18 — Treat persisted run state as truth and SSE as a disposable projection

**Decision**: Every material stage update is persisted before it is published. The SSE adapter
subscribes first, then reads and emits the current persisted snapshot and discards queued events
whose sequence is not newer; this closes the snapshot/subscription race. It then forwards
best-effort events with a monotonic `progress_sequence` and closes after a terminal event. The
browser reads `GET /analysis-runs/{id}` before every initial connection or reconnect and owns
bounded reconnection; it does not rely on event replay.

**Rationale**: The existing progress publisher is process-local and callback-based. Persist-first
ordering makes refresh and reconnection correct without introducing a durable message broker.

**Alternatives considered**:

- Make the in-memory publisher the source of truth: rejected because events disappear on refresh
  or process restart.
- Add durable SSE replay now: rejected because polling the persisted snapshot closes the MVP
  recovery requirement with much less infrastructure.

### Decision 19 — Classify scenarios deterministically before hashing the revision

**Decision**: Scenario creation uses an injected classifier contract. Phase 3 supplies a
deterministic Portuguese-first classifier for the four supported categories plus `unsupported`;
tests may inject fixed classifications. Multiple matches are the deterministic ordered list of
specific categories, while no match is exactly `[unsupported]`. Classification is completed before
the immutable revision hash is calculated. The hash covers normalized revision content and
categories, excludes database identity and timestamps, preserves list order, and is unique per
scenario.

**Rationale**: Classification is part of the revision returned by `POST /scenarios` and therefore
cannot depend on a later analysis run. Injection keeps the policy testable and replaceable without
changing persistence or API contracts.

**Alternatives considered**:

- Ask the browser to choose the category: rejected because FR-003 requires the system to identify
  one, several, or no supported categories.
- Run a second LLM request during scenario creation: rejected because scenario persistence must
  work without GPU and the classification result must be deterministic in default tests.

### Decision 20 — Generated ADRs are proposed or provisional only

**Decision**: Model-generated Phase 3 outputs may use only `proposed` or `provisional`. Statuses
`accepted`, `rejected`, and `superseded` are reserved for a future explicit human workflow. All
nested ADR values use closed, versioned schemas, and deterministic validation returns stable
finding codes and paths shared by the API, CLI, benchmarks, and tests.

**Rationale**: A generated draft cannot claim an organizational decision state. Closed nested
schemas make the typed browser client and contract tests meaningful instead of accepting arbitrary
objects.

**Alternatives considered**:

- Accept every lifecycle status from the model: rejected because it would imply authority the
  product explicitly does not have.
- Leave nested values as arbitrary JSON objects: rejected because cross-field invariants and
  compatibility could not be verified.

### Decision 21 — Mount one versioned API and normalize every validation failure

**Decision**: Mount system and feature routers under `/api/v1`, matching the OpenAPI server URL.
Convert FastAPI request validation errors and domain errors to the same RFC 9457-style problem
shape with a stable code and request ID. Markdown exports include an attachment filename derived
from safe local identifiers.

**Rationale**: A single prefix prevents the generated client and running app from drifting. One
error envelope lets the browser handle input, domain, and state-transition failures consistently.

**Alternatives considered**:

- Remove `/api/v1` from the contract: rejected because versioning is already public and additional
  feature routes are about to land.
- Let framework-native 422 responses pass through: rejected because they violate the published
  problem-details contract.

## Phase 4 Clarification Refinements

### Decision 22 — Treat stored run questions as authoritative evidence

**Decision**: A clarification answer references an unresolved-question ID and source run. The
server loads the stored provisional ADR, verifies that the run belongs to the requested base
revision and ended in `needs_clarification`, and snapshots the authoritative question text and
impact beside the answer in the new revision. Requests do not submit authoritative question prose.

**Rationale**: Question provenance must survive prompt changes and UI retries. Resolving it from
immutable run evidence prevents a client from rewriting the question, answering a question from a
different scenario, or creating unsupported context.

**Alternatives considered**:

- Trust question text echoed by the browser: rejected because mutable client text is not reliable
  evidence.
- Store only the answer string: rejected because reviewers could not determine what was answered
  or which model run requested it.
- Create a mutable question table: rejected because questions already belong to an immutable ADR
  and Phase 4 does not need an independently editable lifecycle.

### Decision 23 — Append revisions with compare-and-swap on the scenario head

**Decision**: `POST /scenarios/{scenarioId}/revisions` supplies `base_revision_number`. The service
validates outside the write transaction, then conditionally advances the scenario head and inserts
revision `base + 1` in one SQLite transaction. If the current head differs, the request returns
`409` with stable code `stale_revision`; there is no automatic merge or rebase.

**Rationale**: Scenario revisions are immutable, but two browser tabs can still race to append the
next revision. A conditional head update gives exactly one winner without locks held during model
or validation work and makes the conflict visible to the architect.

**Alternatives considered**:

- Last write wins: rejected because it silently discards clarification evidence.
- Pessimistic locking across the request: rejected because SQLite offers no useful row-level lock
  and the critical section can remain a short atomic transaction.
- Automatically merge answer sets: rejected because duplicated or contradictory answers require a
  human rebase decision.

### Decision 24 — Keep answers as answers and preserve the prior snapshot

**Decision**: A clarification revision inherits the base problem, facts, constraints, desired
qualities, candidate alternatives, and ordered categories, then appends normalized clarification
answer snapshots. It does not rewrite the base revision or infer that free-text answers are facts
or constraints. Starting a new analysis run is a separate existing operation after the revision
commits.

**Rationale**: User answers are relevant evidence, but their semantic role may require judgment.
Keeping the original fields unchanged preserves auditability, makes canonical hashing
deterministic, and prevents an analysis enqueue failure from losing submitted answers.

**Alternatives considered**:

- Parse every answer into facts or constraints: rejected because deterministic text heuristics
  would invent semantics.
- Mutate the current revision in place: rejected because previous experiment inputs would no
  longer be reproducible.
- Create the revision and run in one transaction: rejected because queueing occurs after commit and
  a run failure must not erase accepted user evidence.

### Decision 25 — Bound provisional confidence and make continuation non-mutating

**Decision**: A valid provisional ADR contains one to three unique impact-aware questions, at
least one explicit assumption, and confidence no greater than `0.60`. Missing critical context and
contradictory constraints receive stable validation findings. If the architect declines to answer,
the browser continues to display and export the existing provisional ADR; no extra revision or run
is created.

**Rationale**: A numeric ceiling makes “reduced confidence” deterministic and testable while the
provisional status, assumptions, and questions communicate why the result is uncertain. Reusing
the stored ADR avoids producing a second output from identical evidence.

**Alternatives considered**:

- Compare confidence with a hypothetical complete run: rejected because no comparable run may
  exist and model scores are not calibrated across executions.
- Use only a visual warning: rejected because API, benchmarks, and exports also need the invariant.
- Rerun when the user declines questions: rejected because it adds cost without adding evidence.

## Phase 5 Strategy Comparison Refinements

### Decision 26 — Hash the complete versioned retrieval envelope and reuse by content

**Decision**: Model retrieval filters, locations, and chunks as frozen closed value objects and
serialize a versioned canonical snapshot with the existing shared canonical JSON implementation.
The content hash covers provider and embedding identity, normalized query and filters, and every
exact chunk field in provider rank order. Database IDs, artifact paths, and creation timestamps are
excluded. Publish the canonical JSON artifact first, then commit its artifact metadata, snapshot,
and owner reference in one database transaction. Reuse an existing row by unique content hash.

**Rationale**: Experimental equivalence requires the query, provider configuration, and exact
ordered evidence—not only source IDs—to be reproducible. Excluding storage identity and time makes
identical evidence deduplicable while retaining all variables that could affect generation.

**Alternatives considered**:

- Hash only chunk text or IDs: rejected because request, provider, embedding, ordering, scores, and
  provenance could change without changing identity.
- Include creation time in the content hash: rejected because identical evidence could never be
  reused.
- Re-query for each strategy: rejected because mutable retrieval would confound the comparison.

### Decision 27 — Enforce one wall-clock retrieval deadline around both attempts

**Decision**: Implement the Knowledge Hub adapter with an injected `httpx.AsyncClient`, monotonic
deadline, sleeper, and jitter source. A single 15-second wall-clock budget includes at most two
attempts and their backoff; each connection attempt has a 2-second connect timeout. Retry only
connection failures, 408, 429, and 5xx. Validate the complete response projection, provider
version, and embedding identity before producing a snapshot. Authentication, other 4xx, malformed
responses, and missing required fields fail immediately with sanitized stable reasons.

**Rationale**: An `httpx` timeout applied independently to each attempt can exceed the advertised
total. Injected time and backoff make exact retry behavior testable without sleeping, while strict
schema validation prevents partial or unauthenticated evidence from being mislabeled as RAG.

**Alternatives considered**:

- Add a general retry library: rejected because one bounded retry does not justify another
  dependency.
- Retry every failure or return empty context: rejected because both violate the retrieval
  contract and strategy identity.
- Trust provider or embedding identity from optional fields: rejected because live snapshots
  without pinned provenance are not reproducible.

### Decision 28 — Freeze one execution envelope before comparable strategy runs

**Decision**: Evolve strategy execution around an immutable input envelope containing scenario
revision identity/hash, optional retrieval snapshot identity/hash, and versioned generation
configuration/hash. Strategies compose prompts but never retrieve. RAG-capable runs in one cohort
must use the same snapshot and decoding configuration; a non-RAG strategy receives no snapshot.
Persist these identities on every run and fail before queueing when required dependencies are
missing. Fine-tuned definitions remain unavailable until a compatible adapter artifact exists.

**Rationale**: The experiment must vary declared strategy/model/prompt inputs without accidentally
varying scenario, retrieved evidence, or decoding configuration. Persisted identities remain true
even if the in-memory registry later changes.

**Alternatives considered**:

- Compare only by scenario ID: rejected because retrieval and decoding remain hidden variables.
- Let each strategy retrieve or choose decoding parameters: rejected because it prevents causal
  attribution.
- Pass a snapshot to the baseline: rejected because that changes a non-RAG treatment into RAG.

### Decision 29 — Persist the secret mapping and append-only evaluation chain

**Decision**: A blind comparison stores randomized opaque labels in child rows with unique
comparison/label and comparison/run constraints. Pre-submission DTOs contain a dedicated blinded
ADR projection and public rubric definition, never the normal ADR/run DTO. The first complete
evaluation atomically becomes the comparison head and unlocks reveal. A correction supplies the
current result ID, creates a new immutable result with `supersedes_evaluation_id`, and atomically
advances the head; stale or duplicate submissions conflict.

**Rationale**: Separate public projection prevents accidental identity leakage. Append-only
supersession preserves the original human judgment and provides deterministic concurrency
behavior while allowing an explicit correction workflow.

**Alternatives considered**:

- Derive labels from run IDs or insertion order: rejected because identities become guessable.
- Reuse the full ADR response before submission: rejected because it includes run provenance.
- Update an evaluation in place: rejected because it destroys audit history.

### Decision 30 — Pull the minimum immutable rubric into Phase 5 and advance migration IDs

**Decision**: Phase 5 introduces the minimal published `RubricVersion` required to render and
validate blind evaluation, seeded from a versioned tracked definition. Scores use each dimension's
declared bounds rather than browser constants. Because `0005_run_events.py` and
`0006_run_telemetry.py` already exist, retrieval and blind-evaluation schema changes use
`0007_retrieval_snapshots.py` and `0008_blind_evaluation.py`; later migration numbers advance.

**Rationale**: A rubric identifier without a resolvable immutable definition cannot drive complete
server validation or accessible UI controls. Reusing occupied Alembic revisions would create a
broken history.

**Alternatives considered**:

- Wait for the Phase 6 experiment task to create rubrics: rejected because Phase 5 cannot submit a
  valid rubric evaluation without it.
- Hard-code score bounds only in React/OpenAPI: rejected because multiple implementations could
  drift and the recorded rubric would not be reproducible.
- Rename existing migrations: rejected because merged migration history is immutable.

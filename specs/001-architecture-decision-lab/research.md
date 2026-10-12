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

<!--
Sync Impact Report
- Version change: template -> 1.0.0
- Modified principles: placeholder principles -> six ADR Forge governance principles
- Added sections: Technical and Data Constraints; Delivery Workflow and Quality Gates
- Removed sections: none
- Follow-up TODOs: none
-->
# ADR Forge Constitution

## Core Principles

### I. Evidence Before Claims

Every architectural recommendation MUST distinguish facts, assumptions, unresolved questions,
and accepted decisions. A conclusive ADR MUST compare at least two viable alternatives, connect
its rationale to scenario evidence or identified references, disclose negative consequences, and
define measurable review triggers. When material context is missing, the system MUST ask focused
questions or label the result provisional; it MUST NOT silently invent requirements. Generated
ADRs are reviewable drafts, and final accountability remains with a human architect.

### II. Reproducible and Honest Experiments

Every experiment MUST be traceable to immutable versions of its scenario, retrieval snapshot,
dataset, rubric, model, adapter, generation settings, and code revision. Raw model output MUST be
preserved before repair or normalization. Failed, partial, invalid, cancelled, and excluded runs
MUST remain visible in reports. A benchmark MUST NOT present partial data as complete, and a
fine-tuning claim MUST be compared against the strongest relevant non-fine-tuned baseline under
equivalent inputs.

### III. Dataset Integrity and Human Review

Training, validation, and fixed evaluation partitions MUST be explicit and protected against
exact duplicates and known derived variants crossing boundaries. Every example MUST record
source, authorization or license, language, category, creation method, lineage, and review state.
Synthetic examples MUST receive human approval before inclusion in a publishable dataset.
Proprietary course material, employer-confidential content, personal data, payment data, and
production data MUST NOT enter public datasets or test fixtures.

### IV. Contracts and Tests Are Executable Specifications

Schemas, state transitions, invariants, and external contracts MUST be machine-verifiable.
Deterministic validation MUST be implemented once and reused by the application, CLI, benchmarks,
and Pytest suite. Tests MUST cover domain rules without requiring a live language model, while
contract and snapshot tests MUST cover model and Knowledge Hub boundaries. GPU-dependent tests
MUST be explicitly marked and MUST NOT be required for the default CI pipeline.

### V. Local-First Security and Resource Safety

The MVP MUST bind only to localhost and MUST NOT imply network-safe operation without adding
authentication and TLS. Secrets MUST remain outside source control, logs, datasets, and experiment
artifacts. Retrieved content MUST be treated as untrusted data and never as executable
instructions. GPU workloads MUST acquire an exclusive resource lease, perform a capacity
preflight, expose progress and cancellation, and MUST NOT terminate external processes
automatically. Model artifacts MUST be pinned by identity and revision and excluded from Git.

### VI. Simplicity With Measured Evolution

The system MUST begin as a modular monolith with one application codebase, SQLite metadata,
filesystem artifacts, native local model execution, and the existing Knowledge Hub behind an
adapter. Redis, external queues, PostgreSQL for ADR Forge, distributed services, GPU containers,
and external observability MUST NOT be introduced without a documented requirement and measurable
trigger. Module boundaries MUST protect real volatility—model runtime, retrieval, persistence, and
evaluation—rather than create ceremonial layers.

## Technical and Data Constraints

- The supported MVP runtime is a single local user on an NVIDIA RTX 3060 with 12 GB VRAM.
- Qwen3-4B-Instruct-2507 is the initial training and inference baseline; model replacement MUST
  occur through the strategy and runtime ports rather than domain changes.
- Fine-tuning uses supervised QLoRA through the canonical Transformers, TRL, PEFT, and
  bitsandbytes ecosystem before optional accelerator-specific alternatives are evaluated.
- The Knowledge Hub search API is the authoritative live retrieval provider. Benchmarks MUST use
  frozen retrieval snapshots so all comparable strategies receive identical context.
- Only one GPU workload may run at a time. Training requires exclusive GPU use and MUST fail its
  preflight with actionable diagnostics when insufficient VRAM is available.
- Public datasets and manifests are versioned in Git. SQLite databases, model weights, adapters,
  checkpoints, private snapshots, caches, and extensive run artifacts remain outside Git.
- The initial artifact budget is 50 GB, with a warning at 80 percent and explicit cleanup.
- The UI and curated dataset MUST support Brazilian Portuguese; source code identifiers and
  technical contracts use English for interoperability.
- The future GitLab test environment is CPU-safe by default and uses fakes or snapshots until GPU
  capacity is explicitly confirmed.

## Delivery Workflow and Quality Gates

1. Every change starts from a specification or task linked to a user story, requirement, risk, or
   accepted ADR.
2. Domain and contract tests are written with or before implementation for affected invariants.
3. The default CI gate runs formatting, linting, type checking, unit tests, contract tests,
   dataset validation, frontend build, secret scanning, and dependency checks without a GPU.
4. Model-dependent validation runs locally under an explicit marker and records model revision,
   hardware, configuration, duration, and artifacts.
5. Dataset publication requires provenance validation, human review, license compatibility, and a
   clean contamination check.
6. Benchmark publication requires complete run accounting, reproducible configuration, baseline
   comparison, and disclosure of limitations and unfavorable results.
7. New infrastructure or architectural complexity requires an ADR with alternatives,
   consequences, operational cost, and a measurable adoption trigger.
8. Changes to public schemas, dataset formats, or API contracts require compatibility assessment,
   migration notes, and contract tests.

## Governance

This constitution governs all specifications, plans, tasks, reviews, and implementation work in
ADR Forge. When another project document conflicts with it, this constitution takes precedence.

Amendments require a documented proposal, rationale, impact analysis, and explicit approval by the
project owner. Governance versions follow semantic versioning: MAJOR for incompatible principle or
governance changes, MINOR for new principles or material expansions, and PATCH for clarifications
that do not change obligations. Every plan and pull request MUST include a constitution compliance
check. Exceptions MUST be time-bounded, documented with owner and review date, and MUST NOT weaken
dataset provenance, experiment honesty, secret handling, or human accountability.

**Version**: 1.0.0 | **Ratified**: 2026-10-10 | **Last Amended**: 2026-10-10

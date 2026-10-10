# Architecture Quality Gates

- **Review date**: 2026-10-10
- **Scope**: Localhost-only, single-user ADR Forge MVP
- **Decision**: Approved to begin implementation
- **Blocking items**: None

Statuses follow the architecture review rubric: `Met`, `Not applicable`, `Non-blocking pending`, or
`Blocking`. A `Not applicable` item includes the condition that would make it applicable.

## Definition Gate

| Area | Status | Evidence or rationale |
| --- | --- | --- |
| Problem, users, outcome, MVP, exclusions, and critical flows | Met | `spec.md`, blueprint sections 1–3 and the critical-flow sequence |
| Success criteria and measurable quality targets | Met | `spec.md` success criteria and blueprint section 4 |
| Team, schedule, and budget constraints | Non-blocking pending | One owner and local-first cost model are known; delivery dates and a monetary ceiling have not been committed and do not alter the MVP design |
| Current scale, peak, and growth horizon | Met | One user, one GPU job, 100 initial examples, up to 5,000 examples and 100 benchmark scenarios |
| Latency, availability, RPO, RTO, retention, and residence | Met | Acknowledgement and retrieval targets, local availability boundary, RPO 24 h, RTO 4 h, artifact quota, local storage |
| Domain entities, invariants, lifecycle, and transaction boundaries | Met | `data-model.md` and plan transaction boundaries |
| Sensitive data classification, access, and minimization | Met | Public-data governance, local private artifacts, no employer/payment/production data |
| Backup, restore, deletion, and integrity verification | Met | Daily SQLite backup, restore drill, immutable references, hash verification, safe prune tasks |
| Architecture recommendation and plausible alternatives | Met | Modular monolith compared with notebook-only and distributed services |
| Component responsibilities, boundaries, contracts, and evolution triggers | Met | Blueprint sections 6–10, plan module table, OpenAPI/CLI/Knowledge Hub contracts, ADRs |
| Authentication and tenant isolation | Not applicable | The accepted boundary is one local user on loopback; authentication becomes blocking before LAN, VM, multi-user, or public exposure |
| Trust boundaries, secrets, untrusted input, uploads, and dependency integrity | Met | Blueprint security review and CI/security tasks |
| Audit trail and privacy controls | Met | Immutable run/evaluation metadata, correlation IDs, redacted logs, provenance and review gates |
| External timeouts, bounded retry, degradation, and reconciliation | Met | Knowledge Hub contract and startup reconciliation; non-RAG paths remain available |
| Broker, DLQ, ordering, and poison-message policy | Not applicable | There is no queue or broker; reconsider only if work moves to durable asynchronous workers |
| Logs, metrics, traces, health, readiness, and correlation | Met | Structured logs, persisted run telemetry, diagnostics endpoints, correlation fields; distributed tracing is unnecessary for the local monolith |
| Actionable SLO alerts and live on-call ownership | Not applicable | No production service or on-call operation exists; required before production exposure |
| Deploy, rollback, and zero-downtime operation | Not applicable | Current scope is local development and CPU-safe builds, not deployment; a deployment ADR is required before VM use |
| Migrations, capacity, cost, runbooks, and recovery | Met | Alembic plan, GPU/disk limits, cost drivers, quickstart, recovery and backup tasks |
| Test strategy and CI quality/security gates | Met | Plan testing strategy and tasks T006–T009, T119–T121 |
| Environment, configuration, and secret separation | Met | Environment contract, ignored local artifacts, CPU CI, native GPU execution |
| Dependency-aware roadmap and reversible increments | Met | Blueprint roadmap and tasks phases/dependency graph |
| Difficult-to-reverse decisions captured as ADRs | Met | ADRs 0001–0010 |

## Professional Reviews

| Review | Status | Result |
| --- | --- | --- |
| Threat review | Met | Spoofing is limited by loopback scope; tampering, repudiation, disclosure, denial of service, and privilege risks map to hashes/immutability, audit metadata, redaction, quotas/lease, safe paths, and pinned model revisions. Residual risk: a compromised local account can access local data. |
| Privacy review | Met | Purpose and minimization are explicit; public examples require provenance, authorization, review, and contamination checks. Private artifacts stay outside Git and have bounded retention through the quota/prune workflow. |
| Reliability review | Met | Knowledge Hub, model runtime, SQLite, filesystem, and GPU failures have detection, containment, recovery, and verification behavior. Generated work is not silently retried. |
| Operability review | Met | Local start, diagnostics, progress, cancellation, backup/restore, interrupted-run reconciliation, and artifact inspection are planned. |
| Cost review | Met | Base infrastructure cost is near zero; dominant variable drivers are developer/reviewer time, GPU electricity/compute, and local disk, each measurable in run/artifact metadata. |
| Evolvability review | Met | Ports isolate model and retrieval volatility. Extraction is deferred until measured concurrency, independent deployment, or persistence needs justify it. |

## Overarchitecture Check

No unsupported microservices, queue, Redis, Kubernetes, CQRS, event sourcing, database-per-service,
or high-availability topology is present. The React application is a separate build artifact, not a
separate business backend. SQLite, filesystem artifacts, an in-process executor, and one external
retrieval adapter match the accepted scale.

## Acceptance Assessment

| Criterion | Status | Assessment |
| --- | --- | --- |
| Coherent | Met | Specification, diagrams, stack, contracts, ADRs, and task plan agree |
| Traceable | Met | Decisions map to requirements, risks, or accepted constraints |
| Executable | Met | 127 ordered tasks define an MVP vertical slice and later increments |
| Operable | Met | Failure, observation, cancellation, backup, and recovery paths are explicit |
| Secure | Met | Controls are proportional to local data and trust boundaries |
| Economic | Met | Complexity and infrastructure match a one-owner local lab |
| Evolvable | Met | Objective triggers govern authentication, deployment, extraction, and scaling |
| Honest | Met | GPU capacity and fine-tuning benefit remain hypotheses until measured |

## Exit Conditions for Pending Items

1. Record an indicative schedule and monetary ceiling before treating the roadmap as a delivery
   commitment rather than a learning plan.
2. Resolve QLoRA batch size, rank, context length, duration, and peak VRAM through the smoke run in
   T125; update the relevant ADR if the architecture must change.
3. Run a new architecture and security gate before binding beyond `127.0.0.1`, using the GitLab VM,
   or performing any deployment.

# Quickstart Validation Guide

This guide describes the expected end-to-end validation flow after implementation. It is not an
installation guarantee for the current documentation-only repository.

## Prerequisites

- `uv`, Python 3.12, Node.js, npm, and Git.
- A local writable directory for temporary SQLite metadata and artifacts.

The Phase 3 fake-runtime and Phase 5 fixture-comparison flows are CPU-safe and require neither a
GPU, model download, nor Knowledge Hub. Live Qwen validation additionally requires an NVIDIA
driver, an RTX 3060-class GPU
with 12 GB VRAM, access to the pinned `Qwen/Qwen3-4B-Instruct-2507` revision, sufficient local
disk, and any conflicting LM Studio model unloaded.

## Configure

```bash
test -f .env || cp .env.example .env
uv sync --all-extras
npm --prefix apps/web ci
uv run alembic upgrade head
```

Required local values include artifact root, SQLite URL, Knowledge Hub URL, and bearer token. The
API and web client bind to loopback by default.

## Run CPU-safe quality gates

```bash
uv run ruff check .
uv run mypy src
uv run pytest -m "not gpu and not live_integration"
npm --prefix apps/web test
npm --prefix apps/web run build
```

Expected result: all deterministic, repository, contract, and frontend tests pass without loading a
language model or contacting Knowledge Hub.

## Validate the Phase 2 foundation

After T011–T027 are implemented, run the focused foundation gate with temporary storage and no GPU
or live integration:

```bash
uv run alembic upgrade head
uv run pytest \
  tests/unit/shared \
  tests/integration/persistence \
  tests/unit/artifacts \
  tests/unit/system \
  -m "not gpu and not live_integration"
uv run adr-forge doctor --json
```

Expected result: migrations reach head; shared, persistence, artifact, and resource tests pass; the
doctor command returns a sanitized JSON result without downloading a model or changing system
state. Optional integrations may be reported as unavailable through bounded probes. Use temporary
overrides for the SQLite URL and artifact root when running destructive artifact-prune fixtures.

## Validate resources and integrations

```bash
uv run adr-forge doctor
uv run adr-forge doctor --json
```

Expected result: the command reports disk budget, CUDA/VRAM, active GPU processes, model status,
SQLite status, and Knowledge Hub reachability without exposing its token.

## Start the local application

```bash
uv run uvicorn apps.api.main:app --host 127.0.0.1 --port 8000
npm --prefix apps/web run dev -- --host 127.0.0.1
```

Open the Vite loopback URL. Select the fake baseline and submit a complete Portuguese scenario
covering one of the four supported categories. Verify that progress changes from pending through
running to completed, every ADR section is visible, the human-accountability notice is present,
and the resulting ADR can be exported as Markdown.

## Validate the Phase 3 vertical slice

Run the focused CPU-safe suites with temporary database and artifact roots:

```bash
uv run alembic upgrade head
uv run pytest \
  tests/unit/scenarios \
  tests/unit/decisions \
  tests/contract/test_analysis_api.py \
  tests/integration/test_analysis_vertical_slice.py \
  -m "not gpu and not live_integration"
npm --prefix apps/web test -- AnalysisFlow
npm --prefix apps/web run build
```

Expected result: scenario classification and canonical hashes are deterministic; a fake analysis
persists state before publishing progress; reconnect reads the current state before reopening SSE;
the run reaches a valid terminal ADR or exposes stable validation findings; and Markdown rendering
does not add facts absent from the structured ADR. All tests run without CUDA, network access, or
model packages.

## Validate clarification behavior

Run the Phase 4 CPU-safe suites:

```bash
uv run pytest \
  tests/benchmark/test_clarification_cases.py \
  tests/contract/test_scenario_revisions_api.py

npm --prefix apps/web test -- ClarificationFlow.test.tsx
```

Then start the local application and submit one incomplete pt-BR case from
`datasets/fixtures/clarification.jsonl`. Verify both branches of the interaction:

1. Choose **Continuar como provisório** and confirm that no revision or run is created and the
   existing ADR remains visibly provisional and exportable.
2. Answer one or more displayed questions and submit. Confirm that revision `N + 1` is created,
   a new run starts from it, and the source revision/run/ADR can still be fetched unchanged.

Expected result:

- no more than three focused questions, each explaining why the answer matters;
- a provisional ADR with explicit assumptions and confidence at or below `0.60`;
- a new scenario revision after valid answers, with authoritative question and source-run linkage;
- the original run, ADR, output artifacts, validation findings, and revision remain unchanged;
- two submissions using the same base produce one `201` and one `409 stale_revision`;
- a complete Phase 3 fixture still completes without showing the clarification panel.

## Validate the Phase 5 strategy comparison

Run the focused CPU-safe suites against a fresh migrated temporary database and artifact root:

```bash
uv run alembic upgrade head
uv run pytest \
  tests/contract/test_knowledge_hub.py \
  tests/unit/retrieval/test_snapshot.py \
  tests/integration/test_strategy_equivalence.py \
  tests/unit/evaluation/test_blinding.py \
  -m "not gpu and not live_integration"
npm --prefix apps/web test -- BlindComparison.test.tsx
npm --prefix apps/web run build
```

Expected result: the mocked adapter obeys one 15-second total budget and exact retry policy; a
fixture produces byte-stable canonical snapshot content; fake RAG strategies observe the same
scenario, snapshot, evidence order, and generation configuration; and identity cannot be revealed
before a complete immutable evaluation is submitted.

With the local application running, perform the fixture vertical slice:

1. Create a snapshot through `POST /api/v1/retrieval-snapshots` using `provider=fixture` and a
   configured fixture ID. Repeat the request and confirm the canonical content hash and snapshot
   identity are reused.
2. Create two completed fake RAG runs for the same scenario revision and snapshot. Confirm their
   persisted snapshot ID and generation configuration hash are equal.
3. Create a comparison and fetch it before evaluation. Confirm the response and rendered DOM show
   only opaque labels, ADR review content, and rubric definitions—no run, strategy, model, snapshot,
   artifact, timing, or resource identity.
4. Call reveal before submission and confirm `409 evaluation_required`.
5. Score every label/dimension, choose one label or a tie, optionally add notes, and submit. Confirm
   the result is immutable and reveal now returns label-to-run/strategy provenance.
6. Submit again without a superseding result ID and confirm `409 evaluation_already_submitted`.
   Submit an explicit correction against the current result and confirm a new result becomes the
   head while the original remains unchanged.

The phase passes only if all of the above works without network, CUDA, model packages, or arbitrary
fixture filesystem paths.

## Validate live retrieval

```bash
curl --fail-with-body http://127.0.0.1:8000/api/v1/retrieval-snapshots \
  -H 'Content-Type: application/json' \
  --data '{"provider":"knowledge_hub","query":"restrições para processamento assíncrono","filters":{"limit":8}}'
```

Expected result: the artifact contains ordered Knowledge Hub chunks, exact content, source
locations, scores, provider and embedding identity, query and content hashes. The bearer token is
absent from the response and logs. Repeating an experiment uses this stored snapshot rather than
silently retrieving again. This check is opt-in and requires the loopback Knowledge Hub service.

## Validate a GPU baseline

Unload GPT-OSS and other large LM Studio models, then run:

```bash
uv run pytest -m gpu tests/integration/test_qwen_baseline.py
```

Expected result: Qwen loads after preflight, only one GPU lease exists, raw output is preserved,
structured validation runs, and peak VRAM is recorded. This test is opt-in and is not part of the
default Phase 3 completion gate.

## Validate dataset integrity

```bash
uv run adr-forge dataset validate \
  --manifest datasets/manifests/v0.1.0.json
```

Expected result: every included example is approved and licensed, hashes match, and no content or
lineage family crosses into fixed evaluation.

## Run the first QLoRA experiment

```bash
uv run adr-forge train sft --config configs/training/qwen3-4b-smoke.yaml
```

Expected result: insufficient VRAM fails before model allocation with actionable diagnostics;
otherwise the run records effective configuration, checkpoints, final adapter hash, duration, and
peak VRAM.

## Run and report a benchmark

```bash
uv run adr-forge benchmark run --config configs/evaluation/smoke.yaml
uv run adr-forge benchmark report --experiment EXPERIMENT_ID --output data/reports/smoke.md
```

Expected result: the report accounts for all expected runs, shows failures and exclusions, compares
the strongest non-tuned baseline with the tuned strategy, and includes exact reproduction inputs.

## Recovery checks

Run the Phase 8 CPU-only recovery and security evidence with temporary roots:

```bash
validation_root="$(mktemp -d)"
trap 'rm -rf "$validation_root"' EXIT
export ADR_FORGE_DATABASE_URL="sqlite+aiosqlite:///$validation_root/adr-forge.sqlite3"
export ADR_FORGE_ARTIFACT_ROOT="$validation_root/artifacts"
uv run alembic upgrade head
uv run pytest -q tests/security tests/integration/test_recovery.py tests/performance/test_local_benchmark.py
mkdir -p "$validation_root/backups"
uv run adr-forge database backup --output "$validation_root/backups/adr-forge.db"
uv run adr-forge artifacts list --json
```

The variables above keep deletion within disposable SQLite and artifact directories. Verify the dry
precondition and then confirm the explicit operation:

```bash
uv run adr-forge artifacts prune
uv run adr-forge artifacts prune --confirm --json
```

Expected result: security tests stay offline and redact sentinel secrets; the 100-scenario fake
benchmark accounts for every scenario; recovery tests restore the backup into an isolated
temporary path and verify its manifest/integrity/schema; the unconfirmed prune changes nothing;
the confirmed prune preserves referenced and retained artifacts and reports audit-backed reclaimed
bytes. Never restore over the configured live database during validation.

- Restarting the API converts abandoned `pending`, `waiting_resources`, and `running` records to
  `interrupted`.
- Reconnecting the browser reads current run state before subscribing to new SSE progress.
- `adr-forge database backup` creates a restorable SQLite backup with a verified manifest.
- `adr-forge artifacts prune` refuses to delete referenced or retained artifacts.

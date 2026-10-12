# Quickstart Validation Guide

This guide describes the expected end-to-end validation flow after implementation. It is not an
installation guarantee for the current documentation-only repository.

## Prerequisites

- Linux workstation with NVIDIA driver and RTX 3060 12 GB.
- `uv`, Python 3.12, Node.js, npm, and Git.
- Knowledge Hub running locally for live RAG scenarios.
- `Qwen/Qwen3-4B-Instruct-2507` access and sufficient local disk.
- GPT-OSS unloaded from LM Studio before Qwen inference or training.

## Configure

```bash
cp .env.example .env
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
  tests/contract/test_system_api.py \
  tests/contract/test_doctor_cli.py \
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

Open the Vite loopback URL. Submit a fixture-backed scenario and verify that progress changes from
pending through running to completed, then export the resulting ADR as Markdown.

## Validate clarification behavior

Submit the intentionally incomplete fixture from `datasets/fixtures`. Expected result:

- no more than three focused questions;
- no unsupported conclusive recommendation;
- a new scenario revision after answers;
- the original run and revision remain unchanged.

## Validate live retrieval

```bash
uv run adr-forge retrieval snapshot \
  --scenario SCENARIO_REVISION_ID \
  --output var/artifacts/retrieval/manual-snapshot.json
```

Expected result: the artifact contains ordered Knowledge Hub chunks, exact content, source
locations, scores, query and content hashes. Repeating an experiment uses this stored snapshot
rather than silently retrieving again.

## Validate a GPU baseline

Unload GPT-OSS and other large LM Studio models, then run:

```bash
uv run pytest -m gpu tests/integration/test_qwen_baseline.py
```

Expected result: Qwen loads after preflight, only one GPU lease exists, raw output is preserved,
structured validation runs, and peak VRAM is recorded.

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
uv run adr-forge benchmark report --experiment EXPERIMENT_ID --output var/reports/smoke.md
```

Expected result: the report accounts for all expected runs, shows failures and exclusions, compares
the strongest non-tuned baseline with the tuned strategy, and includes exact reproduction inputs.

## Recovery checks

- Restarting the API converts abandoned `running` records to `interrupted`.
- Reconnecting the browser reads current run state before subscribing to new SSE progress.
- `adr-forge database backup` creates a restorable SQLite backup with a verified manifest.
- `adr-forge artifacts prune` refuses to delete referenced or retained artifacts.

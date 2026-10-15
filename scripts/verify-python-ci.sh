#!/usr/bin/env bash
# Reproduce the Python quality job locally before sending changes to CI.
set -euo pipefail

uv run ruff format --check .
uv run ruff check .
uv run mypy src apps/api
CUDA_VISIBLE_DEVICES="" ADR_FORGE_HOST=127.0.0.1 \
  uv run pytest -m "not gpu and not live_integration"

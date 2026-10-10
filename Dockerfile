# syntax=docker/dockerfile:1.7

FROM python:3.12-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_PROGRESS=1

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.11.28 /uv /uvx /bin/
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY apps ./apps
COPY src ./src
COPY README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

FROM python:3.12-slim AS runtime

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ADR_FORGE_HOST=127.0.0.1 \
    ADR_FORGE_PORT=8000

WORKDIR /app

RUN groupadd --system adrforge \
    && useradd --system --gid adrforge --create-home adrforge

COPY --from=builder --chown=adrforge:adrforge /app/.venv /app/.venv
COPY --from=builder --chown=adrforge:adrforge /app/apps /app/apps
COPY --from=builder --chown=adrforge:adrforge /app/src /app/src

USER adrforge
EXPOSE 8000

CMD ["uvicorn", "apps.api.main:app", "--host", "127.0.0.1", "--port", "8000"]

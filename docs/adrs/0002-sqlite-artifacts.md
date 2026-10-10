# ADR-002 — Store metadata in SQLite and artifacts in the filesystem

- Status: accepted
- Date: 2026-10-10
- Decisors: Marcelo Soiber

## Context

The local single-user lab needs transactions and queries for metadata but stores multi-gigabyte
models, checkpoints, raw output, and reports.

## Decision

Use SQLite WAL through SQLAlchemy/Alembic for metadata, content-addressed files under `var` for
large/private artifacts, and Git for public datasets, schemas, configurations, and reports.

## Alternatives considered

- PostgreSQL: unnecessary operation for one writer.
- Database blobs: poor fit for large regenerable artifacts.
- MLflow or DVC as system of record: premature before domain contracts stabilize.

## Consequences

Backup and distribution are simple, but shared concurrent use is not supported. File and metadata
commit order must prevent dangling references.

## Review triggers

Move metadata to PostgreSQL when multiple users/writers, remote deployment, or measured lock
contention appears. Evaluate DVC/object storage when artifacts must be shared between machines.

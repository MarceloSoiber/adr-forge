# CLI Contract

## General Rules

- Executable name: `adr-forge`.
- Human-readable output is the default; `--json` returns one JSON value suitable for automation.
- Exit code `0` means success, `2` means invalid user input, `3` means failed precondition, `4`
  means integration unavailable, and `1` means an unexpected or execution failure.
- Secrets are never printed. Paths are project-relative where practical.
- Destructive prune operations require `--confirm`; no interactive confirmation is used in CI.

## Commands

### `adr-forge doctor`

Checks configuration, SQLite path, artifact budget, disk, CUDA, VRAM, active GPU processes,
Knowledge Hub reachability, model availability, and dataset schemas. This command does not download
models, unload processes, or mutate data.

### `adr-forge dataset validate --manifest PATH`

Validates schema, provenance, licenses, review states, hashes, duplicate content, known semantic
duplicates, lineage groups, and split contamination. Publication gates require zero blocking
findings.

### `adr-forge dataset build --manifest PATH --output PATH`

Builds a canonical prompt-completion dataset from approved examples. Output includes a manifest,
content hash, source version, and excluded-example report.

### `adr-forge retrieval snapshot --scenario REVISION_ID --output PATH`

Calls the configured retrieval provider and writes a canonical immutable snapshot. Failure leaves
no partially published snapshot.

### `adr-forge train sft --config PATH`

Runs GPU and disk preflight, acquires the exclusive GPU lease, records the effective configuration,
trains a QLoRA adapter, writes checkpoints atomically, and emits a final artifact manifest. It fails
without killing external GPU processes when capacity is insufficient.

### `adr-forge benchmark run --config PATH`

Runs the declared scenario-strategy matrix, preserves every terminal outcome, supports resuming
missing work without overwriting completed runs, and never reports a partial matrix as complete.

### `adr-forge benchmark report --experiment ID --output PATH`

Creates a report containing deterministic scores, human evaluation summaries, failures, exclusions,
latency, resource use, model and dataset identities, configuration, and reproduction instructions.

### `adr-forge artifacts list`

Lists artifact ID, kind, hash, size, retention state, reference count, and total budget use in a
deterministic order. `--json` returns `artifacts`, `artifact_count`, `used_bytes`, `warning_bytes`,
`limit_bytes`, `free_bytes`, and `reserve_bytes`; it never mutates or reconciles storage.

### `adr-forge artifacts prune --confirm`

Deletes only unreferenced artifacts marked `prunable` or expired `temporary`. Omission of
`--confirm` performs no mutation and exits `3`. Success reports `operation_id`, selected/deleted/
failed counts, reclaimed bytes, and one result per candidate. Every successful deletion preserves
an append-only metadata audit record. Referenced, `keep`, non-expired temporary, and unsafe-path
artifacts are never candidates.

### `adr-forge database backup --output PATH`

Creates a consistent SQLite backup plus a canonical JSON manifest containing format version, UTC
timestamp, schema revision, byte size, SHA-256, and application version. The output path must not
be the configured live database or an existing file. Publication uses temporary siblings and does
not leave a database or manifest on failure. `--json` returns both output paths and all manifest
fields.

## Progress Output

Long commands emit structured stage transitions to stderr in human mode and newline-delimited JSON
to stderr in `--json` mode. Final result JSON is written to stdout.

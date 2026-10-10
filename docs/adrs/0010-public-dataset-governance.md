# ADR-010 — Publish only reviewed and traceable dataset examples

- Status: accepted
- Date: 2026-10-10
- Decisors: Marcelo Soiber

## Context

The dataset is both training material and portfolio evidence. Unlicensed, private, synthetic-only,
or contaminated data would invalidate results and create legal or ethical risk.

## Decision

Publish only authored, reviewed synthetic, or compatibly licensed derived examples with source,
license, language, category, lineage, review identity, and content hash. Enforce immutable versions
and train/evaluation contamination gates.

## Alternatives considered

- Copy course materials: rejected without explicit authorization.
- Publish raw Knowledge Hub snapshots: rejected because sources may be private.
- Accept unreviewed synthetic volume: rejected because quantity does not establish quality.

## Consequences

Dataset growth is slower and requires manual review, but results are defensible and reproducible.

## Review triggers

Add multiple-reviewer workflow when dataset publication or evaluation becomes collaborative.

"""Persistence-neutral records for local artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class ArtifactKind(StrEnum):
    RAW_OUTPUT = "raw_output"
    RETRIEVAL_SNAPSHOT = "retrieval_snapshot"
    MODEL = "model"
    ADAPTER = "adapter"
    CHECKPOINT = "checkpoint"
    REPORT = "report"
    CONFIG = "config"
    LOG = "log"


class Retention(StrEnum):
    KEEP = "keep"
    PRUNABLE = "prunable"
    TEMPORARY = "temporary"


@dataclass(frozen=True, slots=True)
class Artifact:
    id: str
    kind: ArtifactKind
    relative_path: str
    sha256: str
    size_bytes: int
    media_type: str
    created_at: datetime
    retention: Retention


@dataclass(frozen=True, slots=True)
class ArtifactReference:
    artifact_id: str
    owner_type: str
    owner_id: str
    created_at: datetime

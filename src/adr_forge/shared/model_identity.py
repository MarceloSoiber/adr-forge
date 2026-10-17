"""Validation for immutable model identities used in reproducible runs."""

from __future__ import annotations

import re

_GIT_COMMIT_REVISION = re.compile(r"^[0-9a-f]{40}$")
DEFAULT_QWEN_MODEL_REVISION = "cdbee75f17c01a7cc42f958dc650907174af0554"


def require_immutable_model_revision(value: str | None) -> str:
    """Return a normalized resolved Git commit or reject a mutable reference."""
    if value is None:
        raise ValueError("model_revision must be an immutable resolved Git commit")
    revision = value.strip()
    if not _GIT_COMMIT_REVISION.fullmatch(revision):
        raise ValueError("model_revision must be a 40-character lowercase Git commit")
    return revision

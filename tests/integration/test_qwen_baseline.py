"""Opt-in local smoke test for the pinned Qwen baseline.

This module deliberately performs no model-framework import during collection.
It only runs when an operator explicitly enables it and forces the Hugging Face
clients offline so a normal test run can never trigger a download or network
request.
"""

from __future__ import annotations

import os
from uuid import uuid4

import pytest

pytestmark = pytest.mark.gpu

_ENABLE_ENV = "ADR_FORGE_QWEN_SMOKE"
_REVISION_ENV = "ADR_FORGE_QWEN_REVISION"


def _smoke_is_configured() -> bool:
    """Require both an explicit opt-in and a reproducible model revision."""
    return os.environ.get(_ENABLE_ENV) == "1" and bool(os.environ.get(_REVISION_ENV))


@pytest.mark.asyncio
async def test_qwen_baseline_generates_from_local_pinned_artifacts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise a locally cached Qwen model without permitting network access.

    Run manually with ``ADR_FORGE_QWEN_SMOKE=1`` and
    ``ADR_FORGE_QWEN_REVISION=<pinned-revision>`` after provisioning the model
    artifacts in the local Hugging Face cache.
    """
    if not _smoke_is_configured():
        pytest.skip(
            "set ADR_FORGE_QWEN_SMOKE=1 and ADR_FORGE_QWEN_REVISION to run the local GPU smoke"
        )

    # These are set before importing the adapter or Transformers.  A missing
    # local artifact therefore fails clearly instead of downloading anything.
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")

    torch = pytest.importorskip("torch", reason="Qwen GPU smoke requires optional ml dependencies")
    if not torch.cuda.is_available():
        pytest.skip("Qwen GPU smoke requires a locally available CUDA device")

    from adr_forge.scenarios.models import DecisionCategory, ScenarioRevision
    from adr_forge.strategies.qwen_runtime import QwenRuntime
    from adr_forge.system.progress import CancellationToken

    scenario = ScenarioRevision(
        scenario_id=uuid4(),
        revision_number=1,
        problem=(
            "Precisamos escolher uma tecnologia de persistência para um catálogo transacional "
            "com relações entre produtos, preços e estoque."
        ),
        facts=["O catálogo mantém relações entre produtos, preços e estoque."],
        constraints=["A avaliação deve usar somente recursos locais."],
        desired_qualities=["consistência", "auditabilidade"],
        candidate_alternatives=["PostgreSQL", "MongoDB"],
        categories=[DecisionCategory.SQL_VS_NOSQL],
    )

    result = await QwenRuntime(
        revision=os.environ[_REVISION_ENV], max_new_tokens=64
    ).generate(
        scenario, cancellation=CancellationToken()
    )

    assert result.raw_output.strip()

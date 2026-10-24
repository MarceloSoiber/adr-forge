"""Public discovery of locally configured analysis strategies."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict

from adr_forge.strategies.configuration import configured_registry

router = APIRouter(prefix="/api/v1")


class StrategySummary(BaseModel):
    """Public projection of a configured strategy's local availability."""

    model_config = ConfigDict(extra="forbid")

    id: str
    version: str
    kind: Literal["base", "prompted", "rag", "fine_tuned", "fine_tuned_rag"]
    model_id: str
    model_revision: str
    requires_retrieval: bool
    available: bool
    unavailable_reason: str | None = None
    unavailable_reason_code: str | None = None


@router.get(
    "/strategies",
    operation_id="listStrategies",
    response_model=list[StrategySummary],
)
async def list_strategies(request: Request) -> list[StrategySummary]:
    """Expose availability without loading optional model runtimes."""
    settings = request.app.state.settings
    registry = configured_registry(settings)
    return [
        StrategySummary(
            id=strategy.id,
            version=strategy.version,
            kind=strategy.kind.value,
            model_id=strategy.model_id,
            model_revision=strategy.model_revision,
            requires_retrieval=strategy.requires_retrieval,
            available=strategy.enabled and strategy.availability.available,
            unavailable_reason=(
                strategy.availability.unavailable_reason
                if not strategy.enabled or not strategy.availability.available
                else None
            ),
            unavailable_reason_code=(
                "strategy_disabled"
                if not strategy.enabled
                else strategy.availability.unavailable_reason_code
            ),
        )
        for strategy in registry.list()
    ]

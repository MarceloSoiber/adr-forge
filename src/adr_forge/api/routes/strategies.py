"""Public discovery of locally configured analysis strategies."""

from __future__ import annotations

from fastapi import APIRouter

from adr_forge.strategies.registry import default_registry

router = APIRouter(prefix="/api/v1")


@router.get("/strategies", operation_id="listStrategies")
async def list_strategies() -> list[dict[str, object]]:
    """Expose availability without loading optional model runtimes."""
    return [
        {
            "id": strategy.id,
            "version": strategy.version,
            "available": strategy.enabled and strategy.availability.available,
            "unavailable_reason": strategy.availability.unavailable_reason,
        }
        for strategy in default_registry().list()
    ]

"""Public discovery of locally configured analysis strategies."""

from __future__ import annotations

from fastapi import APIRouter, Request

from adr_forge.strategies.registry import default_registry

router = APIRouter(prefix="/api/v1")


@router.get("/strategies", operation_id="listStrategies")
async def list_strategies(request: Request) -> list[dict[str, object]]:
    """Expose availability without loading optional model runtimes."""
    settings = request.app.state.settings
    registry = default_registry(
        model_revision=settings.model_revision or "main",
        # The endpoint validates configuration only; it never probes the remote
        # service.  A token is required by the production Knowledge Hub adapter.
        retrieval_configured=settings.knowledge_hub_token is not None,
    )
    return [
        {
            "id": strategy.id,
            "version": strategy.version,
            "kind": strategy.kind.value,
            "model_id": strategy.model_id,
            "model_revision": strategy.model_revision,
            "requires_retrieval": strategy.requires_retrieval,
            "available": strategy.enabled and strategy.availability.available,
            "unavailable_reason": (
                strategy.availability.unavailable_reason
                if not strategy.enabled or not strategy.availability.available
                else None
            ),
            "unavailable_reason_code": (
                "strategy_disabled"
                if not strategy.enabled
                else strategy.availability.unavailable_reason_code
            ),
        }
        for strategy in registry.list()
    ]

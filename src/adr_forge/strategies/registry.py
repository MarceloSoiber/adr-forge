"""In-memory strategy registry for the local single-process application."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from uuid import UUID

from adr_forge.shared.hashing import canonical_sha256
from adr_forge.shared.model_identity import require_immutable_model_revision
from adr_forge.strategies.fine_tuned import AdapterVerificationError, verify_adapter_manifest
from adr_forge.strategies.models import (
    AnalysisStrategy,
    RuntimeKind,
    StrategyAvailability,
    StrategyKind,
)
from adr_forge.strategies.qwen_runtime import QWEN_MODEL_ID


class StrategyRegistry:
    def __init__(self, strategies: list[AnalysisStrategy] | None = None) -> None:
        self._strategies: dict[tuple[str, str], AnalysisStrategy] = {}
        for strategy in strategies or []:
            self.register(strategy)

    def register(self, strategy: AnalysisStrategy) -> None:
        key = (strategy.id, strategy.version)
        if key in self._strategies:
            raise ValueError(f"strategy already registered: {strategy.id}@{strategy.version}")
        self._strategies[key] = strategy

    def get(self, strategy_id: str, version: str) -> AnalysisStrategy | None:
        return self._strategies.get((strategy_id, version))

    def list(self) -> list[AnalysisStrategy]:
        return sorted(
            self._strategies.values(), key=lambda strategy: (strategy.id, strategy.version)
        )

    def available_for(
        self,
        strategy_id: str,
        version: str,
        *,
        snapshot_id: UUID | None = None,
    ) -> StrategyAvailability:
        """Return request-aware availability without attempting external retrieval."""
        strategy = self.get(strategy_id, version)
        if strategy is None:
            return _unavailable("strategy_not_found", "Estratégia não configurada.")
        if not strategy.enabled:
            return _unavailable(
                "strategy_disabled", "Estratégia desabilitada na configuração local."
            )
        if not strategy.availability.available:
            return strategy.availability
        if strategy.requires_retrieval and snapshot_id is None:
            return _unavailable(
                "retrieval_snapshot_required",
                "Esta estratégia exige um snapshot de recuperação válido.",
            )
        if not strategy.requires_retrieval and snapshot_id is not None:
            return _unavailable(
                "retrieval_snapshot_not_supported",
                "Esta estratégia não aceita snapshot de recuperação.",
            )
        return StrategyAvailability(available=True)


def _unavailable(code: str, reason: str) -> StrategyAvailability:
    return StrategyAvailability(
        available=False, unavailable_reason=reason, unavailable_reason_code=code
    )


def default_registry(
    model_revision: str | None = None,
    *,
    lm_studio_base_url: object | None = None,
    lm_studio_model_id: str | None = None,
    retrieval_configured: bool = False,
    adapter_artifact_id: UUID | None = None,
    adapter_manifest_path: Path | None = None,
    adapter_runtime_available: bool = False,
    enabled: Iterable[str] | None = None,
) -> StrategyRegistry:
    """Return all configured Phase 5 strategy compositions.

    This function only inspects local configuration.  It deliberately never
    calls Knowledge Hub or imports optional ML runtimes, so strategy discovery
    stays fast and deterministic.
    """
    model_revision = require_immutable_model_revision(model_revision)
    generation_config_hash = canonical_sha256({"max_new_tokens": 1024, "temperature": 0})
    enabled_ids = set(enabled) if enabled is not None else None

    def is_enabled(strategy_id: str) -> bool:
        return enabled_ids is None or strategy_id in enabled_ids

    retrieval_availability = (
        StrategyAvailability(available=True)
        if retrieval_configured
        else _unavailable(
            "retrieval_provider_unconfigured",
            "O provedor de recuperação Knowledge Hub não está configurado.",
        )
    )
    adapter_availability = _adapter_availability(
        adapter_artifact_id,
        adapter_manifest_path,
        model_revision,
        adapter_runtime_available,
    )
    lm_studio_available = lm_studio_base_url is not None and lm_studio_model_id is not None
    lm_studio_availability = (
        StrategyAvailability(available=True)
        if lm_studio_available
        else _unavailable(
            "lm_studio_unconfigured",
            "Configure ADR_FORGE_LM_STUDIO_BASE_URL e ADR_FORGE_LM_STUDIO_MODEL_ID.",
        )
    )
    return StrategyRegistry(
        [
            AnalysisStrategy(
                id="fake-baseline",
                version="1",
                kind=StrategyKind.BASE,
                model_id="adr-forge/fake",
                model_revision="1",
                prompt_version="adr-v1",
                generation_config_hash=generation_config_hash,
                runtime_kind=RuntimeKind.FAKE,
                enabled=is_enabled("fake-baseline"),
                availability=StrategyAvailability(available=True),
            ),
            AnalysisStrategy(
                id="prompted",
                version="1",
                kind=StrategyKind.PROMPTED,
                model_id="adr-forge/fake",
                model_revision="1",
                prompt_version="adr-structured-v1",
                generation_config_hash=generation_config_hash,
                runtime_kind=RuntimeKind.FAKE,
                enabled=is_enabled("prompted"),
                availability=StrategyAvailability(available=True),
            ),
            AnalysisStrategy(
                id="rag",
                version="1",
                kind=StrategyKind.RAG,
                model_id="adr-forge/fake",
                model_revision="1",
                prompt_version="adr-rag-v1",
                generation_config_hash=generation_config_hash,
                requires_retrieval=True,
                runtime_kind=RuntimeKind.FAKE,
                enabled=is_enabled("rag"),
                availability=retrieval_availability,
            ),
            AnalysisStrategy(
                id="fine-tuned",
                version="1",
                kind=StrategyKind.FINE_TUNED,
                model_id=QWEN_MODEL_ID,
                model_revision=model_revision,
                adapter_artifact_id=adapter_artifact_id,
                prompt_version="adr-structured-v1",
                generation_config_hash=generation_config_hash,
                runtime_kind=RuntimeKind.TRANSFORMERS,
                enabled=is_enabled("fine-tuned"),
                availability=adapter_availability,
            ),
            AnalysisStrategy(
                id="fine-tuned-rag",
                version="1",
                kind=StrategyKind.FINE_TUNED_RAG,
                model_id=QWEN_MODEL_ID,
                model_revision=model_revision,
                adapter_artifact_id=adapter_artifact_id,
                prompt_version="adr-rag-v1",
                generation_config_hash=generation_config_hash,
                requires_retrieval=True,
                runtime_kind=RuntimeKind.TRANSFORMERS,
                enabled=is_enabled("fine-tuned-rag"),
                availability=adapter_availability,
            ),
            AnalysisStrategy(
                id="qwen3-4b-baseline",
                version="1",
                kind=StrategyKind.BASE,
                # LM Studio reports the loaded GGUF identifier; the immutable HF
                # revision remains the provenance reference for this baseline.
                model_id=lm_studio_model_id or QWEN_MODEL_ID,
                model_revision=model_revision,
                prompt_version="adr-v1",
                generation_config_hash=generation_config_hash,
                runtime_kind=RuntimeKind.OPENAI_COMPATIBLE,
                enabled=is_enabled("qwen3-4b-baseline"),
                availability=lm_studio_availability,
            ),
        ]
    )


def _adapter_availability(
    artifact_id: UUID | None,
    manifest_path: Path | None,
    model_revision: str,
    runtime_available: bool,
) -> StrategyAvailability:
    if artifact_id is None or manifest_path is None:
        return _unavailable(
            "adapter_artifact_missing", "Não há um artefato de adaptador configurado."
        )
    try:
        verify_adapter_manifest(
            manifest_path,
            expected_model_id=QWEN_MODEL_ID,
            expected_model_revision=model_revision,
        )
    except AdapterVerificationError as exc:
        return _unavailable(str(exc), "O artefato do adaptador não foi verificado.")
    if not runtime_available:
        return _unavailable(
            "adapter_runtime_unavailable", "O runtime do adaptador configurado não está disponível."
        )
    return StrategyAvailability(available=True)

"""Validated, local-first application configuration."""

from __future__ import annotations

import ipaddress
from pathlib import Path
from typing import Annotated

from pydantic import AliasChoices, AnyHttpUrl, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from adr_forge.shared.model_identity import (
    DEFAULT_QWEN_MODEL_REVISION,
    require_immutable_model_revision,
)

GIB = 1024**3
DEFAULT_ARTIFACT_WARNING_BYTES = 40 * GIB
DEFAULT_ARTIFACT_LIMIT_BYTES = 50 * GIB
DEFAULT_ARTIFACT_FREE_DISK_RESERVE_BYTES = 5 * GIB


def _validate_loopback(host: str) -> str:
    if host.lower() == "localhost":
        return host
    try:
        if ipaddress.ip_address(host).is_loopback:
            return host
    except ValueError:
        pass
    raise ValueError("host must be a loopback address")


class Settings(BaseSettings):
    """The sole configuration composition root for ADR Forge."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="ADR_FORGE_", extra="ignore")

    host: str = "127.0.0.1"
    port: Annotated[int, Field(ge=1, le=65535)] = 8000
    web_host: str = "127.0.0.1"
    web_port: Annotated[int, Field(ge=1, le=65535)] = 5173
    database_url: str = "sqlite+aiosqlite:///./data/adr-forge.sqlite3"
    artifact_root: Path = Path("./data/artifacts")
    artifact_warning_bytes: Annotated[int, Field(gt=0)] = DEFAULT_ARTIFACT_WARNING_BYTES
    artifact_limit_bytes: Annotated[int, Field(gt=0)] = DEFAULT_ARTIFACT_LIMIT_BYTES
    artifact_free_disk_reserve_bytes: Annotated[int, Field(gt=0)] = (
        DEFAULT_ARTIFACT_FREE_DISK_RESERVE_BYTES
    )
    knowledge_hub_base_url: AnyHttpUrl = Field(
        default=AnyHttpUrl("http://127.0.0.1:8001"),
        validation_alias=AliasChoices("KNOWLEDGE_HUB_BASE_URL", "ADR_FORGE_KNOWLEDGE_HUB_BASE_URL"),
    )
    knowledge_hub_token: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("KNOWLEDGE_HUB_TOKEN", "ADR_FORGE_KNOWLEDGE_HUB_TOKEN"),
    )
    hf_token: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("HF_TOKEN", "ADR_FORGE_HF_TOKEN")
    )
    hf_home: Path = Field(
        default=Path("./data/huggingface"),
        validation_alias=AliasChoices("HF_HOME", "ADR_FORGE_HF_HOME"),
    )
    adapter_manifest_path: Path | None = Field(
        default=Path("./data/training/qwen3-4b-adr-json/adapter-manifest.json"),
        validation_alias=AliasChoices(
            "ADR_FORGE_ADAPTER_MANIFEST_PATH",
            "ADAPTER_MANIFEST_PATH",
        ),
    )
    model_id: str = "Qwen/Qwen3-4B-Instruct-2507"
    model_revision: str = DEFAULT_QWEN_MODEL_REVISION
    model_trust_remote_code: bool = False
    # The OpenAI-compatible endpoint is deliberately opt-in: a configured
    # application never probes a LAN service unless both values are supplied.
    lm_studio_base_url: AnyHttpUrl | None = None
    lm_studio_model_id: str | None = Field(default=None, min_length=1)
    lm_studio_api_key: SecretStr | None = None
    lm_studio_timeout_seconds: Annotated[int, Field(ge=1, le=300)] = 120

    @field_validator("host", "web_host")
    @classmethod
    def loopback_hosts_only(cls, value: str) -> str:
        return _validate_loopback(value)

    @field_validator("artifact_root", "hf_home", "adapter_manifest_path")
    @classmethod
    def typed_paths(cls, value: Path | None) -> Path | None:
        return value.expanduser() if value is not None else None

    @field_validator("model_revision")
    @classmethod
    def immutable_model_revision(cls, value: str) -> str:
        return require_immutable_model_revision(value)

    @model_validator(mode="after")
    def validate_artifact_budget(self) -> Settings:
        if self.artifact_warning_bytes >= self.artifact_limit_bytes:
            raise ValueError("artifact_warning_bytes must be less than artifact_limit_bytes")
        if self.artifact_limit_bytes > DEFAULT_ARTIFACT_LIMIT_BYTES:
            raise ValueError("artifact_limit_bytes cannot exceed the 50 GiB local safety limit")
        if self.model_trust_remote_code:
            raise ValueError("model_trust_remote_code must be false")
        if (self.lm_studio_base_url is None) != (self.lm_studio_model_id is None):
            raise ValueError(
                "lm_studio_base_url and lm_studio_model_id must be configured together"
            )
        return self


AppSettings = Settings

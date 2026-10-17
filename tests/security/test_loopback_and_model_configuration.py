"""Offline fail-closed checks for network and local-model configuration."""

from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from adr_forge.shared.config import Settings
from adr_forge.strategies.registry import default_registry

PINNED_REVISION = "cdbee75f17c01a7cc42f958dc650907174af0554"
WILDCARD_HOST = ".".join(("0", "0", "0", "0"))


@pytest.mark.parametrize("host", [WILDCARD_HOST, "192.168.15.125", "10.0.0.1", "example.com"])
def test_unauthenticated_bindings_reject_wildcard_lan_and_public_hosts(host: str) -> None:
    with pytest.raises(PydanticValidationError, match="loopback"):
        Settings(host=host)
    with pytest.raises(PydanticValidationError, match="loopback"):
        Settings(web_host=host)


@pytest.mark.parametrize("host", ["127.0.0.1", "::1", "localhost"])
def test_loopback_bindings_remain_accepted(host: str) -> None:
    settings = Settings(host=host, web_host=host, model_revision=PINNED_REVISION)
    assert settings.host == host
    assert settings.web_host == host


@pytest.mark.parametrize("revision", [None, "", "main", "latest"])
def test_model_configuration_rejects_unpinned_revisions_before_registry_activation(
    revision: str | None,
) -> None:
    with pytest.raises((PydanticValidationError, ValueError), match=r"revision|pinned|immutable"):
        Settings(model_revision=revision)
    with pytest.raises(ValueError, match=r"revision|pinned|immutable"):
        default_registry(model_revision=revision or "main")


def test_model_configuration_rejects_remote_code_execution() -> None:
    with pytest.raises(PydanticValidationError, match=r"remote.code|remote_code"):
        Settings(model_trust_remote_code=True)

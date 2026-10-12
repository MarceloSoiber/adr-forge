from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError as PydanticValidationError

from adr_forge.api.problem_details import problem_from_error, problem_response
from adr_forge.shared.config import Settings
from adr_forge.shared.errors import NotFoundError
from adr_forge.shared.hashing import canonical_json, canonical_sha256
from adr_forge.shared.identity import new_uuid7
from adr_forge.shared.logging import JsonFormatter, log_context
from adr_forge.shared.time import utc_now


def test_uuid7_and_clock_are_time_safe() -> None:
    assert new_uuid7().version == 7
    assert utc_now().tzinfo is UTC


def test_canonical_json_is_order_independent_and_rejects_naive_datetime() -> None:
    value = {"b": Decimal("1.20"), "a": datetime(2026, 1, 1, tzinfo=UTC)}
    assert canonical_json(value) == '{"a":"2026-01-01T00:00:00Z","b":"1.2"}'
    assert canonical_sha256({"a": 1, "b": 2}) == canonical_sha256({"b": 2, "a": 1})
    with pytest.raises(ValueError, match="timezone-aware"):
        canonical_json(datetime(2026, 1, 1))


def test_settings_enforce_loopback_and_artifact_budget() -> None:
    assert Settings().artifact_free_disk_reserve_bytes == 5 * 1024**3
    with pytest.raises(PydanticValidationError, match="loopback"):
        Settings(host="0.0.0.0")  # noqa: S104
    with pytest.raises(PydanticValidationError, match="less than"):
        Settings(artifact_warning_bytes=10, artifact_limit_bytes=10)


def test_domain_errors_are_problem_details_with_stable_code() -> None:
    response = problem_response(
        problem_from_error(NotFoundError("No scenario has this identifier"), request_id="req-1")
    )
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    assert b'"code":"not_found"' in response.body
    assert b'"request_id":"req-1"' in response.body


def test_structured_logs_redact_sensitive_fields_and_keep_correlation() -> None:
    record = logging.LogRecord("adr_forge", logging.INFO, __file__, 1, "completed", (), None)
    record.structured = {"token": "secret", "retrieved_content": "untrusted", "safe": "yes"}
    with log_context(request_id="req-1", run_id="run-1"):
        payload = json.loads(JsonFormatter().format(record))
    assert payload["token"] == "[REDACTED]"  # noqa: S105
    assert payload["retrieved_content"] == "[REDACTED]"
    assert payload["request_id"] == "req-1"
    assert payload["run_id"] == "run-1"

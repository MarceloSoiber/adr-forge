"""Offline adversarial checks for secret-safe diagnostic output."""

from __future__ import annotations

import json
import logging

from adr_forge.shared.logging import REDACTED, JsonFormatter


def test_nested_secret_and_prompt_sentinels_never_reach_structured_logs() -> None:
    token = "security-test-token-7ddf0e5a"  # noqa: S105 - controlled sentinel
    prompt = "security-test-prompt-9f2ab1c4"
    retrieved = "security-test-retrieved-0c6e8ab3"
    record = logging.LogRecord("adr_forge", logging.ERROR, __file__, 1, "request failed", (), None)
    record.structured = {
        "authorization": f"Bearer {token}",
        "failure": {
            "api_token": token,
            "original_prompt": prompt,
            "retrieved_content": retrieved,
        },
        "safe": "retained",
    }

    rendered = JsonFormatter().format(record)
    payload = json.loads(rendered)

    assert token not in rendered
    assert prompt not in rendered
    assert retrieved not in rendered
    assert payload["authorization"] == REDACTED
    assert payload["failure"] == {
        "api_token": REDACTED,
        "original_prompt": REDACTED,
        "retrieved_content": REDACTED,
    }
    assert payload["safe"] == "retained"

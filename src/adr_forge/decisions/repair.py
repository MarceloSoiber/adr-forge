"""Conservative, deterministic normalization for known model output shapes."""

from __future__ import annotations

import json
from typing import Any


def repair_adr_json(raw_output: str) -> str:
    """Normalize known non-semantic shapes without inventing ADR content.

    The original output is retained by the caller. This function never creates
    facts or decisions: an object without a non-empty textual ``restriction``
    remains unchanged. It also removes only an empty root ``reference`` field,
    which is not part of the ADR contract.
    """
    try:
        payload = json.loads(raw_output)
    except json.JSONDecodeError:
        return raw_output
    if not isinstance(payload, dict):
        return raw_output

    changed = False
    constraints = payload.get("constraints")
    if isinstance(constraints, list):
        repaired_constraints: list[Any] = []
        for constraint in constraints:
            if isinstance(constraint, dict):
                restriction = constraint.get("restriction")
                if isinstance(restriction, str) and restriction.strip():
                    repaired_constraints.append(restriction.strip())
                    changed = True
                    continue
            repaired_constraints.append(constraint)
        payload["constraints"] = repaired_constraints
    if payload.get("reference") is None and "reference" in payload:
        del payload["reference"]
        changed = True
    if not changed:
        return raw_output
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

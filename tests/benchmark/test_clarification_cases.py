"""Deterministic adverse cases for provisional clarification output."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest

from adr_forge.decisions.parsing import parse_adr_output
from adr_forge.decisions.validation import classify_context
from adr_forge.scenarios.models import DecisionCategory, ScenarioRevision
from adr_forge.strategies.fake import FakeStrategy
from adr_forge.system.progress import CancellationToken

FIXTURES = Path("datasets/fixtures/clarification.jsonl")
CASES = [json.loads(line) for line in FIXTURES.read_text(encoding="utf-8").splitlines()]


@pytest.mark.asyncio
async def test_reviewed_adverse_cases_produce_bounded_provisional_questions() -> None:
    for fixture in CASES:
        scenario = ScenarioRevision(
            scenario_id=uuid4(),
            revision_number=1,
            problem=fixture["input"]["problem"],
            facts=fixture["input"]["facts"],
            constraints=fixture["input"]["constraints"],
            categories=[DecisionCategory(fixture["category"])],
        )
        findings = classify_context(scenario)
        assert fixture["expected_issue_kind"] in {finding.code for finding in findings}
        generated = await FakeStrategy().generate(scenario, cancellation=CancellationToken())
        parsed = parse_adr_output(generated.raw_output, uuid4())
        assert parsed.draft is not None
        if fixture["expected_issue_kind"] != "context.forced_preference":
            assert parsed.draft.status.value == "provisional"
            assert 1 <= len(parsed.draft.unresolved_questions) <= 3
            assert all(question.impact for question in parsed.draft.unresolved_questions)
            assert parsed.draft.assumptions
            assert parsed.draft.confidence <= 0.60

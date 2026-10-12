"""Phase 3 analysis HTTP contract.

The checked-in OpenAPI document is the source of truth.  These tests keep the
FastAPI schema honest while the feature routes are built incrementally.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from apps.api.main import create_app


CONTRACT_PATH = (
    Path(__file__).resolve().parents[2]
    / "specs/001-architecture-decision-lab/contracts/api.openapi.yaml"
)


@pytest.mark.parametrize(
    ("path", "method", "operation_id", "success_status", "content_type"),
    [
        ("/scenarios", "post", "createScenario", "201", "application/json"),
        ("/scenarios/{scenarioId}", "get", "getScenario", "200", "application/json"),
        ("/analysis-runs", "post", "createAnalysisRun", "202", "application/json"),
        ("/analysis-runs/{runId}", "get", "getAnalysisRun", "200", "application/json"),
        (
            "/analysis-runs/{runId}/events",
            "get",
            "streamAnalysisRunEvents",
            "200",
            "text/event-stream",
        ),
        (
            "/analysis-runs/{runId}/cancel",
            "post",
            "cancelAnalysisRun",
            "202",
            "application/json",
        ),
        ("/analysis-runs/{runId}/adr", "get", "getRunAdr", "200", "application/json"),
        (
            "/analysis-runs/{runId}/export",
            "get",
            "exportRunAdr",
            "200",
            "text/markdown",
        ),
    ],
)
def test_analysis_operations_are_exposed_in_application_openapi(
    path: str,
    method: str,
    operation_id: str,
    success_status: str,
    content_type: str,
) -> None:
    operation = create_app().openapi()["paths"][path][method]

    assert operation["operationId"] == operation_id
    assert success_status in operation["responses"]
    assert content_type in operation["responses"][success_status]["content"]


def test_checked_contract_declares_phase_three_payloads_and_errors() -> None:
    """Guard request/response DTOs, problem details, progress, and export semantics."""
    contract = CONTRACT_PATH.read_text(encoding="utf-8")

    for expected in (
        'servers:\n  - url: http://127.0.0.1:8000/api/v1',
        'operationId: createScenario',
        '$ref: "#/components/schemas/CreateScenarioRequest"',
        '$ref: "#/components/schemas/ScenarioResponse"',
        'operationId: createAnalysisRun',
        '$ref: "#/components/schemas/CreateAnalysisRunRequest"',
        '$ref: "#/components/schemas/AnalysisRun"',
        'operationId: streamAnalysisRunEvents',
        'text/event-stream:',
        'event: progress',
        'operationId: getRunAdr',
        '$ref: "#/components/schemas/AdrDraft"',
        'operationId: exportRunAdr',
        'enum: [markdown, json]',
        'Content-Disposition:',
        'application/problem+json:',
        'required: [type, title, status]',
    ):
        assert expected in contract


def test_run_event_operation_documents_progress_payload_and_terminal_close() -> None:
    contract = CONTRACT_PATH.read_text(encoding="utf-8")

    assert "first event is the current persisted" in contract
    assert "payload conforms to ProgressEvent" in contract
    assert "closes the\n            stream after a terminal status" in contract
    assert '"progress_sequence":3' in contract


def test_export_operation_documents_markdown_and_json_representations() -> None:
    contract = CONTRACT_PATH.read_text(encoding="utf-8")
    export_section = contract[contract.index("  /analysis-runs/{runId}/export:") :]

    assert "text/markdown:" in export_section
    assert "application/json:" in export_section
    assert '$ref: "#/components/schemas/AdrDraft"' in export_section

"""OpenAPI contract coverage for the Phase 3 analysis flow.

The checked-in contract is the public API source of truth.  These tests verify
that the FastAPI document exposes the same operations and that the schemas
which carry scenario, run, progress, ADR, error, and export data keep the
fields clients rely on.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest
from apps.api.main import create_app

CONTRACT_PATH = (
    Path(__file__).resolve().parents[2]
    / "specs/001-architecture-decision-lab/contracts/api.openapi.yaml"
)
API_PREFIX = "/api/v1"


def _operation(document: Mapping[str, object], path: str, method: str) -> Mapping[str, object]:
    """Get an operation whether FastAPI includes the application prefix or not."""
    paths = document["paths"]
    assert isinstance(paths, Mapping)
    operation_path = path if path in paths else f"{API_PREFIX}{path}"
    item = paths[operation_path]
    assert isinstance(item, Mapping)
    operation = item[method]
    assert isinstance(operation, Mapping)
    return operation


def _schema(document: Mapping[str, object], name: str) -> Mapping[str, object]:
    components = document["components"]
    assert isinstance(components, Mapping)
    schemas = components["schemas"]
    assert isinstance(schemas, Mapping)
    result = schemas[name]
    assert isinstance(result, Mapping)
    return result


def _response_schema(
    document: Mapping[str, object], path: str, method: str, status: str, media_type: str
) -> Mapping[str, object]:
    responses = _operation(document, path, method)["responses"]
    assert isinstance(responses, Mapping)
    response = responses[status]
    assert isinstance(response, Mapping)
    content = response["content"]
    assert isinstance(content, Mapping)
    representation = content[media_type]
    assert isinstance(representation, Mapping)
    schema = representation["schema"]
    assert isinstance(schema, Mapping)
    return schema


@pytest.fixture(scope="module")
def application_openapi() -> Mapping[str, object]:
    return create_app().openapi()


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
        ("/analysis-runs/{runId}/cancel", "post", "cancelAnalysisRun", "202", "application/json"),
        ("/analysis-runs/{runId}/adr", "get", "getRunAdr", "200", "application/json"),
        ("/analysis-runs/{runId}/export", "get", "exportRunAdr", "200", "text/markdown"),
    ],
)
def test_analysis_operations_are_exposed_in_application_openapi(
    application_openapi: Mapping[str, object],
    path: str,
    method: str,
    operation_id: str,
    success_status: str,
    content_type: str,
) -> None:
    operation = _operation(application_openapi, path, method)

    assert operation["operationId"] == operation_id
    responses = operation["responses"]
    assert isinstance(responses, Mapping)
    assert success_status in responses
    response = responses[success_status]
    assert isinstance(response, Mapping)
    content = response["content"]
    assert isinstance(content, Mapping)
    assert content_type in content


@pytest.mark.parametrize(
    ("path", "method", "status"),
    [
        ("/scenarios", "post", "422"),
        ("/scenarios/{scenarioId}", "get", "404"),
        ("/analysis-runs", "post", "409"),
        ("/analysis-runs", "post", "422"),
        ("/analysis-runs/{runId}", "get", "404"),
        ("/analysis-runs/{runId}/events", "get", "404"),
        ("/analysis-runs/{runId}/cancel", "post", "404"),
        ("/analysis-runs/{runId}/cancel", "post", "409"),
        ("/analysis-runs/{runId}/adr", "get", "404"),
        ("/analysis-runs/{runId}/adr", "get", "409"),
        ("/analysis-runs/{runId}/export", "get", "404"),
        ("/analysis-runs/{runId}/export", "get", "409"),
    ],
)
def test_analysis_failures_advertise_problem_details(
    application_openapi: Mapping[str, object], path: str, method: str, status: str
) -> None:
    responses = _operation(application_openapi, path, method)["responses"]
    assert isinstance(responses, Mapping)
    response = responses[status]
    assert isinstance(response, Mapping)
    content = response["content"]
    assert isinstance(content, Mapping)
    problem = content["application/problem+json"]
    assert isinstance(problem, Mapping)
    assert problem["schema"] == {"$ref": "#/components/schemas/Problem"}


def test_scenario_and_run_payloads_have_stable_contract_fields(
    application_openapi: Mapping[str, object],
) -> None:
    scenario_request = _schema(application_openapi, "CreateScenarioRequest")
    scenario = _schema(application_openapi, "ScenarioResponse")
    revision = _schema(application_openapi, "ScenarioRevision")
    run_request = _schema(application_openapi, "CreateAnalysisRunRequest")
    run = _schema(application_openapi, "AnalysisRun")

    assert set(scenario_request["required"]) == {"title", "language", "problem"}
    assert scenario_request["properties"]["language"] == {"type": "string", "const": "pt-BR"}
    assert {"id", "title", "language", "current_revision"} <= set(scenario["required"])
    assert {
        "id",
        "scenario_id",
        "revision_number",
        "categories",
        "content_hash",
        "created_at",
    } <= set(revision["required"])
    assert set(run_request["required"]) == {
        "scenario_revision_id",
        "strategy_id",
        "strategy_version",
    }
    assert {
        "id",
        "scenario_revision_id",
        "strategy_id",
        "strategy_version",
        "status",
        "stage",
        "progress_sequence",
        "validation_attempts",
        "created_at",
        "updated_at",
    } <= set(run["required"])
    assert set(run["properties"]["status"]["enum"]) == {
        "pending",
        "waiting_resources",
        "running",
        "completed",
        "needs_clarification",
        "invalid_output",
        "failed",
        "cancelled",
        "interrupted",
    }


def test_progress_adr_problem_and_export_schemas_are_complete(
    application_openapi: Mapping[str, object],
) -> None:
    progress = _schema(application_openapi, "ProgressEvent")
    adr = _schema(application_openapi, "AdrDraft")
    problem = _schema(application_openapi, "Problem")

    assert {"run_id", "status", "stage", "progress_sequence", "updated_at"} <= set(
        progress["required"]
    )
    assert progress["properties"]["progress_sequence"] == {"type": "integer", "minimum": 0}
    assert adr["additionalProperties"] is False
    assert {
        "id",
        "analysis_run_id",
        "schema_version",
        "title",
        "status",
        "alternatives",
        "decision",
        "rationale",
        "risks",
        "review_triggers",
        "confidence",
    } <= set(adr["required"])
    assert problem["required"] == ["type", "title", "status"]
    assert {"type", "title", "status", "detail", "code", "request_id"} <= set(problem["properties"])

    markdown = _response_schema(
        application_openapi, "/analysis-runs/{runId}/export", "get", "200", "text/markdown"
    )
    exported_json = _response_schema(
        application_openapi, "/analysis-runs/{runId}/export", "get", "200", "application/json"
    )
    assert markdown["type"] == "string"
    assert exported_json == {"$ref": "#/components/schemas/AdrDraft"}


def test_checked_contract_declares_phase_three_payloads_and_errors() -> None:
    """Keep the source contract explicit even before a router is mounted."""
    contract = CONTRACT_PATH.read_text(encoding="utf-8")

    for expected in (
        "servers:\n  - url: http://127.0.0.1:8000/api/v1",
        "operationId: createScenario",
        '$ref: "#/components/schemas/CreateScenarioRequest"',
        '$ref: "#/components/schemas/ScenarioResponse"',
        "operationId: createAnalysisRun",
        '$ref: "#/components/schemas/CreateAnalysisRunRequest"',
        '$ref: "#/components/schemas/AnalysisRun"',
        "operationId: streamAnalysisRunEvents",
        "text/event-stream:",
        "event: progress",
        "operationId: getRunAdr",
        '$ref: "#/components/schemas/AdrDraft"',
        "operationId: exportRunAdr",
        "enum: [markdown, json]",
        "Content-Disposition:",
        "application/problem+json:",
        "required: [type, title, status]",
    ):
        assert expected in contract


def test_run_event_operation_documents_progress_payload_and_terminal_close() -> None:
    contract = CONTRACT_PATH.read_text(encoding="utf-8")

    assert "first event is the current persisted" in contract
    assert "payload conforms to ProgressEvent" in contract
    assert "closes the\n            stream after a terminal status" in contract
    assert '\\"progress_sequence\\":3' in contract

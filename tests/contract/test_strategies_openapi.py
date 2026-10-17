"""OpenAPI coverage for public strategy discovery."""

from __future__ import annotations

from collections.abc import Mapping

from apps.api.main import create_app


def test_strategies_operation_and_summary_schema_match_the_public_contract() -> None:
    """Keep discovery metadata and nullable availability diagnostics explicit."""
    document = create_app().openapi()
    paths = document["paths"]
    assert isinstance(paths, Mapping)
    strategies = paths["/api/v1/strategies"]
    assert isinstance(strategies, Mapping)
    operation = strategies["get"]
    assert isinstance(operation, Mapping)

    assert operation["operationId"] == "listStrategies"
    responses = operation["responses"]
    assert isinstance(responses, Mapping)
    successful = responses["200"]
    assert isinstance(successful, Mapping)
    content = successful["content"]
    assert isinstance(content, Mapping)
    response_schema = content["application/json"]
    assert isinstance(response_schema, Mapping)
    assert response_schema["schema"] == {
        "type": "array",
        "items": {"$ref": "#/components/schemas/StrategySummary"},
    }

    components = document["components"]
    assert isinstance(components, Mapping)
    schemas = components["schemas"]
    assert isinstance(schemas, Mapping)
    summary = schemas["StrategySummary"]
    assert isinstance(summary, Mapping)
    assert summary["type"] == "object"
    assert summary["additionalProperties"] is False
    assert summary["required"] == [
        "id",
        "version",
        "kind",
        "model_id",
        "model_revision",
        "requires_retrieval",
        "available",
    ]
    properties = summary["properties"]
    assert isinstance(properties, Mapping)
    assert properties["kind"] == {
        "type": "string",
        "enum": ["base", "prompted", "rag", "fine_tuned", "fine_tuned_rag"],
    }
    assert properties["unavailable_reason"] == {"anyOf": [{"type": "string"}, {"type": "null"}]}
    assert properties["unavailable_reason_code"] == {
        "anyOf": [{"type": "string"}, {"type": "null"}]
    }

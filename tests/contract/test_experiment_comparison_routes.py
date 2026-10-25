"""Contract alignment for experiment and blind-comparison route identities."""

from __future__ import annotations

from collections.abc import Mapping

import pytest
from apps.api.main import create_app


@pytest.fixture(scope="module")
def paths() -> Mapping[str, object]:
    document = create_app().openapi()
    result = document["paths"]
    assert isinstance(result, Mapping)
    return result


@pytest.mark.parametrize(
    ("path", "method", "operation_id"),
    [
        ("/api/v1/experiments/{experimentId}", "get", "getExperiment"),
        ("/api/v1/experiments/{experimentId}/runs", "get", "listExperimentRuns"),
        ("/api/v1/experiments/{experimentId}/report", "get", "getExperimentReport"),
        ("/api/v1/comparisons", "post", "createBlindComparison"),
        ("/api/v1/comparisons/{comparisonId}", "get", "getBlindComparison"),
        (
            "/api/v1/comparisons/{comparisonId}/evaluation",
            "post",
            "submitBlindEvaluation",
        ),
        (
            "/api/v1/comparisons/{comparisonId}/reveal",
            "get",
            "revealComparisonIdentities",
        ),
    ],
)
def test_route_paths_and_operation_ids_match_the_published_contract(
    paths: Mapping[str, object], path: str, method: str, operation_id: str
) -> None:
    item = paths[path]
    assert isinstance(item, Mapping)
    operation = item[method]
    assert isinstance(operation, Mapping)
    assert operation["operationId"] == operation_id

"""ADR Forge's local-only FastAPI composition root."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import RequestResponseEndpoint

from adr_forge.api.problem_details import install_problem_details_handlers
from adr_forge.api.routes.analysis import ProgressEvent
from adr_forge.api.routes.analysis import router as analysis_router
from adr_forge.api.routes.comparisons import router as comparisons_router
from adr_forge.api.routes.experiments import router as experiments_router
from adr_forge.api.routes.retrieval import router as retrieval_router
from adr_forge.api.routes.strategies import router as strategies_router
from adr_forge.api.routes.system import router as system_router
from adr_forge.artifacts.store import ArtifactStore
from adr_forge.experiments.run_repository import RunRepository
from adr_forge.persistence.database import create_database_engine, create_session_factory
from adr_forge.shared.config import Settings
from adr_forge.strategies.executor import AnalysisExecutor
from adr_forge.system.resources import HostResourceProbe


def _remove_generated_schema_titles(value: object) -> None:
    """Keep generated OpenAPI aligned with the title-free committed contract."""
    if isinstance(value, dict):
        value.pop("title", None)
        for nested in value.values():
            _remove_generated_schema_titles(nested)
    elif isinstance(value, list):
        for nested in value:
            _remove_generated_schema_titles(nested)


def _canonicalize_nullable_any_of(value: object) -> None:
    """Emit nullable schemas in the contract's compact OpenAPI 3.1 form."""
    if isinstance(value, dict):
        options = value.get("anyOf")
        if (
            isinstance(options, list)
            and len(options) == 2
            and isinstance(options[0], dict)
            and isinstance(options[1], dict)
        ):
            null_option = next((option for option in options if option == {"type": "null"}), None)
            typed_option = next((option for option in options if option is not null_option), None)
            if (
                null_option is not None
                and isinstance(typed_option, dict)
                and isinstance(typed_option.get("type"), str)
            ):
                value.pop("anyOf")
                value.update(typed_option)
                value["type"] = [typed_option["type"], "null"]
        for nested in value.values():
            _canonicalize_nullable_any_of(nested)
    elif isinstance(value, list):
        for nested in value:
            _canonicalize_nullable_any_of(nested)


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or Settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        await ArtifactStore(resolved.artifact_root).reconcile_temporary()
        executor = AnalysisExecutor()
        application.state.analysis_executor = executor
        await executor.recover_abandoned_runs(RunRepository(application.state.session_factory))
        await executor.start()
        try:
            yield
        finally:
            await executor.stop()
            await application.state.database_engine.dispose()

    application = FastAPI(title="ADR Forge Local API", version="0.1.0", lifespan=lifespan)
    application.state.settings = resolved
    application.state.database_engine = create_database_engine(resolved.database_url)
    application.state.session_factory = create_session_factory(application.state.database_engine)
    application.state.resources = HostResourceProbe()
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[f"http://{resolved.web_host}:{resolved.web_port}"],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-Request-ID"],
    )

    @application.middleware("http")
    async def request_id(request: Request, call_next: RequestResponseEndpoint) -> Response:
        request.state.request_id = request.headers.get("X-Request-ID") or str(uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    install_problem_details_handlers(application)
    application.include_router(system_router)
    application.include_router(analysis_router)
    application.include_router(retrieval_router)
    application.include_router(strategies_router)
    application.include_router(comparisons_router)
    application.include_router(experiments_router)

    original_openapi = application.openapi

    def phase_three_openapi() -> dict[str, object]:
        document = original_openapi()
        _remove_generated_schema_titles(document)
        _canonicalize_nullable_any_of(document)
        all_components = document.setdefault("components", {})
        components = all_components.setdefault("schemas", {})
        all_components["parameters"] = {
            "RunId": {
                "name": "runId",
                "in": "path",
                "required": True,
                "schema": {"type": "string", "format": "uuid"},
            },
            "ScenarioId": {
                "name": "scenarioId",
                "in": "path",
                "required": True,
                "schema": {"type": "string", "format": "uuid"},
            },
            "ComparisonId": {
                "name": "comparisonId",
                "in": "path",
                "required": True,
                "schema": {"type": "string", "format": "uuid"},
            },
            "ExperimentId": {
                "name": "experimentId",
                "in": "path",
                "required": True,
                "schema": {"type": "string", "format": "uuid"},
            },
        }
        all_components["responses"] = {
            "ProblemResponse": {
                "description": "Problem Details error response.",
                "content": {
                    "application/problem+json": {"schema": {"$ref": "#/components/schemas/Problem"}}
                },
            }
        }
        problem_schema = components.get("Problem")
        if isinstance(problem_schema, dict):
            properties = problem_schema.get("properties", {})
            if isinstance(properties, dict):
                properties.setdefault("title", {"type": "string"})
        components.setdefault("ProgressEvent", ProgressEvent.model_json_schema())
        scenario_request = components.get("CreateScenarioRequest")
        if isinstance(scenario_request, dict):
            language = scenario_request.get("properties", {}).get("language")
            if isinstance(language, dict):
                language.pop("title", None)
        analysis_run = components.get("AnalysisRun")
        if isinstance(analysis_run, dict):
            status = analysis_run.get("properties", {}).get("status")
            if isinstance(status, dict):
                status["enum"] = [
                    "pending",
                    "waiting_resources",
                    "running",
                    "completed",
                    "needs_clarification",
                    "invalid_output",
                    "failed",
                    "cancelled",
                    "interrupted",
                ]
        progress = components.get("ProgressEvent")
        if isinstance(progress, dict):
            sequence = progress.get("properties", {}).get("progress_sequence")
            if isinstance(sequence, dict):
                sequence.pop("title", None)
        for path in document.get("paths", {}).values():
            for operation in path.values():
                if not isinstance(operation, dict):
                    continue
                operation.pop("tags", None)
                parameters = operation.get("parameters", [])
                if isinstance(parameters, list) and parameters:
                    operation["parameters"] = [
                        {"$ref": f"#/components/parameters/{name[:-2].title()}Id"}
                        if isinstance(parameter, dict)
                        and parameter.get("in") == "path"
                        and (name := parameter.get("name"))
                        in {
                            "runId",
                            "scenarioId",
                            "comparisonId",
                            "experimentId",
                        }
                        else parameter
                        for parameter in parameters
                    ]
                # FastAPI's synthesized list-response title is documentation
                # metadata and is absent from the versioned wire contract.
                successful = operation.get("responses", {}).get("200")
                if isinstance(successful, dict):
                    schema = successful.get("content", {}).get("application/json", {}).get("schema")
                    if isinstance(schema, dict) and schema.get("type") == "array":
                        schema.pop("title", None)
                for response in operation.get("responses", {}).values():
                    content = response.get("content", {})
                    if (
                        "application/json" in content
                        and "$ref" in content["application/json"].get("schema", {})
                        and content["application/json"]["schema"]["$ref"].endswith("/Problem")
                    ):
                        content["application/problem+json"] = content.pop("application/json")
        _canonicalize_nullable_any_of(document)
        return document

    application.openapi = phase_three_openapi  # type: ignore[method-assign]
    return application


app = create_app()

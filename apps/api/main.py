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
from adr_forge.api.routes.retrieval import router as retrieval_router
from adr_forge.api.routes.strategies import router as strategies_router
from adr_forge.api.routes.system import router as system_router
from adr_forge.artifacts.store import ArtifactStore
from adr_forge.persistence.database import create_database_engine, create_session_factory
from adr_forge.shared.config import Settings
from adr_forge.system.resources import HostResourceProbe


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or Settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        await ArtifactStore(resolved.artifact_root).reconcile_temporary()
        try:
            yield
        finally:
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

    original_openapi = application.openapi

    def phase_three_openapi() -> dict[str, object]:
        document = original_openapi()
        components = document.setdefault("components", {}).setdefault("schemas", {})
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
                for response in operation.get("responses", {}).values():
                    content = response.get("content", {})
                    if (
                        "application/json" in content
                        and "$ref" in content["application/json"].get("schema", {})
                        and content["application/json"]["schema"]["$ref"].endswith("/Problem")
                    ):
                        content["application/problem+json"] = content.pop("application/json")
        return document

    application.openapi = phase_three_openapi  # type: ignore[method-assign]
    return application


app = create_app()

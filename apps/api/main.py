"""ADR Forge's local-only FastAPI composition root."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import RequestResponseEndpoint

from adr_forge.api.problem_details import install_problem_details_handlers
from adr_forge.api.routes.system import router as system_router
from adr_forge.artifacts.store import ArtifactStore
from adr_forge.shared.config import Settings
from adr_forge.system.resources import HostResourceProbe


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or Settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        await ArtifactStore(resolved.artifact_root).reconcile_temporary()
        yield

    application = FastAPI(title="ADR Forge Local API", version="0.1.0", lifespan=lifespan)
    application.state.settings = resolved
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
    return application


app = create_app()

"""RFC 9457 problem-details response mapping."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from adr_forge.shared.errors import DomainError, ErrorCode

PROBLEM_MEDIA_TYPE = "application/problem+json"
PROBLEM_TYPE_BASE = "https://adr-forge.local/problems/"


class ProblemDetails(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    title: str
    status: int
    detail: str | None = None
    code: ErrorCode | str | None = None
    request_id: str | None = Field(default=None, serialization_alias="request_id")


def problem_from_error(error: DomainError, *, request_id: str | None = None) -> ProblemDetails:
    return ProblemDetails(
        type=f"{PROBLEM_TYPE_BASE}{error.code}",
        title=error.title,
        status=error.status,
        detail=error.detail,
        code=error.code,
        request_id=request_id,
    )


def problem_response(problem: ProblemDetails) -> JSONResponse:
    return JSONResponse(
        status_code=problem.status,
        content=problem.model_dump(mode="json", exclude_none=True, by_alias=True),
        media_type=PROBLEM_MEDIA_TYPE,
    )


async def domain_error_handler(request: Request, error: DomainError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID")
    return problem_response(problem_from_error(error, request_id=request_id))


def install_problem_details_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, domain_error_handler)  # type: ignore[arg-type]

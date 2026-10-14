"""Read-only-safe HTTP projections for benchmark experiments."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request

from adr_forge.experiments.reporting import aggregate_report
from adr_forge.experiments.repository import ExperimentRepository
from adr_forge.shared.errors import NotFoundError

router = APIRouter(prefix="/api/v1")


def _repository(request: Request) -> ExperimentRepository:
    return ExperimentRepository(request.app.state.session_factory)


@router.get("/experiments/{experiment_id}")
async def get_experiment(experiment_id: UUID, request: Request) -> dict[str, object]:
    experiment = await _repository(request).get(experiment_id)
    if experiment is None:
        raise NotFoundError("Experiment not found.")
    return experiment.model_dump(mode="json")


@router.get("/experiments/{experiment_id}/runs")
async def get_experiment_runs(experiment_id: UUID, request: Request) -> dict[str, object]:
    experiment = await _repository(request).get(experiment_id)
    if experiment is None:
        raise NotFoundError("Experiment not found.")
    return {
        "expected_run_count": experiment.run_count,
        "cells": [cell.model_dump(mode="json") for cell in experiment.matrix],
    }


@router.get("/experiments/{experiment_id}/report")
async def get_experiment_report(experiment_id: UUID, request: Request) -> dict[str, object]:
    experiment = await _repository(request).get(experiment_id)
    if experiment is None:
        raise NotFoundError("Experiment not found.")
    return aggregate_report(experiment, {})

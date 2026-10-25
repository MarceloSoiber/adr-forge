"""Read-only discovery for the configured governed dataset."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Request

from adr_forge.datasets.summary import (
    DatasetRecordPage,
    DatasetSummary,
    read_dataset_records,
    read_dataset_summary,
)

router = APIRouter(prefix="/api/v1")


@router.get("/datasets/current", operation_id="getCurrentDataset", response_model=DatasetSummary)
async def get_current_dataset(request: Request) -> DatasetSummary:
    settings = request.app.state.settings
    return read_dataset_summary(settings.dataset_manifest_path, settings.dataset_training_path)


@router.get(
    "/datasets/current/records",
    operation_id="listCurrentDatasetRecords",
    response_model=DatasetRecordPage,
)
async def list_current_dataset_records(
    request: Request,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=50)] = 12,
) -> DatasetRecordPage:
    settings = request.app.state.settings
    return read_dataset_records(settings.dataset_training_path, offset=offset, limit=limit)

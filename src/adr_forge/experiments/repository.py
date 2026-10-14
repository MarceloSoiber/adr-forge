"""SQLite persistence for frozen benchmark experiments."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from adr_forge.evaluation.models import RubricVersion
from adr_forge.experiments.models import Experiment


class ExperimentRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def add(self, experiment: Experiment) -> None:
        payload = experiment.model_dump(mode="json")
        payload["matrix_json"] = json.dumps(payload.pop("matrix"), ensure_ascii=False)
        payload.pop("expected_run_count", None)
        payload.pop("outcomes", None)
        async with self._session_factory.begin() as session:
            await session.execute(
                text("""INSERT INTO experiments
                (id, name, status, dataset_version_id, rubric_version_id, code_revision,
                 configuration_artifact_id, matrix_json, created_at, started_at, finished_at)
                VALUES (:id, :name, :status, :dataset_version_id, :rubric_version_id,
                 :code_revision, :configuration_artifact_id, :matrix_json, :created_at,
                 :started_at, :finished_at)"""),
                payload,
            )

    async def add_rubric(self, rubric: RubricVersion) -> None:
        payload = rubric.model_dump(mode="json")
        payload["dimensions_json"] = json.dumps(payload.pop("dimensions"), ensure_ascii=False)
        async with self._session_factory.begin() as session:
            await session.execute(
                text("""INSERT INTO rubric_versions
                (id,name,version,content_hash,dimensions_json,published_at)
                VALUES (:id,:name,:version,:content_hash,:dimensions_json,:published_at)"""),
                payload,
            )

    async def get_rubric(self, identity: UUID) -> RubricVersion | None:
        async with self._session_factory() as session:
            row = (
                (
                    await session.execute(
                        text("SELECT * FROM rubric_versions WHERE id=:id"), {"id": str(identity)}
                    )
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            return None
        value = dict(row)
        value["dimensions"] = json.loads(value.pop("dimensions_json"))
        return RubricVersion.model_validate(value)

    async def get(self, identity: UUID) -> Experiment | None:
        async with self._session_factory() as session:
            row = (
                (
                    await session.execute(
                        text("SELECT * FROM experiments WHERE id=:id"), {"id": str(identity)}
                    )
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            return None
        value: dict[str, Any] = dict(row)
        value["matrix"] = json.loads(value.pop("matrix_json"))
        value["expected_run_count"] = len(value["matrix"])
        return Experiment.model_validate(value)

    async def update_status(self, experiment: Experiment) -> None:
        async with self._session_factory.begin() as session:
            await session.execute(
                text(
                    "UPDATE experiments SET status=:status, started_at=:started_at, "
                    "finished_at=:finished_at WHERE id=:id"
                ),
                experiment.model_dump(
                    mode="json", include={"id", "status", "started_at", "finished_at"}
                ),
            )

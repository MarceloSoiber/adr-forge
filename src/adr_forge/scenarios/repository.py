"""SQLite repository for immutable scenario snapshots."""

from __future__ import annotations

import json

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from adr_forge.scenarios.models import DecisionCategory, DecisionScenario, ScenarioRevision
from adr_forge.shared.errors import ConflictError


class ScenarioRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create_first(self, scenario: DecisionScenario, revision: ScenarioRevision) -> None:
        if revision.scenario_id != scenario.id or revision.revision_number != 1:
            raise ValueError("first revision must belong to its scenario and be numbered one")
        try:
            async with self._session_factory.begin() as session:
                await session.execute(
                    text(
                        """INSERT INTO decision_scenarios
                        (id, title, language, current_revision_number, created_at, updated_at)
                        VALUES (:id, :title, :language, :current_revision_number,
                        :created_at, :updated_at)"""
                    ),
                    scenario.model_dump(mode="json"),
                )
                await self._insert_revision(session, revision)
        except IntegrityError as error:
            raise ConflictError(
                "Scenario revision already exists or duplicates its content."
            ) from error

    async def get(self, scenario_id: str) -> tuple[DecisionScenario, ScenarioRevision] | None:
        async with self._session_factory() as session:
            row = (
                (
                    await session.execute(
                        text(
                            """SELECT s.id AS scenario_id, s.title, s.language,
                        s.current_revision_number,
                        s.created_at AS scenario_created_at, s.updated_at,
                        r.id AS revision_id, r.revision_number, r.problem, r.facts_json,
                        r.constraints_json, r.desired_qualities_json,
                        r.candidate_alternatives_json, r.clarification_answers_json,
                        r.categories_json, r.created_at AS revision_created_at
                        FROM decision_scenarios s JOIN scenario_revisions r
                        ON r.scenario_id = s.id AND r.revision_number = s.current_revision_number
                        WHERE s.id = :scenario_id"""
                        ),
                        {"scenario_id": scenario_id},
                    )
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            return None
        scenario = DecisionScenario(
            id=row["scenario_id"],
            title=row["title"],
            language=row["language"],
            current_revision_number=row["current_revision_number"],
            created_at=row["scenario_created_at"],
            updated_at=row["updated_at"],
        )
        revision = ScenarioRevision(
            id=row["revision_id"],
            scenario_id=row["scenario_id"],
            revision_number=row["revision_number"],
            problem=row["problem"],
            facts=json.loads(row["facts_json"]),
            constraints=json.loads(row["constraints_json"]),
            desired_qualities=json.loads(row["desired_qualities_json"]),
            candidate_alternatives=json.loads(row["candidate_alternatives_json"]),
            clarification_answers=json.loads(row["clarification_answers_json"]),
            categories=[
                DecisionCategory(category) for category in json.loads(row["categories_json"])
            ],
            created_at=row["revision_created_at"],
        )
        return scenario, revision

    async def get_revision(self, revision_id: str) -> ScenarioRevision | None:
        """Retrieve an immutable revision by id for starting an analysis run."""
        async with self._session_factory() as session:
            row = (
                (
                    await session.execute(
                        text(
                            """SELECT id, scenario_id, revision_number, problem, facts_json,
                        constraints_json, desired_qualities_json, candidate_alternatives_json,
                        clarification_answers_json, categories_json, created_at
                        FROM scenario_revisions WHERE id = :revision_id"""
                        ),
                        {"revision_id": revision_id},
                    )
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            return None
        return ScenarioRevision(
            id=row["id"],
            scenario_id=row["scenario_id"],
            revision_number=row["revision_number"],
            problem=row["problem"],
            facts=json.loads(row["facts_json"]),
            constraints=json.loads(row["constraints_json"]),
            desired_qualities=json.loads(row["desired_qualities_json"]),
            candidate_alternatives=json.loads(row["candidate_alternatives_json"]),
            clarification_answers=json.loads(row["clarification_answers_json"]),
            categories=[
                DecisionCategory(category) for category in json.loads(row["categories_json"])
            ],
            created_at=row["created_at"],
        )

    async def append_revision(
        self, scenario: DecisionScenario, base: ScenarioRevision, revision: ScenarioRevision
    ) -> bool:
        """Advance the scenario head and add a revision with a single CAS transaction."""
        if (
            revision.scenario_id != scenario.id
            or revision.revision_number != base.revision_number + 1
        ):
            raise ValueError("revision must immediately follow the supplied scenario base")
        try:
            async with self._session_factory.begin() as session:
                result = await session.execute(
                    text(
                        """UPDATE decision_scenarios SET current_revision_number = :next_revision,
                        updated_at = :updated_at WHERE id = :scenario_id
                        AND current_revision_number = :base_revision"""
                    ),
                    {
                        "scenario_id": str(scenario.id),
                        "base_revision": base.revision_number,
                        "next_revision": revision.revision_number,
                        "updated_at": revision.created_at,
                    },
                )
                if result.rowcount != 1:
                    return False
                await self._insert_revision(session, revision)
        except IntegrityError as error:
            raise ConflictError("Clarification answers duplicate an existing revision.") from error
        return True

    async def _insert_revision(self, session: AsyncSession, revision: ScenarioRevision) -> None:
        payload = revision.model_dump(mode="json")
        payload.update(
            {
                "facts_json": json.dumps(payload.pop("facts"), ensure_ascii=False),
                "constraints_json": json.dumps(payload.pop("constraints"), ensure_ascii=False),
                "desired_qualities_json": json.dumps(
                    payload.pop("desired_qualities"), ensure_ascii=False
                ),
                "candidate_alternatives_json": json.dumps(
                    payload.pop("candidate_alternatives"), ensure_ascii=False
                ),
                "clarification_answers_json": json.dumps(
                    payload.pop("clarification_answers"), ensure_ascii=False
                ),
                "categories_json": json.dumps(payload.pop("categories"), ensure_ascii=False),
            }
        )
        payload.pop("content_hash")
        payload["content_hash"] = revision.content_hash
        await session.execute(
            text(
                """INSERT INTO scenario_revisions
                (id, scenario_id, revision_number, problem, facts_json, constraints_json,
                desired_qualities_json, candidate_alternatives_json, clarification_answers_json,
                categories_json, content_hash, created_at)
                VALUES (:id, :scenario_id, :revision_number, :problem, :facts_json,
                :constraints_json,
                :desired_qualities_json, :candidate_alternatives_json, :clarification_answers_json,
                :categories_json, :content_hash, :created_at)"""
            ),
            payload,
        )

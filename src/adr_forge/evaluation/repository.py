"""Persistence boundary for the blind-comparison aggregate."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class EvaluationRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None: self._session_factory = session_factory
    async def save_comparison(self, comparison: dict[str, Any]) -> None:
        async with self._session_factory.begin() as session:
            await session.execute(text("INSERT INTO blind_comparisons (id, rubric_version_id, rubric_json, current_evaluation_id, created_at) VALUES (:id,:rubric_version_id,:rubric_json,NULL,:created_at)"), {**comparison, "rubric_json": json.dumps(comparison["rubric"], default=str)})
            for candidate in comparison["candidates"]:
                await session.execute(text("INSERT INTO comparison_candidates (comparison_id,label,run_id,adr_json,strategy_id,strategy_version,generation_config_hash,retrieval_snapshot_id) VALUES (:comparison_id,:label,:run_id,:adr_json,:strategy_id,:strategy_version,:generation_config_hash,:retrieval_snapshot_id)"), {"comparison_id": comparison["id"], **candidate, "adr_json": json.dumps(candidate["adr"], default=str)})

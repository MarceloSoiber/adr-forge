"""The comparison repository retains blinding and immutable evaluation history."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config

from adr_forge.evaluation.models import CandidateRun, RubricDimension, RubricVersion
from adr_forge.evaluation.repository import EvaluationRepository
from adr_forge.evaluation.service import BlindComparisonService, EvaluationConflict
from adr_forge.persistence.database import create_database_engine, create_session_factory


@pytest.fixture
def migrated_database(tmp_path: Path) -> Path:
    database_path = tmp_path / "evaluations.sqlite3"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{database_path}")
    command.upgrade(config, "head")
    return database_path


def _comparison():
    revision = uuid4()
    rubric = RubricVersion(name="quality", version="1", dimensions=[
        RubricDimension(key="quality", description="Quality", minimum=1, maximum=5, anchors={"1": "low", "5": "high"})
    ])
    candidates = [CandidateRun(
        run_id=uuid4(), scenario_revision_id=revision, status="completed", adr={"title": f"ADR {index}"},
        strategy_id=f"strategy-{index}", strategy_version="1", generation_config_hash="a" * 64,
    ) for index in range(2)]
    return BlindComparisonService().create(candidates=candidates, rubric=rubric)


@pytest.mark.asyncio
async def test_persists_blinded_comparison_and_append_only_evaluations(migrated_database: Path) -> None:
    engine = create_database_engine(f"sqlite+aiosqlite:///{migrated_database}")
    repository = EvaluationRepository(create_session_factory(engine))
    try:
        created = _comparison()
        await repository.save_comparison(created)
        restored = await repository.get_comparison(created.id)
        assert restored is not None
        blinded = restored.blinded()
        assert {candidate.label for candidate in blinded.candidates} == {"A", "B"}
        assert all("strategy_id" not in candidate.model_dump() for candidate in blinded.candidates)

        scores = {candidate.label: {"quality": 4} for candidate in blinded.candidates}
        first = restored.submit(evaluator_id="reviewer", evaluator_type="human", scores=scores, preference="A", notes="first")
        await repository.append_evaluation(first)

        persisted = await repository.get_comparison(created.id)
        assert persisted is not None
        assert persisted.reveal().evaluation_id == first.id
        assert persisted.history()[0].notes == "first"
        correction = persisted.submit(evaluator_id="reviewer", evaluator_type="human", scores=scores, preference="tie", supersedes_evaluation_id=first.id)
        await repository.append_evaluation(correction)
        assert [result.id for result in (await repository.get_comparison(created.id)).history()] == [first.id, correction.id]  # type: ignore[union-attr]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_rejects_second_writer_using_a_stale_comparison_head(migrated_database: Path) -> None:
    engine = create_database_engine(f"sqlite+aiosqlite:///{migrated_database}")
    repository = EvaluationRepository(create_session_factory(engine))
    try:
        created = _comparison()
        await repository.save_comparison(created)
        first_reader = await repository.get_comparison(created.id)
        stale_reader = await repository.get_comparison(created.id)
        assert first_reader and stale_reader
        scores = {candidate.label: {"quality": 4} for candidate in first_reader.blinded().candidates}
        await repository.append_evaluation(first_reader.submit(evaluator_id="one", evaluator_type="human", scores=scores, preference="A"))
        with pytest.raises(EvaluationConflict, match="stale"):
            await repository.append_evaluation(stale_reader.submit(evaluator_id="two", evaluator_type="human", scores=scores, preference="A"))
    finally:
        await engine.dispose()

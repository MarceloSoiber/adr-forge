"""Persist immutable provenance for analysis runs.

Revision ID: 0011_run_provenance
Revises: 0010_artifact_prune_audit
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0011_run_provenance"
down_revision = "0010_artifact_prune_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("analysis_runs") as batch:
        batch.add_column(sa.Column("retrieval_snapshot_id", sa.String(36)))
        batch.add_column(sa.Column("experiment_id", sa.String(36)))
        batch.add_column(sa.Column("scenario_content_hash", sa.String(64), nullable=True))
        batch.add_column(sa.Column("strategy_configuration_hash", sa.String(64), nullable=True))
        batch.add_column(sa.Column("generation_config_hash", sa.String(64), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("analysis_runs") as batch:
        batch.drop_column("generation_config_hash")
        batch.drop_column("strategy_configuration_hash")
        batch.drop_column("scenario_content_hash")
        batch.drop_column("experiment_id")
        batch.drop_column("retrieval_snapshot_id")

"""Create immutable rubric and benchmark experiment tables.

Revision ID: 0009_experiments
Revises: 0008_blind_evaluation
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0009_experiments"
down_revision = "0008_blind_evaluation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("rubric_versions", sa.Column("id", sa.String(36), primary_key=True), sa.Column("name", sa.String(200), nullable=False), sa.Column("version", sa.String(100), nullable=False), sa.Column("content_hash", sa.String(64), nullable=False, unique=True), sa.Column("dimensions_json", sa.Text(), nullable=False), sa.Column("published_at", sa.DateTime(timezone=True)))
    op.create_index("uq_rubric_name_version", "rubric_versions", ["name", "version"], unique=True)
    op.create_table("experiments", sa.Column("id", sa.String(36), primary_key=True), sa.Column("name", sa.String(200), nullable=False), sa.Column("status", sa.String(16), nullable=False), sa.Column("dataset_version_id", sa.String(36)), sa.Column("rubric_version_id", sa.String(36), sa.ForeignKey("rubric_versions.id"), nullable=False), sa.Column("code_revision", sa.String(200), nullable=False), sa.Column("configuration_artifact_id", sa.String(36)), sa.Column("matrix_json", sa.Text(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("started_at", sa.DateTime(timezone=True)), sa.Column("finished_at", sa.DateTime(timezone=True)))
    op.create_index("ix_experiments_status_created", "experiments", ["status", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_experiments_status_created", table_name="experiments")
    op.drop_table("experiments")
    op.drop_index("uq_rubric_name_version", table_name="rubric_versions")
    op.drop_table("rubric_versions")

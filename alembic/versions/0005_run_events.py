"""Add durable progress events and validation-attempt records.

Revision ID: 0005_run_events
Revises: 0004_analysis_runs
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005_run_events"
down_revision = "0004_analysis_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analysis_run_events",
        sa.Column("run_id", sa.String(36), sa.ForeignKey("analysis_runs.id"), primary_key=True),
        sa.Column("progress_sequence", sa.Integer(), primary_key=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("stage", sa.String(200), nullable=False),
        sa.Column("progress_percent", sa.Integer()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("progress_sequence >= 0", name="ck_run_event_sequence"),
        sa.CheckConstraint(
            "progress_percent IS NULL OR progress_percent BETWEEN 0 AND 100",
            name="ck_run_event_progress",
        ),
    )
    op.create_table(
        "analysis_run_validation_attempts",
        sa.Column("run_id", sa.String(36), sa.ForeignKey("analysis_runs.id"), primary_key=True),
        sa.Column("attempt", sa.String(16), primary_key=True),
        sa.Column("artifact_id", sa.String(36), nullable=False),
        sa.Column("parse_succeeded", sa.Boolean(), nullable=False),
        sa.Column("findings_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("attempt IN ('original', 'repaired')", name="ck_run_validation_attempt"),
    )


def downgrade() -> None:
    op.drop_table("analysis_run_validation_attempts")
    op.drop_table("analysis_run_events")

"""Create persisted analysis runs and validated ADR drafts.

Revision ID: 0004_analysis_runs
Revises: 0003_scenarios
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_analysis_runs"
down_revision = "0003_scenarios"
branch_labels = None
depends_on = None

_STATUSES = (
    "'pending','waiting_resources','running','completed','needs_clarification',"
    "'invalid_output','failed','cancelled','interrupted'"
)


def upgrade() -> None:
    op.create_table(
        "analysis_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "scenario_revision_id",
            sa.String(36),
            sa.ForeignKey("scenario_revisions.id"),
            nullable=False,
        ),
        sa.Column("strategy_id", sa.String(80), nullable=False),
        sa.Column("strategy_version", sa.String(80), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("stage", sa.String(200), nullable=False),
        sa.Column("progress_percent", sa.Integer()),
        sa.Column("progress_sequence", sa.Integer(), nullable=False),
        sa.Column("validation_attempts_json", sa.Text(), nullable=False),
        sa.Column("raw_output_artifact_id", sa.String(36)),
        sa.Column("repaired_output_artifact_id", sa.String(36)),
        sa.Column("adr_draft_id", sa.String(36)),
        sa.Column("failure_code", sa.String(120)),
        sa.Column("failure_detail", sa.String(2000)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(f"status IN ({_STATUSES})", name="ck_analysis_run_status"),
        sa.CheckConstraint("progress_sequence >= 0", name="ck_analysis_run_sequence"),
        sa.CheckConstraint(
            "progress_percent IS NULL OR progress_percent BETWEEN 0 AND 100",
            name="ck_analysis_run_progress",
        ),
    )
    op.create_index("ix_analysis_runs_status", "analysis_runs", ["status"])
    op.create_table(
        "adr_drafts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "analysis_run_id",
            sa.String(36),
            sa.ForeignKey("analysis_runs.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("adr_drafts")
    op.drop_index("ix_analysis_runs_status", table_name="analysis_runs")
    op.drop_table("analysis_runs")

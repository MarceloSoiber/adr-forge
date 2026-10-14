"""Persist blind comparisons and append-only evaluations.

Revision ID: 0008_blind_evaluation
Revises: 0007_retrieval_snapshots
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008_blind_evaluation"
down_revision = "0007_retrieval_snapshots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "blind_comparisons",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("rubric_version_id", sa.String(36), nullable=False),
        sa.Column("rubric_json", sa.Text(), nullable=False),
        sa.Column("current_evaluation_id", sa.String(36)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "comparison_candidates",
        sa.Column(
            "comparison_id", sa.String(36), sa.ForeignKey("blind_comparisons.id"), primary_key=True
        ),
        sa.Column("label", sa.String(8), primary_key=True),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("adr_json", sa.Text(), nullable=False),
        sa.Column("strategy_id", sa.String(80), nullable=False),
        sa.Column("strategy_version", sa.String(80), nullable=False),
        sa.Column("generation_config_hash", sa.String(64), nullable=False),
        sa.Column("retrieval_snapshot_id", sa.String(36)),
        sa.UniqueConstraint("comparison_id", "run_id", name="uq_comparison_candidate_run"),
    )
    op.create_table(
        "evaluation_results",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "comparison_id", sa.String(36), sa.ForeignKey("blind_comparisons.id"), nullable=False
        ),
        sa.Column("rubric_version_id", sa.String(36), nullable=False),
        sa.Column("evaluator_id", sa.String(200), nullable=False),
        sa.Column("evaluator_type", sa.String(32), nullable=False),
        sa.Column("scores_json", sa.Text(), nullable=False),
        sa.Column("preference", sa.String(8), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("supersedes_evaluation_id", sa.String(36), unique=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_evaluation_results_comparison_submitted",
        "evaluation_results",
        ["comparison_id", "submitted_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_evaluation_results_comparison_submitted", table_name="evaluation_results")
    op.drop_table("evaluation_results")
    op.drop_table("comparison_candidates")
    op.drop_table("blind_comparisons")

"""Persist immutable retrieval snapshots.

Revision ID: 0007_retrieval_snapshots
Revises: 0006_run_telemetry
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007_retrieval_snapshots"
down_revision = "0006_run_telemetry"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "retrieval_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("schema_version", sa.String(64), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("provider_version", sa.String(200), nullable=False),
        sa.Column("embedding_model", sa.String(200), nullable=False),
        sa.Column("embedding_version", sa.String(200), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("filters_json", sa.Text(), nullable=False),
        sa.Column("chunks_json", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("artifact_id", sa.String(36), sa.ForeignKey("artifacts.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("length(query) > 0", name="ck_retrieval_snapshot_query"),
    )
    op.create_index(
        "ix_retrieval_snapshots_provider_created", "retrieval_snapshots", ["provider", "created_at"]
    )
    op.create_index("ix_retrieval_snapshots_artifact", "retrieval_snapshots", ["artifact_id"])


def downgrade() -> None:
    op.drop_index("ix_retrieval_snapshots_artifact", table_name="retrieval_snapshots")
    op.drop_index("ix_retrieval_snapshots_provider_created", table_name="retrieval_snapshots")
    op.drop_table("retrieval_snapshots")

"""Record successful artifact-prune operations.

Revision ID: 0010_artifact_prune_audit
Revises: 0009_experiments
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0010_artifact_prune_audit"
down_revision = "0009_experiments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "artifact_prune_audits",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("operation_id", sa.String(36), nullable=False),
        sa.Column("artifact_id", sa.String(36), nullable=False),
        sa.Column("artifact_kind", sa.String(32), nullable=False),
        sa.Column("relative_path", sa.String(1024), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("reason", sa.String(32), nullable=False),
        sa.Column("reclaimed_bytes", sa.BigInteger(), nullable=False),
        sa.Column("pruned_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("reclaimed_bytes >= 0", name="ck_prune_audit_reclaimed_bytes"),
        sa.CheckConstraint(
            "reason IN ('unreferenced_prunable', 'expired_temporary', 'missing_bytes')",
            name="ck_prune_audit_reason",
        ),
    )
    op.create_index(
        "ix_prune_audit_operation_pruned",
        "artifact_prune_audits",
        ["operation_id", "pruned_at"],
    )
    op.create_index("ix_prune_audit_artifact", "artifact_prune_audits", ["artifact_id"])


def downgrade() -> None:
    op.drop_index("ix_prune_audit_artifact", table_name="artifact_prune_audits")
    op.drop_index("ix_prune_audit_operation_pruned", table_name="artifact_prune_audits")
    op.drop_table("artifact_prune_audits")

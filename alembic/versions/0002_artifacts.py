"""Create artifact catalog and reference registry.

Revision ID: 0002_artifacts
Revises: 0001_schema_version
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_artifacts"
down_revision = "0001_schema_version"
branch_labels = None
depends_on = None

_KINDS = "'raw_output','retrieval_snapshot','model','adapter','checkpoint','report','config','log'"
_RETENTION = "'keep','prunable','temporary'"


def upgrade() -> None:
    op.create_table(
        "artifacts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("relative_path", sa.String(1024), nullable=False, unique=True),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("media_type", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("retention", sa.String(16), nullable=False),
        sa.CheckConstraint(f"kind IN ({_KINDS})", name="ck_artifact_kind"),
        sa.CheckConstraint(
            "length(sha256) = 64 AND sha256 NOT GLOB '*[^0-9a-f]*'", name="ck_artifact_sha"
        ),
        sa.CheckConstraint("size_bytes >= 0", name="ck_artifact_size"),
        sa.CheckConstraint(
            "relative_path NOT LIKE '/%' AND relative_path NOT LIKE '%..%'",
            name="ck_artifact_path",
        ),
        sa.CheckConstraint(f"retention IN ({_RETENTION})", name="ck_artifact_retention"),
        sa.UniqueConstraint("sha256", "kind", name="uq_artifact_sha_kind"),
    )
    op.create_index("ix_artifacts_retention", "artifacts", ["retention"])
    op.create_table(
        "artifact_references",
        sa.Column(
            "artifact_id",
            sa.String(36),
            sa.ForeignKey("artifacts.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("owner_type", sa.String(80), primary_key=True),
        sa.Column("owner_id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("owner_type <> ''", name="ck_artifact_reference_owner_type"),
    )
    op.create_index(
        "ix_artifact_references_artifact_owner",
        "artifact_references",
        ["artifact_id", "owner_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_artifact_references_artifact_owner", table_name="artifact_references")
    op.drop_table("artifact_references")
    op.drop_index("ix_artifacts_retention", table_name="artifacts")
    op.drop_table("artifacts")

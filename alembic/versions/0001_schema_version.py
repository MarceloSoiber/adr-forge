"""Establish Alembic as the sole schema-version authority.

Revision ID: 0001_schema_version
Revises:
Create Date: 2026-10-12
"""

from __future__ import annotations

from alembic import op

revision = "0001_schema_version"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create Alembic's version table through its migration context."""

    op.execute("SELECT 1")


def downgrade() -> None:
    """Leave version-table lifecycle to Alembic when downgrading the base revision."""

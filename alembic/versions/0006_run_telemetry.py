"""Add execution telemetry to persisted analysis runs.

Revision ID: 0006_run_telemetry
Revises: 0005_run_events
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_run_telemetry"
down_revision = "0005_run_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("analysis_runs") as batch:
        for name in ("input_tokens", "output_tokens", "latency_ms", "peak_vram_mb"):
            batch.add_column(sa.Column(name, sa.Integer()))
            batch.create_check_constraint(
                f"ck_analysis_run_{name}", f"{name} IS NULL OR {name} >= 0"
            )


def downgrade() -> None:
    with op.batch_alter_table("analysis_runs") as batch:
        for name in ("input_tokens", "output_tokens", "latency_ms", "peak_vram_mb"):
            batch.drop_constraint(f"ck_analysis_run_{name}", type_="check")
            batch.drop_column(name)

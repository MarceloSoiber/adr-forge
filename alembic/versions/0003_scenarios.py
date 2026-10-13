"""Create immutable scenario and revision metadata.

Revision ID: 0003_scenarios
Revises: 0002_artifacts
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_scenarios"
down_revision = "0002_artifacts"
branch_labels = None
depends_on = None

_CATEGORIES = (
    "'sql_vs_nosql','sync_vs_async','modular_monolith_vs_microservices',"
    "'containers_vs_serverless_vs_traditional','unsupported'"
)


def upgrade() -> None:
    op.create_table(
        "decision_scenarios",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("language", sa.String(10), nullable=False),
        sa.Column("current_revision_number", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("length(title) BETWEEN 3 AND 200", name="ck_scenario_title"),
        sa.CheckConstraint("language = 'pt-BR'", name="ck_scenario_language"),
        sa.CheckConstraint("current_revision_number >= 1", name="ck_scenario_current_revision"),
    )
    op.create_table(
        "scenario_revisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "scenario_id",
            sa.String(36),
            sa.ForeignKey("decision_scenarios.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("problem", sa.Text(), nullable=False),
        sa.Column("facts_json", sa.Text(), nullable=False),
        sa.Column("constraints_json", sa.Text(), nullable=False),
        sa.Column("desired_qualities_json", sa.Text(), nullable=False),
        sa.Column("candidate_alternatives_json", sa.Text(), nullable=False),
        sa.Column("clarification_answers_json", sa.Text(), nullable=False),
        sa.Column("categories_json", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("length(problem) BETWEEN 20 AND 20000", name="ck_revision_problem"),
        sa.CheckConstraint("revision_number >= 1", name="ck_revision_number"),
        sa.CheckConstraint(
            "length(content_hash) = 64 AND content_hash NOT GLOB '*[^0-9a-f]*'",
            name="ck_revision_content_hash",
        ),
        sa.UniqueConstraint("scenario_id", "revision_number", name="uq_scenario_revision_number"),
        sa.UniqueConstraint(
            "scenario_id", "content_hash", name="uq_scenario_revision_content_hash"
        ),
    )
    op.create_index(
        "ix_scenario_revisions_scenario_created",
        "scenario_revisions",
        ["scenario_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_scenario_revisions_scenario_created", table_name="scenario_revisions")
    op.drop_table("scenario_revisions")
    op.drop_table("decision_scenarios")

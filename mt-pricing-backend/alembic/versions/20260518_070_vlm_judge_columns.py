"""vlm_judge_columns — 7 columnas VLM en match_decisions (US-F15-02-02).

Revision ID: 070
Revises: 069
Create Date: 2026-05-18
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "070"
down_revision = "20260517_069"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "match_decisions",
        sa.Column("judge_verdict", sa.String(16), nullable=True),
    )
    op.add_column(
        "match_decisions",
        sa.Column("judge_confidence", sa.Numeric(4, 3), nullable=True),
    )
    op.add_column(
        "match_decisions",
        sa.Column("judge_rationale", sa.Text, nullable=True),
    )
    op.add_column(
        "match_decisions",
        sa.Column(
            "judge_image_regions",
            sa.dialects.postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "match_decisions",
        sa.Column(
            "deal_breakers_triggered",
            sa.ARRAY(sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "match_decisions",
        sa.Column("judge_model_version", sa.String(64), nullable=True),
    )
    op.add_column(
        "match_decisions",
        sa.Column("judge_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        "ck_match_decisions_judge_confidence_range",
        "match_decisions",
        "judge_confidence IS NULL OR (judge_confidence >= 0 AND judge_confidence <= 1)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_match_decisions_judge_confidence_range",
        "match_decisions",
        type_="check",
    )
    for col in (
        "judge_at",
        "judge_model_version",
        "deal_breakers_triggered",
        "judge_image_regions",
        "judge_rationale",
        "judge_confidence",
        "judge_verdict",
    ):
        op.drop_column("match_decisions", col)

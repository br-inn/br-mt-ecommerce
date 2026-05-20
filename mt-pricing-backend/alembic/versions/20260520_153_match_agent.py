"""match_agent_config + match_agent_decisions tables.

Creates two tables for the calibrated match-agent:

- ``match_agent_config`` — singleton (id=1) that controls agent mode
  ('shadow' | 'active'), conformal alpha, and minimum labels gate.
- ``match_agent_decisions`` — time-series log of every verdict emitted
  by the agent, with outcome tracking for human-review loop.

Revision ID: 20260520_153
Revises: 20260520_152
Create Date: 2026-05-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260520_153"
down_revision: str | None = "20260520_152"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # match_agent_config — singleton configuration row (id = 1)
    # ------------------------------------------------------------------
    op.create_table(
        "match_agent_config",
        sa.Column(
            "id",
            sa.SmallInteger(),
            primary_key=True,
        ),
        sa.Column(
            "mode",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'shadow'"),
        ),
        sa.Column(
            "alpha",
            sa.Numeric(4, 3),
            nullable=False,
            server_default=sa.text("0.02"),
        ),
        sa.Column(
            "min_labels_gate",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("200"),
        ),
        sa.Column(
            "updated_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("id = 1", name="ck_match_agent_config_singleton"),
        sa.CheckConstraint(
            "mode IN ('shadow','active')",
            name="ck_match_agent_config_mode",
        ),
        sa.CheckConstraint(
            "alpha > 0 AND alpha < 1",
            name="ck_match_agent_config_alpha",
        ),
        sa.CheckConstraint(
            "min_labels_gate >= 1",
            name="ck_match_agent_config_gate",
        ),
    )

    # Seed the singleton row
    op.execute(
        "INSERT INTO match_agent_config (id, mode, alpha, min_labels_gate) "
        "VALUES (1, 'shadow', 0.02, 200) ON CONFLICT (id) DO NOTHING;"
    )

    # ------------------------------------------------------------------
    # match_agent_decisions — time-series log of agent verdicts
    # ------------------------------------------------------------------
    op.create_table(
        "match_agent_decisions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "candidate_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("match_candidates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "product_sku",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "verdict",
            sa.String(length=16),
            nullable=False,
        ),
        sa.Column(
            "mode",
            sa.String(length=16),
            nullable=False,
        ),
        sa.Column(
            "applied",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "signal",
            sa.String(length=24),
            nullable=False,
        ),
        sa.Column(
            "score",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "calibrated_confidence",
            sa.Numeric(5, 4),
            nullable=True,
        ),
        sa.Column(
            "review_priority",
            sa.String(length=16),
            nullable=True,
        ),
        sa.Column(
            "calibrator_version",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "human_outcome",
            sa.String(length=16),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "verdict IN ('auto_validate','auto_discard','human')",
            name="ck_match_agent_decisions_verdict",
        ),
        sa.CheckConstraint(
            "mode IN ('shadow','active')",
            name="ck_match_agent_decisions_mode",
        ),
        sa.CheckConstraint(
            "signal IN ('conformal','bootstrap')",
            name="ck_match_agent_decisions_signal",
        ),
        sa.CheckConstraint(
            "human_outcome IS NULL OR human_outcome IN ('validated','discarded')",
            name="ck_match_agent_decisions_outcome",
        ),
    )

    op.create_index(
        "idx_match_agent_decisions_sku",
        "match_agent_decisions",
        ["product_sku"],
    )
    op.create_index(
        "idx_match_agent_decisions_created",
        "match_agent_decisions",
        ["created_at"],
    )
    op.create_index(
        "idx_match_agent_decisions_verdict_mode",
        "match_agent_decisions",
        ["verdict", "mode"],
    )
    op.create_index(
        "idx_match_agent_decisions_candidate",
        "match_agent_decisions",
        ["candidate_id"],
    )


def downgrade() -> None:
    # Drop decisions first (FK depends on match_candidates, not config)
    op.drop_index("idx_match_agent_decisions_candidate", table_name="match_agent_decisions")
    op.drop_index("idx_match_agent_decisions_verdict_mode", table_name="match_agent_decisions")
    op.drop_index("idx_match_agent_decisions_created", table_name="match_agent_decisions")
    op.drop_index("idx_match_agent_decisions_sku", table_name="match_agent_decisions")
    op.drop_table("match_agent_decisions")

    # Drop config last
    op.drop_table("match_agent_config")

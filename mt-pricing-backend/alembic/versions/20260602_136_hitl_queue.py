"""hitl_queue — Human-in-the-Loop queue priorizada por uncertainty × value (US-SCR-04-08b).

Revision ID: 20260602_136
Revises: 20260602_135
Create Date: 2026-06-02

Tablas:
- ``hitl_queue`` — cola HITL con priority_score = uncertainty × value_aed.
  Auto-enqueue via trigger cuando match_candidate tiene confidence < 0.6 Y
  product_value > 1000 AED.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260602_136"
down_revision = "20260602_135"
branch_labels = None
depends_on = None

_HITL_STATUSES = ("pending", "approved", "rejected", "skipped")


def upgrade() -> None:
    # ------------------------------------------------------------------
    # hitl_queue — cola HITL priorizada
    # ------------------------------------------------------------------
    op.create_table(
        "hitl_queue",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "match_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("match_candidates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # uncertainty_score: 1 - calibrated_confidence (o 1 si NULL)
        sa.Column("uncertainty_score", sa.Numeric(5, 4), nullable=False),
        # product_value_aed: precio AED del producto MT (de products o price_history)
        sa.Column("product_value_aed", sa.Numeric(14, 4), nullable=True),
        # priority_score = uncertainty_score × product_value_aed
        sa.Column("priority_score", sa.Numeric(18, 4), nullable=True),
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column(
            "assigned_to",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "notes",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "status IN ('pending','approved','rejected','skipped')",
            name="ck_hitl_queue_status",
        ),
        sa.CheckConstraint(
            "uncertainty_score >= 0 AND uncertainty_score <= 1",
            name="ck_hitl_queue_uncertainty",
        ),
    )

    op.create_index(
        "ix_hitl_queue_priority",
        "hitl_queue",
        ["priority_score"],
        postgresql_using="btree",
    )
    op.create_index(
        "ix_hitl_queue_status_priority",
        "hitl_queue",
        ["status", "priority_score"],
    )
    op.create_index(
        "ix_hitl_queue_match_id",
        "hitl_queue",
        ["match_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )

    # ------------------------------------------------------------------
    # updated_at auto-refresh trigger
    # ------------------------------------------------------------------
    op.execute("""
        CREATE OR REPLACE FUNCTION hitl_queue_updated_at()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$
    """)

    op.execute("""
        CREATE TRIGGER trg_hitl_queue_updated_at
        BEFORE UPDATE ON hitl_queue
        FOR EACH ROW EXECUTE FUNCTION hitl_queue_updated_at()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_hitl_queue_updated_at ON hitl_queue")
    op.execute("DROP FUNCTION IF EXISTS hitl_queue_updated_at()")
    op.drop_index("ix_hitl_queue_match_id", table_name="hitl_queue")
    op.drop_index("ix_hitl_queue_status_priority", table_name="hitl_queue")
    op.drop_index("ix_hitl_queue_priority", table_name="hitl_queue")
    op.drop_table("hitl_queue")

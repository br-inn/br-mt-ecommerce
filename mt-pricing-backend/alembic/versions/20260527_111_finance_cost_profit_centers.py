"""EP-ERP-06 US-ERP-06-02 — Cost Centers + Profit Centers.

Revision ID: 20260527_111
Revises: 20260527_110
Create Date: 2026-05-27

Tables: cost_centers, profit_centers
Seeds: 6 cost centers + 3 profit centers
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260527_111"
down_revision = "20260527_110"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # cost_centers
    # -------------------------------------------------------------------------
    op.create_table(
        "cost_centers",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("cc_code", sa.Text(), nullable=False),
        sa.Column("cc_name", sa.Text(), nullable=False),
        sa.Column(
            "parent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cost_centers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("cc_type", sa.Text(), nullable=True),
        sa.Column(
            "responsible_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("valid_from", sa.Date(), server_default=sa.text("CURRENT_DATE"), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "cc_type IN ('PRODUCTION','SERVICE','ADMIN','SALES','IT')",
            name="ck_cost_centers_cc_type",
        ),
        sa.UniqueConstraint("cc_code", name="uq_cost_centers_code"),
    )
    op.create_index("ix_cost_centers_code", "cost_centers", ["cc_code"])

    # -------------------------------------------------------------------------
    # profit_centers
    # -------------------------------------------------------------------------
    op.create_table(
        "profit_centers",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("pc_code", sa.Text(), nullable=False),
        sa.Column("pc_name", sa.Text(), nullable=False),
        sa.Column("business_area", sa.Text(), nullable=False),
        sa.Column(
            "responsible_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "business_area IN ('B2C','B2B','INTERNAL')",
            name="ck_profit_centers_business_area",
        ),
        sa.UniqueConstraint("pc_code", name="uq_profit_centers_code"),
    )
    op.create_index("ix_profit_centers_code", "profit_centers", ["pc_code"])

    # -------------------------------------------------------------------------
    # Seed: cost_centers
    # -------------------------------------------------------------------------
    op.execute("""
        INSERT INTO cost_centers (id, cc_code, cc_name, cc_type, valid_from) VALUES
        (gen_random_uuid(), '1010', 'CC_VENTAS',    'SALES',      CURRENT_DATE),
        (gen_random_uuid(), '1020', 'CC_MARKETING', 'SALES',      CURRENT_DATE),
        (gen_random_uuid(), '2010', 'CC_ALMACEN',   'PRODUCTION', CURRENT_DATE),
        (gen_random_uuid(), '2020', 'CC_LOGISTICA', 'SERVICE',    CURRENT_DATE),
        (gen_random_uuid(), '3010', 'CC_IT',        'IT',         CURRENT_DATE),
        (gen_random_uuid(), '4010', 'CC_GA',        'ADMIN',      CURRENT_DATE)
    """)

    # -------------------------------------------------------------------------
    # Seed: profit_centers
    # -------------------------------------------------------------------------
    op.execute("""
        INSERT INTO profit_centers (id, pc_code, pc_name, business_area) VALUES
        (gen_random_uuid(), 'PC_B2C_AE', 'B2C UAE',   'B2C'),
        (gen_random_uuid(), 'PC_B2C_SA', 'B2C KSA',   'B2C'),
        (gen_random_uuid(), 'PC_INTERN', 'Internal',  'INTERNAL')
    """)


def downgrade() -> None:
    op.execute("DELETE FROM profit_centers")
    op.execute("DELETE FROM cost_centers")
    op.drop_index("ix_profit_centers_code", table_name="profit_centers")
    op.drop_table("profit_centers")
    op.drop_index("ix_cost_centers_code", table_name="cost_centers")
    op.drop_table("cost_centers")

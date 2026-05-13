"""Source List + RFQ tables (US-ERP-03-05).

Revision ID: 20260523_111
Revises: 20260523_110
Create Date: 2026-05-23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision = "20260523_111"
down_revision = "20260523_110"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # source_list — proveedores aprobados por producto
    # ------------------------------------------------------------------
    op.create_table(
        "source_list",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "product_sku",
            sa.Text(),
            sa.ForeignKey("products.sku", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("vendor_id", sa.Text(), nullable=False),
        sa.Column("vendor_name", sa.Text(), nullable=True),
        sa.Column("is_preferred", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_blocked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("valid_from", sa.Date(), nullable=False, server_default=sa.text("CURRENT_DATE")),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("fixed_source", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_source_list"),
        sa.UniqueConstraint("product_sku", "vendor_id", name="uq_source_list_product_vendor"),
    )
    op.create_index("idx_sl_product_sku", "source_list", ["product_sku"])
    op.create_index(
        "idx_sl_active_preferred",
        "source_list",
        ["product_sku", "is_preferred"],
        postgresql_where=sa.text("is_blocked = false"),
    )

    # ------------------------------------------------------------------
    # rfq_headers
    # ------------------------------------------------------------------
    op.create_table(
        "rfq_headers",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("rfq_number", sa.Text(), nullable=False),
        sa.Column(
            "pr_id",
            sa.UUID(),
            sa.ForeignKey("purchase_requisitions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'draft'"),
        ),
        sa.Column("deadline", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column(
            "created_by",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_rfq_headers"),
        sa.UniqueConstraint("rfq_number", name="uq_rfq_headers_number"),
        sa.CheckConstraint(
            "status IN ('draft','sent','responses_received','awarded','cancelled')",
            name="ck_rfq_status",
        ),
    )
    op.create_index("idx_rfq_status", "rfq_headers", ["status"])
    op.create_index("idx_rfq_created_by", "rfq_headers", ["created_by"])

    # ------------------------------------------------------------------
    # rfq_lines
    # ------------------------------------------------------------------
    op.create_table(
        "rfq_lines",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "rfq_id",
            sa.UUID(),
            sa.ForeignKey("rfq_headers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "product_sku",
            sa.Text(),
            sa.ForeignKey("products.sku", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("qty", sa.Numeric(18, 4), nullable=False),
        sa.Column("uom", sa.String(32), nullable=False, server_default=sa.text("'UNIT'")),
        sa.PrimaryKeyConstraint("id", name="pk_rfq_lines"),
        sa.CheckConstraint("qty > 0", name="ck_rfq_lines_qty_pos"),
    )
    op.create_index("idx_rfq_lines_rfq", "rfq_lines", ["rfq_id"])

    # ------------------------------------------------------------------
    # rfq_vendor_responses
    # ------------------------------------------------------------------
    op.create_table(
        "rfq_vendor_responses",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "rfq_id",
            sa.UUID(),
            sa.ForeignKey("rfq_headers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("vendor_id", sa.Text(), nullable=False),
        sa.Column("unit_price", sa.Numeric(18, 4), nullable=True),
        sa.Column("currency", sa.CHAR(3), nullable=False, server_default=sa.text("'AED'")),
        sa.Column("lead_time_days", sa.Integer(), nullable=True),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_rfq_vendor_responses"),
        sa.UniqueConstraint("rfq_id", "vendor_id", name="uq_rfq_response_vendor"),
    )
    op.create_index("idx_rfqr_rfq", "rfq_vendor_responses", ["rfq_id"])


def downgrade() -> None:
    op.drop_table("rfq_vendor_responses")
    op.drop_table("rfq_lines")
    op.drop_table("rfq_headers")
    op.drop_table("source_list")

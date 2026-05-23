"""payment_terms — tabla de condiciones de pago + seed + columnas AP (US-ERP-05-03).

Revision ID: 20260602_139
Revises: 20260602_138
Create Date: 2026-06-02

Tablas nuevas:
- ``payment_terms`` — catálogo de condiciones de pago (NET30, NET60, 2/10 NET30, …).

Columnas añadidas:
- ``invoices.payment_terms_id`` — FK a payment_terms (reemplaza el campo Text existente).
- ``vendor_open_items.discount_days``, ``discount_days_deadline``, ``discount_pct``.

Seed: 5 condiciones estándar.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260602_139"
down_revision = "20260602_138"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Tabla payment_terms
    # ------------------------------------------------------------------
    op.create_table(
        "payment_terms",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "net_days",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("30"),
        ),
        sa.Column(
            "discount_pct",
            sa.Numeric(5, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "discount_days",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("code", name="uq_payment_terms_code"),
    )

    # ------------------------------------------------------------------
    # 2. Columna payment_terms_id en invoices
    # ------------------------------------------------------------------
    op.add_column(
        "invoices",
        sa.Column(
            "payment_terms_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("payment_terms.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "idx_invoice_payment_terms_id",
        "invoices",
        ["payment_terms_id"],
        postgresql_where=sa.text("payment_terms_id IS NOT NULL"),
    )

    # ------------------------------------------------------------------
    # 3. Columnas de descuento pronto-pago en vendor_open_items
    # ------------------------------------------------------------------
    op.add_column(
        "vendor_open_items",
        sa.Column("discount_days", sa.Integer(), nullable=True),
    )
    op.add_column(
        "vendor_open_items",
        sa.Column("discount_days_deadline", sa.Date(), nullable=True),
    )
    op.add_column(
        "vendor_open_items",
        sa.Column(
            "discount_pct",
            sa.Numeric(5, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )

    # ------------------------------------------------------------------
    # 4. Seed — 5 condiciones estándar
    # ------------------------------------------------------------------
    op.execute(
        text("""
        INSERT INTO payment_terms (code, name, net_days, discount_pct, discount_days)
        VALUES
            ('NET30',      'Net 30 Days',    30, 0.00,  0),
            ('NET60',      'Net 60 Days',    60, 0.00,  0),
            ('NET90',      'Net 90 Days',    90, 0.00,  0),
            ('IMMEDIATE',  'Pago Inmediato',  0, 0.00,  0),
            ('2_10_NET30', '2% 10 Net 30',   30, 2.00, 10)
        ON CONFLICT (code) DO NOTHING
    """)
    )


def downgrade() -> None:
    op.drop_column("vendor_open_items", "discount_pct")
    op.drop_column("vendor_open_items", "discount_days_deadline")
    op.drop_column("vendor_open_items", "discount_days")
    op.drop_index("idx_invoice_payment_terms_id", table_name="invoices")
    op.drop_column("invoices", "payment_terms_id")
    op.execute(
        text(
            "DELETE FROM payment_terms WHERE code IN "
            "('NET30','NET60','NET90','IMMEDIATE','2_10_NET30')"
        )
    )
    op.drop_table("payment_terms")

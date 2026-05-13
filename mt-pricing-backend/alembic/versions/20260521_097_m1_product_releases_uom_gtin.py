"""m1_product_releases_uom_gtin — Mejoras M1 Maestro de Producto.

Cambios:
- M1-01: tabla ``product_releases`` (D365 Released Product por mercado).
- M1-04: columna ``products.base_uom`` + tabla ``product_uom_conversions``.
- M1-05: ADD VALUE 'in_review' al tipo PostgreSQL ``lifecycle_status``.
- M1-08: columna ``products.gtin`` (EAN-8/12/13/14) + índice + CHECK.

Slot 097.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "097"
down_revision: str | None = "096"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # M1-05 — añadir 'in_review' al enum lifecycle_status
    # ALTER TYPE ... ADD VALUE sólo permite hacerlo fuera de transacción
    # en PG < 12; en PG 12+ es seguro dentro de transacción pero para
    # máxima compatibilidad usamos COMMIT / BEGIN explícito.
    # ------------------------------------------------------------------
    op.execute("COMMIT")
    op.execute(
        "ALTER TYPE lifecycle_status ADD VALUE IF NOT EXISTS 'in_review' "
        "AFTER 'draft'"
    )
    op.execute("BEGIN")

    # ------------------------------------------------------------------
    # M1-08 — gtin en products
    # ------------------------------------------------------------------
    op.add_column(
        "products",
        sa.Column("gtin", sa.String(14), nullable=True),
    )
    op.create_check_constraint(
        "ck_products_gtin_format",
        "products",
        "gtin IS NULL OR (length(gtin) IN (8,12,13,14) AND gtin ~ '^[0-9]+$')",
    )
    op.create_index("idx_products_gtin", "products", ["gtin"])

    # ------------------------------------------------------------------
    # M1-04 — base_uom en products
    # ------------------------------------------------------------------
    op.add_column(
        "products",
        sa.Column(
            "base_uom",
            sa.String(10),
            nullable=False,
            server_default=sa.text("'UNIT'"),
        ),
    )

    # ------------------------------------------------------------------
    # M1-04 — product_uom_conversions
    # ------------------------------------------------------------------
    op.create_table(
        "product_uom_conversions",
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("product_sku", sa.Text(), nullable=False),
        sa.Column("uom_from", sa.String(10), nullable=False),
        sa.Column("uom_to", sa.String(10), nullable=False),
        sa.Column("factor", sa.Numeric(18, 6), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name="pk_product_uom_conversions"),
        sa.ForeignKeyConstraint(
            ["product_sku"],
            ["products.sku"],
            ondelete="CASCADE",
            name="fk_uom_conv_product_sku",
        ),
        sa.CheckConstraint("uom_from <> uom_to", name="ck_uom_conv_no_self_loop"),
        sa.CheckConstraint("factor > 0", name="ck_uom_conv_positive_factor"),
    )
    op.create_index(
        "uq_uom_conv_product_pair",
        "product_uom_conversions",
        ["product_sku", "uom_from", "uom_to"],
        unique=True,
    )

    # ------------------------------------------------------------------
    # M1-01 — product_releases
    # ------------------------------------------------------------------
    op.create_table(
        "product_releases",
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("product_sku", sa.Text(), nullable=False),
        sa.Column("market_code", sa.String(10), nullable=False),
        sa.Column("local_name", sa.Text(), nullable=True),
        sa.Column("local_description", sa.Text(), nullable=True),
        sa.Column("local_sku", sa.String(50), nullable=True),
        sa.Column("local_uom", sa.String(10), nullable=True),
        sa.Column("list_price", sa.Numeric(18, 4), nullable=True),
        sa.Column("price_currency", sa.String(3), nullable=True),
        sa.Column("tax_class", sa.String(50), nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'draft'"),
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("released_by", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_product_releases"),
        sa.ForeignKeyConstraint(
            ["product_sku"],
            ["products.sku"],
            ondelete="CASCADE",
            name="fk_releases_product_sku",
        ),
        sa.ForeignKeyConstraint(
            ["released_by"],
            ["users.id"],
            ondelete="SET NULL",
            name="fk_releases_released_by",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            ondelete="SET NULL",
            name="fk_releases_created_by",
        ),
        sa.CheckConstraint(
            "status IN ('draft','active','suspended','discontinued')",
            name="ck_product_releases_status",
        ),
        sa.CheckConstraint(
            "price_currency IS NULL OR length(price_currency) = 3",
            name="ck_product_releases_currency_len",
        ),
    )
    op.create_index(
        "uq_product_releases_sku_market",
        "product_releases",
        ["product_sku", "market_code"],
        unique=True,
    )
    op.create_index(
        "idx_product_releases_active",
        "product_releases",
        ["market_code", "is_active"],
    )


def downgrade() -> None:
    op.drop_table("product_releases")
    op.drop_table("product_uom_conversions")
    op.drop_index("idx_products_gtin", table_name="products")
    op.drop_constraint("ck_products_gtin_format", "products", type_="check")
    op.drop_column("products", "gtin")
    op.drop_column("products", "base_uom")
    # No se puede hacer downgrade de ADD VALUE en PostgreSQL — se omite.

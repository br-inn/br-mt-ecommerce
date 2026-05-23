"""product_scalars — Wave 2: lifecycle + technical scalars + parent/child columns.

Cambios:
- Enum ``lifecycle_status``: draft|active|deprecated|replaced|discontinued.
- Identidad/lifecycle:
    * lifecycle_status (lifecycle_status NOT NULL DEFAULT 'active')
    * revision (text)
    * series (text)
    * parent_sku (text, FK self products(sku) ON DELETE SET NULL)
    * is_parent (bool NOT NULL DEFAULT false)
    * is_variant (bool NOT NULL DEFAULT false)
- Técnicos:
    * dn_real (text), size (text)
    * temp_min_c (int), temp_max_c (int)
    * pressure_max_bar (numeric(8,2))
    * manufacturing_method (text)
    * actuator (text)
    * kv (numeric(10,2)), kv2 (numeric(10,2))
    * torque_nm (numeric(10,2))
    * iso5211_interface (text)
- Editorial/SEO:
    * tags (text[] NOT NULL DEFAULT '{}')
    * video_url (text), external_url (text)

Migración de datos:
- lifecycle_status = 'active' WHERE active=true ELSE 'discontinued'.
- is_parent / is_variant default false (todo plano hoy).

Slot 037.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260508_037"
down_revision: str | None = "80af479d704d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ---- Enum lifecycle_status (idempotent) ----------------------------------
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE lifecycle_status AS ENUM (
                'draft','active','deprecated','replaced','discontinued'
            );
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
        """
    )

    # ---- Identidad / lifecycle ----------------------------------------------
    op.add_column(
        "products",
        sa.Column(
            "lifecycle_status",
            postgresql.ENUM(
                "draft",
                "active",
                "deprecated",
                "replaced",
                "discontinued",
                name="lifecycle_status",
                create_type=False,
            ),
            nullable=False,
            server_default=sa.text("'active'::lifecycle_status"),
        ),
    )
    op.add_column("products", sa.Column("revision", sa.Text(), nullable=True))
    op.add_column("products", sa.Column("series", sa.Text(), nullable=True))
    op.add_column(
        "products",
        sa.Column(
            "parent_sku",
            sa.Text(),
            sa.ForeignKey("products.sku", ondelete="SET NULL", name="fk_products_parent_sku"),
            nullable=True,
        ),
    )
    op.add_column(
        "products",
        sa.Column("is_parent", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "products",
        sa.Column("is_variant", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )

    # ---- Técnicos ------------------------------------------------------------
    op.add_column("products", sa.Column("dn_real", sa.Text(), nullable=True))
    op.add_column("products", sa.Column("size", sa.Text(), nullable=True))
    op.add_column("products", sa.Column("temp_min_c", sa.Integer(), nullable=True))
    op.add_column("products", sa.Column("temp_max_c", sa.Integer(), nullable=True))
    op.add_column("products", sa.Column("pressure_max_bar", sa.Numeric(8, 2), nullable=True))
    op.add_column("products", sa.Column("manufacturing_method", sa.Text(), nullable=True))
    op.add_column("products", sa.Column("actuator", sa.Text(), nullable=True))
    op.add_column("products", sa.Column("kv", sa.Numeric(10, 2), nullable=True))
    op.add_column("products", sa.Column("kv2", sa.Numeric(10, 2), nullable=True))
    op.add_column("products", sa.Column("torque_nm", sa.Numeric(10, 2), nullable=True))
    op.add_column("products", sa.Column("iso5211_interface", sa.Text(), nullable=True))

    # ---- Editorial / SEO ----------------------------------------------------
    op.add_column(
        "products",
        sa.Column(
            "tags",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
    )
    op.add_column("products", sa.Column("video_url", sa.Text(), nullable=True))
    op.add_column("products", sa.Column("external_url", sa.Text(), nullable=True))

    # ---- Backfill datos -----------------------------------------------------
    # lifecycle_status: derived from current `active` flag.
    op.execute(
        "UPDATE products SET lifecycle_status = CASE WHEN active THEN 'active'::lifecycle_status "
        "ELSE 'discontinued'::lifecycle_status END"
    )

    # ---- Indexes para facet/parent lookup -----------------------------------
    op.create_index("idx_products_lifecycle_status", "products", ["lifecycle_status"])
    op.create_index(
        "idx_products_parent_sku",
        "products",
        ["parent_sku"],
        postgresql_where=sa.text("parent_sku IS NOT NULL"),
    )
    op.create_index(
        "idx_products_is_parent",
        "products",
        ["is_parent"],
        postgresql_where=sa.text("is_parent = true"),
    )
    op.create_index("idx_products_tags_gin", "products", ["tags"], postgresql_using="gin")

    # ---- Constraints --------------------------------------------------------
    # Temperatura: si ambos están, max debe ser >= min.
    op.create_check_constraint(
        "chk_products_temp_range",
        "products",
        "temp_min_c IS NULL OR temp_max_c IS NULL OR temp_max_c >= temp_min_c",
    )


def downgrade() -> None:
    op.drop_constraint("chk_products_temp_range", "products", type_="check")
    op.drop_index("idx_products_tags_gin", table_name="products")
    op.drop_index("idx_products_is_parent", table_name="products")
    op.drop_index("idx_products_parent_sku", table_name="products")
    op.drop_index("idx_products_lifecycle_status", table_name="products")

    for col in (
        "external_url",
        "video_url",
        "tags",
        "iso5211_interface",
        "torque_nm",
        "kv2",
        "kv",
        "actuator",
        "manufacturing_method",
        "pressure_max_bar",
        "temp_max_c",
        "temp_min_c",
        "size",
        "dn_real",
        "is_variant",
        "is_parent",
        "parent_sku",
        "series",
        "revision",
        "lifecycle_status",
    ):
        op.drop_column("products", col)

    op.execute("DROP TYPE IF EXISTS lifecycle_status")

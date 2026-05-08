"""components — Wave 3: product_materials + product_connections (multi-componente).

Cambios:
- Enum ``component_kind``: body|closure|seat|gasket|screen|actuator_housing|stem|handle|other.
- Enum ``connection_type``: flange|threaded|weld|press|push_fit|compression|other.
- Tabla ``product_materials``: 1 producto → N materiales por componente.
    Composite PK (product_sku, component, position).
- Tabla ``product_connections``: 1 producto → N conexiones (hasta 3+ vías).
    Composite PK (product_sku, position).

Slot 038.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260508_038"
down_revision: str | None = "20260508_037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ---- Enums (idempotent DO blocks) ---------------------------------------
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE component_kind AS ENUM (
                'body','closure','seat','gasket','screen',
                'actuator_housing','stem','handle','other'
            );
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
        """
    )
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE connection_type AS ENUM (
                'flange','threaded','weld','press','push_fit','compression','other'
            );
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
        """
    )

    # ---- product_materials --------------------------------------------------
    op.create_table(
        "product_materials",
        sa.Column(
            "product_sku",
            sa.Text,
            sa.ForeignKey("products.sku", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "component",
            postgresql.ENUM(
                "body", "closure", "seat", "gasket", "screen",
                "actuator_housing", "stem", "handle", "other",
                name="component_kind",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "position",
            sa.SmallInteger,
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("material", sa.Text, nullable=False),
        sa.Column("observations", sa.Text, nullable=True),
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
        sa.PrimaryKeyConstraint("product_sku", "component", "position", name="pk_product_materials"),
    )
    op.create_index("idx_product_materials_sku", "product_materials", ["product_sku"])
    op.create_index("idx_product_materials_material", "product_materials", ["material"])
    op.create_index("idx_product_materials_component", "product_materials", ["component"])

    # ---- product_connections ------------------------------------------------
    op.create_table(
        "product_connections",
        sa.Column(
            "product_sku",
            sa.Text,
            sa.ForeignKey("products.sku", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "position",
            sa.SmallInteger,
            nullable=False,
        ),
        sa.Column(
            "connection_type",
            postgresql.ENUM(
                "flange", "threaded", "weld", "press", "push_fit", "compression", "other",
                name="connection_type",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("dn", sa.Text, nullable=True),
        sa.Column("dn_real", sa.Text, nullable=True),
        sa.Column("size", sa.Text, nullable=True),
        sa.Column("threading", sa.Text, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
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
        sa.PrimaryKeyConstraint("product_sku", "position", name="pk_product_connections"),
        sa.CheckConstraint("position >= 1 AND position <= 8", name="chk_connection_position"),
    )
    op.create_index("idx_product_connections_sku", "product_connections", ["product_sku"])
    op.create_index("idx_product_connections_type", "product_connections", ["connection_type"])
    op.create_index("idx_product_connections_dn", "product_connections", ["dn"])

    # ---- Trigger: denormalize products.material from body[position=0] -------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION sync_product_material_denorm()
        RETURNS TRIGGER AS $$
        BEGIN
            IF (TG_OP = 'DELETE') THEN
                IF OLD.component = 'body' AND OLD.position = 0 THEN
                    UPDATE products SET material = NULL WHERE sku = OLD.product_sku;
                END IF;
                RETURN OLD;
            ELSE
                IF NEW.component = 'body' AND NEW.position = 0 THEN
                    UPDATE products SET material = NEW.material WHERE sku = NEW.product_sku;
                END IF;
                RETURN NEW;
            END IF;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_product_materials_denorm
        AFTER INSERT OR UPDATE OR DELETE ON product_materials
        FOR EACH ROW EXECUTE FUNCTION sync_product_material_denorm();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_product_materials_denorm ON product_materials")
    op.execute("DROP FUNCTION IF EXISTS sync_product_material_denorm()")
    op.drop_index("idx_product_connections_dn", table_name="product_connections")
    op.drop_index("idx_product_connections_type", table_name="product_connections")
    op.drop_index("idx_product_connections_sku", table_name="product_connections")
    op.drop_table("product_connections")
    op.drop_index("idx_product_materials_component", table_name="product_materials")
    op.drop_index("idx_product_materials_material", table_name="product_materials")
    op.drop_index("idx_product_materials_sku", table_name="product_materials")
    op.drop_table("product_materials")
    op.execute("DROP TYPE IF EXISTS connection_type")
    op.execute("DROP TYPE IF EXISTS component_kind")

"""product_compatibility M:N — Wave 7 (recambios/accesorios).

Cambios:
- Enum ``compatibility_kind``:
    spare_part | accessory | replaces | replaced_by | compatible_with
- Tabla ``product_compatibility``:
    * id UUID PK
    * product_sku TEXT NOT NULL FK→products(sku) CASCADE
    * compatible_with_sku TEXT NOT NULL FK→products(sku) CASCADE
    * kind compatibility_kind NOT NULL
    * notes TEXT NULL
    * position SMALLINT NOT NULL DEFAULT 0
    * created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    * created_by UUID NULL FK→users(id) SET NULL
    * CHECK product_sku <> compatible_with_sku (no self-loop)
    * UNIQUE (product_sku, compatible_with_sku, kind)
- Índices en product_sku, compatible_with_sku y kind.

Nota sobre bidireccionalidad:
  La relación es INTENCIONALMENTE unidireccional en la base de datos.
  El servicio (CompatibilityService) mantiene sincronía automática sólo para
  el par semántico ``replaces``/``replaced_by``:
    - Al añadir  A → replaces → B  también persiste  B → replaced_by → A.
    - Al eliminar A → replaces → B  también elimina   B → replaced_by → A.
  El resto de tipos (spare_part, accessory, compatible_with) se almacenan
  en la dirección en que el usuario los declara; el endpoint ``/inverse``
  permite consultar la vista inversa.

Slot 035 — rama independiente (branches).

Revision ID: 20260508_035
Revises: 20260507_029
Create Date: 2026-05-08
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PgUUID

revision: str = "20260508_035"
down_revision: str | None = "20260507_029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Enum type (PostgreSQL-native).
    op.execute(
        """
        CREATE TYPE compatibility_kind AS ENUM (
            'spare_part',
            'accessory',
            'replaces',
            'replaced_by',
            'compatible_with'
        )
        """
    )

    op.create_table(
        "product_compatibility",
        sa.Column(
            "id",
            PgUUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "product_sku",
            sa.Text,
            sa.ForeignKey("products.sku", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "compatible_with_sku",
            sa.Text,
            sa.ForeignKey("products.sku", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "kind",
            sa.Enum(
                "spare_part",
                "accessory",
                "replaces",
                "replaced_by",
                "compatible_with",
                name="compatibility_kind",
                create_type=False,  # ya creado arriba
            ),
            nullable=False,
        ),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "position",
            sa.SmallInteger,
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "created_by",
            PgUUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.CheckConstraint(
            "product_sku <> compatible_with_sku",
            name="chk_no_self_compatibility",
        ),
        sa.UniqueConstraint(
            "product_sku",
            "compatible_with_sku",
            "kind",
            name="uq_product_compatibility",
        ),
    )

    op.create_index(
        "idx_product_compatibility_sku",
        "product_compatibility",
        ["product_sku"],
    )
    op.create_index(
        "idx_product_compatibility_with",
        "product_compatibility",
        ["compatible_with_sku"],
    )
    op.create_index(
        "idx_product_compatibility_kind",
        "product_compatibility",
        ["kind"],
    )


def downgrade() -> None:
    op.drop_index("idx_product_compatibility_kind", table_name="product_compatibility")
    op.drop_index("idx_product_compatibility_with", table_name="product_compatibility")
    op.drop_index("idx_product_compatibility_sku", table_name="product_compatibility")
    op.drop_table("product_compatibility")
    op.execute("DROP TYPE IF EXISTS compatibility_kind")

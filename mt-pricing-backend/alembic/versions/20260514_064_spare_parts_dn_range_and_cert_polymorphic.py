"""Fase 5 — spare parts con DN range + certifications polymorphic.

Esta migración extiende dos tablas existentes para soportar el modelo Phase 5
descrito en PDF §12 y en el documento de comparativa
``_bmad-output/implementation-artifacts/comparativa-modelo-pim-propuesto-vs-implementado-2026-05-11.md``
(§4 — Fase 5):

1.  ``product_compatibility`` — relaciones M:N entre productos: extender con
    ``owner_type`` polymorphic (product/variant/series) + rango DN
    (``dn_min``/``dn_max``). Permite vincular un recambio a un producto
    concreto (owner_type='product' + product_sku) o a una serie completa con
    rango de calibres (owner_type='series' + dn_min/dn_max).

2.  ``product_certifications`` — junction products ↔ certifications: extender
    con columnas ``owner_type`` + ``owner_id`` para soportar certificaciones
    polymorphic (product/variant/series) sin romper compatibilidad con código
    existente.

**Decisión FK compat (product_certifications):**

La tabla actual define ``PK = (product_sku, certification_id)`` con FK
``product_sku → products.sku ON DELETE CASCADE``. Otras partes del backend
referencian ``ProductCertification.product_sku`` extensivamente
(``app/services/products/effective_display_service.py``, relationship
``Product.product_certifications``, etc.) y la PK incluye ``product_sku``.

Por ello, esta migración **NO drop** la columna ``product_sku``. En su lugar:

* Añade columnas ``owner_type`` (NOT NULL, default 'product') y ``owner_id``
  (NOT NULL) como ampliación polymorphic.
* Backfill ``owner_type='product'``, ``owner_id=product_sku`` para filas
  existentes.
* Mantiene ``product_sku`` como NOT NULL existente (no se relaja para
  preservar compat de relationship). Para soportar variant/series en el
  futuro se requerirá otra migración que relaje NOT NULL y elimine la FK
  desde ``product_sku``.
* Añade UNIQUE ``(owner_type, owner_id, certification_id)`` y un índice
  filtrado para queries polymorphic.

Revision ID: 20260514_064
Revises: 20260514_063
Create Date: 2026-05-14
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260514_064"
down_revision: str | None = "20260514_063"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# ---------------------------------------------------------------------------
# upgrade
# ---------------------------------------------------------------------------
def upgrade() -> None:
    # =====================================================================
    # 1) product_compatibility — owner_type + DN range
    # =====================================================================
    op.add_column(
        "product_compatibility",
        sa.Column(
            "owner_type",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'product'"),
        ),
    )
    op.add_column(
        "product_compatibility",
        sa.Column("dn_min", sa.Integer(), nullable=True),
    )
    op.add_column(
        "product_compatibility",
        sa.Column("dn_max", sa.Integer(), nullable=True),
    )

    op.create_check_constraint(
        "ck_product_compatibility_owner_type",
        "product_compatibility",
        "owner_type IN ('product','variant','series')",
    )
    op.create_check_constraint(
        "ck_compat_dn_range",
        "product_compatibility",
        "dn_min IS NULL OR dn_max IS NULL OR dn_max >= dn_min",
    )
    op.create_index(
        "ix_compat_owner",
        "product_compatibility",
        ["owner_type", "product_sku"],
    )

    # =====================================================================
    # 2) product_certifications — owner_type + owner_id (compat layer)
    # =====================================================================
    op.add_column(
        "product_certifications",
        sa.Column("owner_type", sa.Text(), nullable=True),
    )
    op.add_column(
        "product_certifications",
        sa.Column("owner_id", sa.Text(), nullable=True),
    )

    # Backfill: para filas existentes owner_type='product', owner_id=product_sku.
    op.execute(
        sa.text(
            """
            UPDATE product_certifications
            SET owner_type = 'product', owner_id = product_sku
            WHERE owner_type IS NULL
            """
        )
    )

    op.alter_column(
        "product_certifications",
        "owner_type",
        existing_type=sa.Text(),
        nullable=False,
        server_default=sa.text("'product'"),
    )
    op.alter_column(
        "product_certifications",
        "owner_id",
        existing_type=sa.Text(),
        nullable=False,
    )

    op.create_check_constraint(
        "ck_pc_owner_type",
        "product_certifications",
        "owner_type IN ('product','variant','series')",
    )

    # UNIQUE polymorphic — clave natural alternativa cuando owner_type != product.
    op.create_unique_constraint(
        "uq_product_certifications_owner",
        "product_certifications",
        ["owner_type", "owner_id", "certification_id"],
    )
    op.create_index(
        "ix_product_certifications_owner",
        "product_certifications",
        ["owner_type", "owner_id"],
    )


# ---------------------------------------------------------------------------
# downgrade
# ---------------------------------------------------------------------------
def downgrade() -> None:
    # 2) product_certifications — revertir
    op.drop_index(
        "ix_product_certifications_owner",
        table_name="product_certifications",
    )
    op.drop_constraint(
        "uq_product_certifications_owner",
        "product_certifications",
        type_="unique",
    )
    op.drop_constraint(
        "ck_pc_owner_type",
        "product_certifications",
        type_="check",
    )
    op.drop_column("product_certifications", "owner_id")
    op.drop_column("product_certifications", "owner_type")

    # 1) product_compatibility — revertir
    op.drop_index("ix_compat_owner", table_name="product_compatibility")
    op.drop_constraint(
        "ck_compat_dn_range",
        "product_compatibility",
        type_="check",
    )
    op.drop_constraint(
        "ck_product_compatibility_owner_type",
        "product_compatibility",
        type_="check",
    )
    op.drop_column("product_compatibility", "dn_max")
    op.drop_column("product_compatibility", "dn_min")
    op.drop_column("product_compatibility", "owner_type")

"""Fase 4 — polymorphic asset_links for cross-entity references (PDF §11).

Introduce capa `asset_links` polimórfica para permitir que un asset (de
`product_assets`) esté vinculado a cualquier owner del catálogo:
`product | variant | series | family | spare_part` con un `role` semántico.

Backfill: por cada `product_assets` existente se inserta una fila en
`asset_links` con `owner_type='product'`, `owner_id=sku`, `role=kind`,
`order_index=position`. Esto preserva los links actuales sin romper la API
Wave 1 (`product_assets.sku` se mantiene como columna FK durante transición).

Coexistencia con Wave 1: `product_assets` sigue siendo source-of-truth del
binario; `asset_links` agrega la dimensión polimórfica. Más adelante (Fase B)
se puede deprecar `product_assets.sku` una vez frontend/services migren a leer
desde `asset_links`.

Revision ID: 20260514_058
Revises: 20260514_056
Create Date: 2026-05-14
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PgUUID

revision: str = "20260514_058"
down_revision: str | None = "20260514_056"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


OWNER_TYPES = ("product", "variant", "series", "family", "spare_part")

ROLES = (
    "image_padre",
    "banner",
    "ficha_pdf",
    "manual_pdf",
    "ce_pdf",
    "catalogo_pdf",
    "exploded_3d",
    "section_drawing",
    "dimensions_drawing",
    "video",
    "web_image",
    "main_image",
)


def upgrade() -> None:
    op.create_table(
        "asset_links",
        sa.Column(
            "id",
            PgUUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "asset_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("product_assets.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("owner_type", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column(
            "order_index",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "owner_type IN (" + ", ".join(f"'{t}'" for t in OWNER_TYPES) + ")",
            name="ck_asset_links_owner_type",
        ),
        sa.CheckConstraint(
            "role IN (" + ", ".join(f"'{r}'" for r in ROLES) + ")",
            name="ck_asset_links_role",
        ),
        sa.UniqueConstraint(
            "asset_id",
            "owner_type",
            "owner_id",
            "role",
            name="uq_asset_links_asset_owner_role",
        ),
    )
    op.create_index(
        "ix_al_owner",
        "asset_links",
        ["owner_type", "owner_id"],
    )
    op.create_index("ix_al_asset", "asset_links", ["asset_id"])

    # ------------------------------------------------------------------
    # Backfill — poblar asset_links desde product_assets existentes.
    # Solo se hace para kinds que mapean limpiamente al nuevo enum de roles.
    # Los kinds Wave 1 que NO coincidan con role enum quedan sin link
    # (se crearán manualmente o vía servicio en frontera).
    # ------------------------------------------------------------------
    # Mapeo kind (Wave 1) → role (Fase 4):
    #   'photo'             → 'web_image'
    #   'banner'            → 'banner'
    #   'datasheet_pdf'     → 'ficha_pdf'
    #   'certificate_pdf'   → 'ce_pdf'
    #   'exploded_3d'       → 'exploded_3d'
    #   'section_drawing'   → 'section_drawing'
    #   'dimension_drawing' → 'dimensions_drawing'
    #   'video_link'        → 'video'
    #   'external_url' / 'mirror_url' → no se backfilan (sin rol semántico).
    op.execute(
        """
        INSERT INTO asset_links (asset_id, owner_type, owner_id, role, order_index)
        SELECT
            pa.id,
            'product' AS owner_type,
            pa.sku AS owner_id,
            CASE pa.kind
                WHEN 'photo' THEN 'web_image'
                WHEN 'banner' THEN 'banner'
                WHEN 'datasheet_pdf' THEN 'ficha_pdf'
                WHEN 'certificate_pdf' THEN 'ce_pdf'
                WHEN 'exploded_3d' THEN 'exploded_3d'
                WHEN 'section_drawing' THEN 'section_drawing'
                WHEN 'dimension_drawing' THEN 'dimensions_drawing'
                WHEN 'video_link' THEN 'video'
            END AS role,
            COALESCE(pa.position, 0) AS order_index
        FROM product_assets pa
        WHERE pa.kind IN (
            'photo','banner','datasheet_pdf','certificate_pdf',
            'exploded_3d','section_drawing','dimension_drawing','video_link'
        )
        ON CONFLICT ON CONSTRAINT uq_asset_links_asset_owner_role DO NOTHING;
        """
    )


def downgrade() -> None:
    op.drop_index("ix_al_asset", table_name="asset_links")
    op.drop_index("ix_al_owner", table_name="asset_links")
    op.drop_table("asset_links")

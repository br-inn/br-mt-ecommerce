"""Fase 0 — drop legacy promised by 030_assets_unification (reaplicado post-merge taxonomy 2026-05-13).

Drop final de columnas legacy heredadas de la pre-unificación de assets:

- ``products.image_url`` — preview URL primaria. Reemplazado por
  ``product_assets`` (kind='photo', is_primary=true) y resuelto en el
  servicio de listado / detalle.
- ``products.image_origin_url`` — URL externa antes del mirror. No usado
  desde la unificación (mig 030).
- ``products.image_status`` — enum {missing, mirrored, failed}. Reemplazado
  por la presencia/estado de un asset de kind='photo' status='active'
  (``has_image`` se computa con EXISTS()).
- ``product_assets.role`` — antiguo discriminador pre-``kind``. La mig 030
  lo dejó nullable para backward compat; aquí lo eliminamos definitivamente.

También se dropea el CHECK constraint asociado a image_status si existe.

Revision ID: 20260513_053
Revises: 20260512_052
Create Date: 2026-05-13
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260513_053"
down_revision: str | None = "20260512_052"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Drop CHECK constraint ck_products_image_status si existe (idempotente).
    op.execute("ALTER TABLE public.products DROP CONSTRAINT IF EXISTS ck_products_image_status")

    # Drop columnas legacy en products (todas IF EXISTS para idempotencia).
    op.execute("ALTER TABLE public.products DROP COLUMN IF EXISTS image_url")
    op.execute("ALTER TABLE public.products DROP COLUMN IF EXISTS image_origin_url")
    op.execute("ALTER TABLE public.products DROP COLUMN IF EXISTS image_status")

    # Drop columna legacy en product_assets.
    op.execute("ALTER TABLE public.product_assets DROP COLUMN IF EXISTS role")


def downgrade() -> None:
    # Recreate columnas como nullable (no restore de datos — informativo).
    op.add_column(
        "product_assets",
        sa.Column("role", sa.Text(), nullable=True),
    )
    op.add_column(
        "products",
        sa.Column("image_status", sa.String(length=16), nullable=True),
    )
    op.add_column(
        "products",
        sa.Column("image_origin_url", sa.Text(), nullable=True),
    )
    op.add_column(
        "products",
        sa.Column("image_url", sa.Text(), nullable=True),
    )
    # Restablece el server_default + CHECK constraint históricos.
    op.execute("UPDATE public.products SET image_status = 'missing' WHERE image_status IS NULL")
    op.alter_column(
        "products",
        "image_status",
        nullable=False,
        server_default=sa.text("'missing'"),
    )
    op.create_check_constraint(
        "ck_products_image_status",
        "products",
        "image_status IN ('missing','mirrored','failed')",
    )

"""product_images.image_status — pipeline state para mirror worker.

S2 — Gap-fix backend. Añade columna `image_status` a `product_images` para que
el worker `app.workers.probe_mirror.probe_and_mirror_image` (US-1A-02-07) pueda
señalizar el ciclo de vida del mirror obligatorio:

    pending  → mirroring → mirrored
                       \\→ failed

Notas:
- `String(16) + CHECK` (estrategia DDL — ver `app/db/enums.py`).
- `server_default = 'pending'` para backfill seguro de filas existentes.
- Index parcial sobre rows en estado activo de mirror para que el worker
  pueda hacer scan barato (`pending|mirroring`).

Revision ID: 20260507_007
Revises: 20260507_006
Create Date: 2026-05-07
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260507_007"
down_revision: str | None = "20260507_006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "product_images",
        sa.Column(
            "image_status",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
    )
    op.create_check_constraint(
        "ck_product_images_image_status",
        "product_images",
        "image_status IN ('pending','mirroring','mirrored','failed')",
    )
    # Index parcial — el worker solo hace polling sobre el estado activo.
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_product_images_image_status_active
            ON product_images (image_status)
         WHERE image_status IN ('pending','mirroring');
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_product_images_image_status_active;")
    op.drop_constraint("ck_product_images_image_status", "product_images", type_="check")
    op.drop_column("product_images", "image_status")

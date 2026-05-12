"""Fase B step 2 — drop active boolean, derivable from lifecycle_status (audit LEG-01).

Refactor PIM Fase B (paso 2 de 2): ``products.active`` se elimina porque
es redundante con ``products.lifecycle_status`` (Wave 2 — vocabulario
controlado: draft/active/deprecated/replaced/discontinued).

Backfill antes de drop:
- Para cada producto con ``active=false``, garantizar que
  ``lifecycle_status`` refleje el estado inactivo:
    * Si ``lifecycle_status IN ('active','draft')`` → upgrade a
      ``'deprecated'`` (preserva semántica de "no comercializable").
    * Si ya está en ('deprecated','replaced','discontinued') → no tocar.

Downgrade:
- Recrear columna ``active`` NOT NULL DEFAULT true, backfill
  ``active = (lifecycle_status = 'active')``.

Revision ID: 20260515_066
Revises: 20260515_065
Create Date: 2026-05-15
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260515_066"
down_revision: str | None = "20260515_065"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# ---------------------------------------------------------------------------
# upgrade
# ---------------------------------------------------------------------------
def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    # =====================================================================
    # 1) Backfill: preservar semántica "inactive" en lifecycle_status
    # =====================================================================
    if dialect == "postgresql":
        op.execute(
            sa.text(
                """
                UPDATE products
                SET lifecycle_status = 'deprecated'
                WHERE active = false
                  AND lifecycle_status IN ('active', 'draft')
                """
            )
        )

    # =====================================================================
    # 2) DROP index parcial sobre active (mig 001/003), si existe.
    # =====================================================================
    if dialect == "postgresql":
        op.execute(sa.text("DROP INDEX IF EXISTS idx_products_active"))

    # =====================================================================
    # 3) DROP column products.active
    # =====================================================================
    op.drop_column("products", "active")


# ---------------------------------------------------------------------------
# downgrade
# ---------------------------------------------------------------------------
def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    # Recreate column nullable=False default true.
    op.add_column(
        "products",
        sa.Column(
            "active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )

    # Backfill active from lifecycle_status (active when lifecycle is 'active').
    if dialect == "postgresql":
        op.execute(
            sa.text(
                """
                UPDATE products
                SET active = (lifecycle_status = 'active')
                """
            )
        )

        # Recreate partial index.
        op.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS idx_products_active "
                "ON products (active) WHERE active = true"
            )
        )

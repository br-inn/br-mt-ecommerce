"""Backfill products.family_id from products.family TEXT (post-taxonomy/Fase B unification).

Tras Fase B (unificación taxonomy/registry), ``products`` tiene tanto la
columna heredada ``family TEXT`` como la nueva FK ``family_id UUID``. Esta
migración llena ``family_id`` para filas con ``family_id IS NULL`` mapeando
contra ``families.code``.

Las filas cuyo ``family`` no matchea ningún ``families.code`` quedan con
``family_id NULL`` y se loggea su count (gap a remediar manualmente o con
una nueva migración de seed de families).

Reportes vía ``print()`` — alembic captura output.

Downgrade: ``UPDATE products SET family_id = NULL`` (idempotente, reversible
si el FE/back necesita reaplicar luego con otro mapping).

Revision ID: 20260516_068
Revises: 20260516_067
Create Date: 2026-05-16
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "20260516_068"
down_revision: str | None = "20260516_067"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()

    # Pre-stats
    pre_null = bind.execute(
        text("SELECT COUNT(*) FROM products WHERE family_id IS NULL AND family IS NOT NULL")
    ).scalar()
    print(f"[mig 068] pre-backfill: products with family_id NULL and family NOT NULL = {pre_null}")

    # Backfill
    result = bind.execute(
        text(
            """
            UPDATE products p
            SET family_id = f.id
            FROM families f
            WHERE p.family = f.code
              AND p.family_id IS NULL
              AND p.family IS NOT NULL
            """
        )
    )
    updated = result.rowcount if result.rowcount is not None else -1
    print(f"[mig 068] backfilled family_id for {updated} products")

    # No-match count (filas que aún quedaron con family_id NULL pese a
    # tener family TEXT poblado).
    no_match = bind.execute(
        text("SELECT COUNT(*) FROM products WHERE family_id IS NULL AND family IS NOT NULL")
    ).scalar()
    print(
        f"[mig 068] post-backfill: products with family TEXT but no "
        f"matching families.code (still family_id NULL) = {no_match}"
    )

    if no_match and no_match > 0:
        # Log distinct codes con gap.
        gaps = bind.execute(
            text(
                "SELECT family, COUNT(*) FROM products "
                "WHERE family_id IS NULL AND family IS NOT NULL "
                "GROUP BY family ORDER BY family"
            )
        ).fetchall()
        for g in gaps:
            print(f"[mig 068] gap: family='{g[0]}' count={g[1]}")


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(text("UPDATE products SET family_id = NULL"))
    print("[mig 068] downgrade: set products.family_id = NULL on all rows")

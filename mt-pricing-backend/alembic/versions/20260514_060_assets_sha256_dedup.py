"""Fase 4 — SHA-256 dedup unique constraint on product_assets.

Añade UNIQUE constraint sobre `product_assets.hash_sha256` para garantizar
deduplicación de binarios. Si llega un upload con un SHA-256 ya conocido, el
servicio debe reutilizar el asset existente en lugar de insertar uno nuevo
(ver `app/services/assets/asset_link_service.py::find_or_create_asset_by_hash`).

Defensive: si la base de datos ya tiene la unique key o si existen duplicados
in-flight, la migración no rompe — solo emite warning y deja a operaciones
limpiar antes de re-aplicar.

Revision ID: 20260514_060
Revises: 20260514_059
Create Date: 2026-05-14
"""

from __future__ import annotations

import warnings
from collections.abc import Sequence

from sqlalchemy import text

from alembic import op

revision: str = "20260514_060"
down_revision: str | None = "20260514_059"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


CONSTRAINT_NAME = "uq_product_assets_hash_sha256"


def upgrade() -> None:
    bind = op.get_bind()

    # 1) Si la unique key ya existe (cualquier nombre), abortar idempotente.
    existing = bind.execute(
        text(
            """
            SELECT indexname
            FROM pg_indexes
            WHERE tablename = 'product_assets'
              AND indexname LIKE '%hash%'
              AND indexdef ILIKE '%UNIQUE%'
            """
        )
    ).fetchall()
    if existing:
        print(
            f"[mig 060] UNIQUE index sobre hash_sha256 ya existe: "
            f"{[r[0] for r in existing]} — skip."
        )
        return

    # 2) Detectar duplicados antes de añadir constraint.
    dup_rows = bind.execute(
        text(
            """
            SELECT hash_sha256, COUNT(*) AS c
            FROM product_assets
            WHERE hash_sha256 IS NOT NULL
            GROUP BY hash_sha256
            HAVING COUNT(*) > 1
            """
        )
    ).fetchall()

    if dup_rows:
        msg = (
            f"[mig 060] {len(dup_rows)} hash_sha256 duplicados detectados en "
            f"product_assets — UNIQUE constraint NO añadida. "
            f"Limpia duplicados (mantener oldest) y re-aplica esta migración."
        )
        print(msg)
        warnings.warn(msg, UserWarning, stacklevel=1)
        return

    # 3) Crear UNIQUE constraint (NULL values are allowed múltiplemente por SQL std).
    op.create_unique_constraint(
        CONSTRAINT_NAME,
        "product_assets",
        ["hash_sha256"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    exists = bind.execute(
        text(
            f"""
            SELECT 1 FROM pg_constraint
            WHERE conname = '{CONSTRAINT_NAME}'
            """
        )
    ).fetchone()
    if exists:
        op.drop_constraint(
            CONSTRAINT_NAME,
            "product_assets",
            type_="unique",
        )

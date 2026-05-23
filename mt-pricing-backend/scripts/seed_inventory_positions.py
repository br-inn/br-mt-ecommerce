"""Seed inventory_positions desde costs activos existentes (US-INV-01-08).

Idempotente: usa INSERT ... ON CONFLICT (sku, supplier_code, scheme_code) DO NOTHING.
Ejecutar:
    cd mt-pricing-backend
    python -m scripts.seed_inventory_positions
"""

from __future__ import annotations

import asyncio
import logging
import sys

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import get_sessionmaker
from app.db.models.cost import Cost

logger = logging.getLogger("seed_inventory_positions")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

_INSERT_SQL = text(
    """
    INSERT INTO inventory_positions
        (sku, supplier_code, scheme_code, qty_on_hand, map_aed, last_updated_at)
    VALUES
        (:sku, :supplier_code, :scheme_code, 0, :map_aed, :last_updated_at)
    ON CONFLICT (sku, supplier_code, scheme_code) DO NOTHING
    """
)


async def seed(session: AsyncSession) -> tuple[int, int]:
    """Siembra inventory_positions desde costs activos.

    Returns:
        (seeded, skipped) — counts de filas insertadas y omitidas.
    """
    stmt = select(Cost).where(Cost.status == "active")
    result = await session.execute(stmt)
    costs = result.scalars().all()

    seeded = 0
    skipped_null = 0
    skipped_conflict = 0

    for cost in costs:
        if cost.scheme_landed_aed is None:
            logger.warning(
                "Skipping cost id=%s sku=%s scheme=%s — scheme_landed_aed is NULL",
                cost.id,
                cost.sku,
                cost.scheme_code,
            )
            skipped_null += 1
            continue

        # costs.supplier_code puede ser NULL para costes globales sin proveedor asignado.
        # inventory_positions tiene una UNIQUE constraint sobre (sku, supplier_code,
        # scheme_code) que no tolera NULLs duplicados en Postgres. Usamos '__default__'
        # como centinela para representar "sin proveedor específico" manteniendo la
        # unicidad garantizada por la constraint.
        supplier_code = cost.supplier_code if cost.supplier_code else "__default__"

        result_insert = await session.execute(
            _INSERT_SQL,
            {
                "sku": cost.sku,
                "supplier_code": supplier_code,
                "scheme_code": cost.scheme_code,
                "map_aed": cost.scheme_landed_aed,
                "last_updated_at": cost.created_at,
            },
        )
        if result_insert.rowcount == 1:
            seeded += 1
        else:
            skipped_conflict += 1

    await session.commit()

    total_skipped = skipped_null + skipped_conflict
    return seeded, total_skipped


async def _main() -> None:
    sm = get_sessionmaker()
    async with sm() as session:
        seeded, skipped = await seed(session)
    logger.info("Seeded %d inventory positions from existing costs (skipped %d)", seeded, skipped)
    print(f"Seeded {seeded} inventory positions, skipped {skipped} (already existed)")


if __name__ == "__main__":
    try:
        asyncio.run(_main())
    except Exception as exc:
        logger.exception("seed_inventory_positions failed")
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

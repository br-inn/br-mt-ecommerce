"""Admin API — operaciones de mantenimiento y seed (US-INV-01-08).

Endpoints:
- POST /admin/inventory/seed-from-costs — idempotente, siembra inventory_positions
  desde costs activos. Rol `admin` requerido.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_role
from app.db.models.cost import Cost
from app.db.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

_INSERT_SQL = text(
    """
    INSERT INTO inventory_positions
        (sku, supplier_code, scheme_code, qty_on_hand, map_aed, last_updated_at)
    VALUES
        (:sku, :supplier_code, :scheme_code, 0, :map_aed, :last_updated_at)
    ON CONFLICT (sku, supplier_code, scheme_code) DO NOTHING
    """
)


class SeedInventoryResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    seeded: int
    skipped: int
    total_costs: int


@router.post(
    "/inventory/seed-from-costs",
    response_model=SeedInventoryResponse,
    summary="Seed inventory_positions desde costs activos",
)
async def seed_inventory_from_costs(
    current_user: Annotated[User, Depends(require_role("admin"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SeedInventoryResponse:
    """Idempotente. Siembra inventory_positions desde costs vigentes hoy."""
    today = func.current_date()
    stmt = select(Cost).where(
        Cost.valid_from <= today,
        (Cost.valid_to.is_(None)) | (Cost.valid_to >= today),
    )
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

        insert_result = await session.execute(
            _INSERT_SQL,
            {
                "sku": cost.sku,
                "supplier_code": supplier_code,
                "scheme_code": cost.scheme_code,
                "map_aed": cost.scheme_landed_aed,
                "last_updated_at": cost.created_at,
            },
        )
        if insert_result.rowcount == 1:
            seeded += 1
        else:
            skipped_conflict += 1

    total_skipped = skipped_null + skipped_conflict
    logger.info(
        "seed_inventory_from_costs: seeded=%d skipped=%d total=%d",
        seeded,
        total_skipped,
        len(costs),
    )
    return SeedInventoryResponse(
        seeded=seeded,
        skipped=total_skipped,
        total_costs=len(costs),
    )

"""Inventory Positions API — EP-INV-01 (US-INV-01-05).

Endpoints de consulta (solo lectura):
- GET /inventory/positions             — lista con filtros
- GET /inventory/positions/{sku}       — posiciones por SKU
- GET /inventory/positions/{sku}/map-history — historial MAP
- GET /inventory/summary               — KPIs agregados

Permiso requerido: purchases:write (mismo rol que GRs y POs).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_permissions
from app.db.models.user import User
from app.repositories.inventory import InventoryRepository
from app.schemas.inventory import (
    InventoryPositionRead,
    InventorySummary,
    MAPHistoryPoint,
)
from app.schemas.common import ProblemDetails  # noqa: F401 — importado para openapi

router = APIRouter(prefix="/inventory", tags=["inventory"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _repo(session: AsyncSession = Depends(get_db_session)) -> InventoryRepository:
    return InventoryRepository(session)


# ---------------------------------------------------------------------------
# GET /inventory/positions
# ---------------------------------------------------------------------------


@router.get(
    "/positions",
    response_model=list[InventoryPositionRead],
    summary="Listar posiciones de inventario con filtros",
    operation_id="inventoryPositionsList",
)
async def list_positions(
    sku: Annotated[str | None, Query(max_length=200)] = None,
    supplier_code: Annotated[str | None, Query(max_length=64)] = None,
    scheme_code: Annotated[str | None, Query(max_length=32)] = None,
    has_stock: Annotated[bool | None, Query()] = None,
    _user: User = Depends(require_permissions("purchases:write")),
    repo: InventoryRepository = Depends(_repo),
) -> list[InventoryPositionRead]:
    return await repo.list_positions(
        sku=sku,
        supplier_code=supplier_code,
        scheme_code=scheme_code,
        has_stock=has_stock,
    )


# ---------------------------------------------------------------------------
# GET /inventory/positions/{sku}
# ---------------------------------------------------------------------------


@router.get(
    "/positions/{sku}",
    response_model=list[InventoryPositionRead],
    summary="Posiciones de inventario para un SKU (todas las combinaciones)",
    operation_id="inventoryPositionsBySku",
)
async def get_positions_by_sku(
    sku: str,
    _user: User = Depends(require_permissions("purchases:write")),
    repo: InventoryRepository = Depends(_repo),
) -> list[InventoryPositionRead]:
    return await repo.get_positions_by_sku(sku)


# ---------------------------------------------------------------------------
# GET /inventory/positions/{sku}/map-history
# ---------------------------------------------------------------------------


@router.get(
    "/positions/{sku}/map-history",
    response_model=list[MAPHistoryPoint],
    summary="Historial de cambios MAP para un SKU",
    operation_id="inventoryMAPHistory",
)
async def get_map_history(
    sku: str,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    _user: User = Depends(require_permissions("purchases:write")),
    repo: InventoryRepository = Depends(_repo),
) -> list[MAPHistoryPoint]:
    return await repo.get_map_history(sku, limit=limit)


# ---------------------------------------------------------------------------
# GET /inventory/summary
# ---------------------------------------------------------------------------


@router.get(
    "/summary",
    response_model=InventorySummary,
    summary="KPIs agregados de inventario",
    operation_id="inventorySummary",
)
async def get_summary(
    _user: User = Depends(require_permissions("purchases:write")),
    repo: InventoryRepository = Depends(_repo),
) -> InventorySummary:
    return await repo.get_summary()

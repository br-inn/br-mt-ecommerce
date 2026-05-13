"""Inventory API — EP-INV-01 + EP-ERP-02.

EP-INV-01 (solo lectura):
  GET  /inventory/positions             — lista con filtros 5D
  GET  /inventory/positions/{sku}       — posiciones por SKU
  GET  /inventory/positions/{sku}/map-history
  GET  /inventory/positions/{sku}/availability — solo unrestricted
  GET  /inventory/summary

US-ERP-02-01 (Movement Types + Movements):
  GET  /inventory/movement-types
  POST /inventory/movements
  GET  /inventory/movements
  POST /inventory/movements/{id}/reverse

US-ERP-02-03 (Lots):
  GET   /inventory/lots
  GET   /inventory/lots/{lot_id}
  PATCH /inventory/lots/{lot_id}/quality-status
  GET   /inventory/lots/{lot_id}/traceability
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_permissions
from app.db.models.user import User
from app.repositories.inventory import InventoryRepository
from app.schemas.common import ProblemDetails  # noqa: F401 — importado para openapi
from app.schemas.inventory import (
    InventoryAvailabilityRead,
    InventoryLotQualityPatch,
    InventoryLotRead,
    InventoryPositionRead,
    InventorySummary,
    LotTraceabilityRead,
    MAPHistoryPoint,
    StockMovementCreate,
    StockMovementRead,
    StockMovementTypeRead,
)

router = APIRouter(prefix="/inventory", tags=["inventory"])


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
    stock_type: Annotated[str | None, Query(max_length=32)] = None,
    warehouse_id: Annotated[UUID | None, Query()] = None,
    zone_id: Annotated[UUID | None, Query()] = None,
    _user: User = Depends(require_permissions("purchases:write")),
    repo: InventoryRepository = Depends(_repo),
) -> list[InventoryPositionRead]:
    return await repo.list_positions(
        sku=sku,
        supplier_code=supplier_code,
        scheme_code=scheme_code,
        has_stock=has_stock,
        stock_type=stock_type,
        warehouse_id=warehouse_id,
        zone_id=zone_id,
    )


# ---------------------------------------------------------------------------
# GET /inventory/positions/{sku}
# ---------------------------------------------------------------------------


@router.get(
    "/positions/{sku}",
    response_model=list[InventoryPositionRead],
    summary="Posiciones de inventario para un SKU",
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
# GET /inventory/positions/{sku}/availability
# ---------------------------------------------------------------------------


@router.get(
    "/positions/{sku}/availability",
    response_model=list[InventoryAvailabilityRead],
    summary="Stock disponible (unrestricted) para un SKU por almacén",
    operation_id="inventoryAvailability",
)
async def get_availability(
    sku: str,
    _user: User = Depends(require_permissions("purchases:write")),
    repo: InventoryRepository = Depends(_repo),
) -> list[InventoryAvailabilityRead]:
    return await repo.get_availability(sku)


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


# ---------------------------------------------------------------------------
# US-ERP-02-01: Movement Types
# ---------------------------------------------------------------------------


@router.get(
    "/movement-types",
    response_model=list[StockMovementTypeRead],
    summary="Catálogo de tipos de movimiento SAP-MM",
    operation_id="inventoryMovementTypes",
)
async def list_movement_types(
    _user: User = Depends(require_permissions("purchases:write")),
    repo: InventoryRepository = Depends(_repo),
) -> list[StockMovementTypeRead]:
    return await repo.list_movement_types()


# ---------------------------------------------------------------------------
# US-ERP-02-01: Movements
# ---------------------------------------------------------------------------


@router.get(
    "/movements",
    response_model=list[StockMovementRead],
    summary="Movimientos de stock recientes",
    operation_id="inventoryMovementsList",
)
async def list_movements(
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    _user: User = Depends(require_permissions("purchases:write")),
    repo: InventoryRepository = Depends(_repo),
) -> list[StockMovementRead]:
    return await repo.list_movements(limit=limit)


@router.post(
    "/movements",
    response_model=StockMovementRead,
    status_code=201,
    summary="Crear movimiento de stock",
    operation_id="inventoryMovementsCreate",
)
async def create_movement(
    payload: StockMovementCreate,
    user: User = Depends(require_permissions("purchases:write")),
    repo: InventoryRepository = Depends(_repo),
) -> StockMovementRead:
    return await repo.create_movement(payload, posted_by=user.id)


@router.post(
    "/movements/{movement_id}/reverse",
    response_model=StockMovementRead,
    status_code=201,
    summary="Reversar un movimiento de stock",
    operation_id="inventoryMovementsReverse",
)
async def reverse_movement(
    movement_id: UUID,
    user: User = Depends(require_permissions("purchases:write")),
    repo: InventoryRepository = Depends(_repo),
) -> StockMovementRead:
    return await repo.reverse_movement(movement_id, posted_by=user.id)


# ---------------------------------------------------------------------------
# US-ERP-02-03: Lots
# ---------------------------------------------------------------------------


@router.get(
    "/lots",
    response_model=list[InventoryLotRead],
    summary="Listar lotes de inventario",
    operation_id="inventoryLotsList",
)
async def list_lots(
    product_id: Annotated[UUID | None, Query()] = None,
    quality_status: Annotated[str | None, Query(max_length=32)] = None,
    _user: User = Depends(require_permissions("purchases:write")),
    repo: InventoryRepository = Depends(_repo),
) -> list[InventoryLotRead]:
    return await repo.list_lots(product_id=product_id, quality_status=quality_status)


@router.get(
    "/lots/{lot_id}",
    response_model=InventoryLotRead,
    summary="Detalle de un lote",
    operation_id="inventoryLotDetail",
)
async def get_lot(
    lot_id: UUID,
    _user: User = Depends(require_permissions("purchases:write")),
    repo: InventoryRepository = Depends(_repo),
) -> InventoryLotRead:
    return await repo.get_lot(lot_id)


@router.patch(
    "/lots/{lot_id}/quality-status",
    response_model=InventoryLotRead,
    summary="Cambiar estado de calidad de un lote",
    operation_id="inventoryLotQualityStatus",
)
async def patch_lot_quality(
    lot_id: UUID,
    payload: InventoryLotQualityPatch,
    _user: User = Depends(require_permissions("purchases:write")),
    repo: InventoryRepository = Depends(_repo),
) -> InventoryLotRead:
    return await repo.patch_lot_quality(lot_id, payload.quality_status)


@router.get(
    "/lots/{lot_id}/traceability",
    response_model=LotTraceabilityRead,
    summary="Trazabilidad completa de un lote (upstream + downstream)",
    operation_id="inventoryLotTraceability",
)
async def get_lot_traceability(
    lot_id: UUID,
    _user: User = Depends(require_permissions("purchases:write")),
    repo: InventoryRepository = Depends(_repo),
) -> LotTraceabilityRead:
    return await repo.get_lot_traceability(lot_id)

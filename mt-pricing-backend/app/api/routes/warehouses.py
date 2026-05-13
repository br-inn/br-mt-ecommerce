"""Warehouses API — US-ERP-02-04.

Jerarquía Warehouse → Zone → Location:
  GET  /warehouses
  POST /warehouses
  GET  /warehouses/{warehouse_id}/zones
  POST /warehouses/{warehouse_id}/zones
  GET  /warehouses/{warehouse_id}/zones/{zone_id}/locations
  POST /warehouses/{warehouse_id}/zones/{zone_id}/locations
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_permissions
from app.db.models.user import User
from app.repositories.inventory import InventoryRepository
from app.schemas.inventory import (
    WarehouseCreate,
    WarehouseLocationCreate,
    WarehouseLocationRead,
    WarehouseRead,
    WarehouseZoneCreate,
    WarehouseZoneRead,
)

router = APIRouter(prefix="/warehouses", tags=["warehouses"])


def _repo(session: AsyncSession = Depends(get_db_session)) -> InventoryRepository:
    return InventoryRepository(session)


# ---------------------------------------------------------------------------
# Warehouses
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=list[WarehouseRead],
    summary="Listar almacenes",
    operation_id="warehousesList",
)
async def list_warehouses(
    _user: User = Depends(require_permissions("purchases:write")),
    repo: InventoryRepository = Depends(_repo),
) -> list[WarehouseRead]:
    return await repo.list_warehouses()


@router.post(
    "",
    response_model=WarehouseRead,
    status_code=201,
    summary="Crear almacén",
    operation_id="warehousesCreate",
)
async def create_warehouse(
    payload: WarehouseCreate,
    _user: User = Depends(require_permissions("purchases:write")),
    repo: InventoryRepository = Depends(_repo),
) -> WarehouseRead:
    return await repo.create_warehouse(payload)


# ---------------------------------------------------------------------------
# Zones
# ---------------------------------------------------------------------------


@router.get(
    "/{warehouse_id}/zones",
    response_model=list[WarehouseZoneRead],
    summary="Listar zonas de un almacén",
    operation_id="warehouseZonesList",
)
async def list_zones(
    warehouse_id: UUID,
    _user: User = Depends(require_permissions("purchases:write")),
    repo: InventoryRepository = Depends(_repo),
) -> list[WarehouseZoneRead]:
    return await repo.list_zones(warehouse_id)


@router.post(
    "/{warehouse_id}/zones",
    response_model=WarehouseZoneRead,
    status_code=201,
    summary="Crear zona en un almacén",
    operation_id="warehouseZonesCreate",
)
async def create_zone(
    warehouse_id: UUID,
    payload: WarehouseZoneCreate,
    _user: User = Depends(require_permissions("purchases:write")),
    repo: InventoryRepository = Depends(_repo),
) -> WarehouseZoneRead:
    return await repo.create_zone(warehouse_id, payload)


# ---------------------------------------------------------------------------
# Locations
# ---------------------------------------------------------------------------


@router.get(
    "/{warehouse_id}/zones/{zone_id}/locations",
    response_model=list[WarehouseLocationRead],
    summary="Listar ubicaciones (bins) de una zona",
    operation_id="warehouseLocationsList",
)
async def list_locations(
    warehouse_id: UUID,
    zone_id: UUID,
    _user: User = Depends(require_permissions("purchases:write")),
    repo: InventoryRepository = Depends(_repo),
) -> list[WarehouseLocationRead]:
    return await repo.list_locations(zone_id)


@router.post(
    "/{warehouse_id}/zones/{zone_id}/locations",
    response_model=WarehouseLocationRead,
    status_code=201,
    summary="Crear ubicación (bin) en una zona",
    operation_id="warehouseLocationsCreate",
)
async def create_location(
    warehouse_id: UUID,
    zone_id: UUID,
    payload: WarehouseLocationCreate,
    _user: User = Depends(require_permissions("purchases:write")),
    repo: InventoryRepository = Depends(_repo),
) -> WarehouseLocationRead:
    return await repo.create_location(zone_id, payload)

"""Admin manufacturers whitelist routes — US-F15-02-03.

Endpoints:
- ``GET   /admin/manufacturers-whitelist``         — lista registros (paginado).
- ``POST  /admin/manufacturers-whitelist``         — crear fabricante.
- ``PATCH /admin/manufacturers-whitelist/{id}/toggle`` — activar/desactivar.

RBAC: perm ``manufacturers:manage`` → ``ti_integracion``, ``admin``.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_permissions
from app.db.models.comparator import ManufacturerWhitelist
from app.db.models.user import User

router = APIRouter(prefix="/admin/manufacturers-whitelist", tags=["Manufacturers Whitelist Admin"])


# ---------------------------------------------------------------------------
# Schemas (inline — tabla interna admin, sin cliente externo)
# ---------------------------------------------------------------------------


class ManufacturerWhitelistItem(BaseModel):
    """Representación pública de un registro de manufacturers_whitelist."""

    id: uuid.UUID
    manufacturer_name: str
    canonical_domains: list[str]
    brand_aliases: list[str]
    confidence: float
    active: bool

    model_config = {"from_attributes": True}


class ManufacturerWhitelistListResponse(BaseModel):
    items: list[ManufacturerWhitelistItem]
    total: int
    limit: int
    offset: int


class ManufacturerWhitelistCreateRequest(BaseModel):
    manufacturer_name: str = Field(..., max_length=128)
    canonical_domains: list[str] = Field(default_factory=list)
    brand_aliases: list[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    active: bool = True


class ManufacturerWhitelistToggleResponse(BaseModel):
    id: uuid.UUID
    manufacturer_name: str
    active: bool


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=ManufacturerWhitelistListResponse,
    summary="List manufacturers whitelist (admin only — manufacturers:manage)",
)
async def list_manufacturers(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    _user: User = Depends(require_permissions("manufacturers:manage")),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    active_only: bool = Query(default=True),
) -> ManufacturerWhitelistListResponse:
    stmt = select(ManufacturerWhitelist)
    if active_only:
        stmt = stmt.where(ManufacturerWhitelist.active.is_(True))
    stmt_count = select(func.count()).select_from(stmt.subquery())

    total_result = await session.execute(stmt_count)
    total = total_result.scalar_one()

    stmt = stmt.order_by(ManufacturerWhitelist.manufacturer_name).limit(limit).offset(offset)
    rows_result = await session.execute(stmt)
    rows = rows_result.scalars().all()

    return ManufacturerWhitelistListResponse(
        items=[ManufacturerWhitelistItem.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "",
    response_model=ManufacturerWhitelistItem,
    status_code=status.HTTP_201_CREATED,
    summary="Crear fabricante en whitelist (admin only — manufacturers:manage)",
)
async def create_manufacturer(
    payload: ManufacturerWhitelistCreateRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    _user: User = Depends(require_permissions("manufacturers:manage")),
) -> ManufacturerWhitelistItem:
    # Verificar unicidad
    existing = await session.execute(
        select(ManufacturerWhitelist).where(
            ManufacturerWhitelist.manufacturer_name == payload.manufacturer_name
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"manufacturer_name '{payload.manufacturer_name}' ya existe en whitelist",
        )

    row = ManufacturerWhitelist(
        manufacturer_name=payload.manufacturer_name,
        canonical_domains=payload.canonical_domains,
        brand_aliases=payload.brand_aliases,
        confidence=payload.confidence,
        active=payload.active,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    await session.commit()
    return ManufacturerWhitelistItem.model_validate(row)


@router.patch(
    "/{manufacturer_id}/toggle",
    response_model=ManufacturerWhitelistToggleResponse,
    summary="Activar/desactivar fabricante (admin only — manufacturers:manage)",
)
async def toggle_manufacturer(
    manufacturer_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    _user: User = Depends(require_permissions("manufacturers:manage")),
) -> ManufacturerWhitelistToggleResponse:
    result = await session.execute(
        select(ManufacturerWhitelist).where(ManufacturerWhitelist.id == manufacturer_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"manufacturer_id '{manufacturer_id}' no encontrado",
        )
    row.active = not row.active
    await session.flush()
    await session.commit()
    return ManufacturerWhitelistToggleResponse(
        id=row.id,
        manufacturer_name=row.manufacturer_name,
        active=row.active,
    )

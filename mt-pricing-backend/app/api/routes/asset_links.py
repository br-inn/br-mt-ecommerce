"""Asset links API — Fase 4 polymorphic asset references (PDF §11).

Endpoints:
- GET    /api/v1/{owner_type}/{owner_id}/asset-links  (lista links del owner)
- POST   /api/v1/asset-links                          (crea link)
- DELETE /api/v1/asset-links/{link_id}                (borra link, 204)
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_permissions
from app.db.models.user import User
from app.schemas.asset_links import (
    AssetLinkCreate,
    AssetLinkOwnerType,
    AssetLinkResponse,
)
from app.schemas.common import ProblemDetails
from app.services.assets.asset_link_service import (
    AssetLinkDomainError,
    AssetLinkService,
)

router = APIRouter(tags=["asset-links"])


def get_asset_link_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AssetLinkService:
    return AssetLinkService(session)


def _raise_domain(err: AssetLinkDomainError) -> None:
    raise HTTPException(
        status_code=err.status_code,
        detail={"type": "about:blank", "title": err.code, "detail": err.message},
    )


# ---------------------------------------------------------------------------
# GET /{owner_type}/{owner_id}/asset-links
# ---------------------------------------------------------------------------
@router.get(
    "/{owner_type}/{owner_id}/asset-links",
    response_model=list[AssetLinkResponse],
    summary="Lista assets vinculados a un owner polimórfico",
    responses={404: {"model": ProblemDetails}},
)
async def list_asset_links_for_owner(
    owner_type: Annotated[AssetLinkOwnerType, Path()],
    owner_id: Annotated[str, Path(min_length=1, max_length=256)],
    _user: User = Depends(require_permissions("products:read")),
    service: AssetLinkService = Depends(get_asset_link_service),
) -> list[AssetLinkResponse]:
    rows = await service.list_links_for_owner(owner_type.value, owner_id)
    return [AssetLinkResponse.model_validate(r) for r in rows]


# ---------------------------------------------------------------------------
# POST /asset-links
# ---------------------------------------------------------------------------
@router.post(
    "/asset-links",
    response_model=AssetLinkResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crea un link polimórfico asset ↔ owner",
    responses={409: {"model": ProblemDetails}, 404: {"model": ProblemDetails}},
)
async def create_asset_link(
    data: AssetLinkCreate,
    _user: User = Depends(require_permissions("products:write")),
    service: AssetLinkService = Depends(get_asset_link_service),
) -> AssetLinkResponse:
    try:
        row = await service.create_link(
            asset_id=data.asset_id,
            owner_type=data.owner_type.value,
            owner_id=data.owner_id,
            role=data.role.value,
            order_index=data.order_index,
        )
    except AssetLinkDomainError as e:
        _raise_domain(e)
    return AssetLinkResponse.model_validate(row)


# ---------------------------------------------------------------------------
# DELETE /asset-links/{link_id}  (204)
# ---------------------------------------------------------------------------
@router.delete(
    "/asset-links/{link_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Elimina un link polimórfico",
    responses={404: {"model": ProblemDetails}},
)
async def delete_asset_link(
    link_id: UUID,
    _user: User = Depends(require_permissions("products:write")),
    service: AssetLinkService = Depends(get_asset_link_service),
):
    try:
        await service.delete_link(link_id)
    except AssetLinkDomainError as e:
        _raise_domain(e)

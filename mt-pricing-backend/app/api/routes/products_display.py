"""Products display API — Wave 11 Stage 3.

Endpoints (mounted at ``/products`` by ``routes/__init__.py``):

- ``GET    /{sku}/effective-display``  (products:read)  — tags + certs efectivos.
- ``PUT    /{sku}/display-pair``       (products:write) — set color-pair simétrico.
- ``DELETE /{sku}/display-pair``       (products:write) — clear pareja (idempotente).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_permissions
from app.db.models.user import User
from app.schemas.common import ProblemDetails
from app.schemas.products_display import (
    CertificationRef,
    DisplayPairSetRequest,
    EffectiveDisplayResponse,
)
from app.services.products.display_pair_service import DisplayPairService
from app.services.products.effective_display_service import EffectiveDisplayService
from app.services.vocabularies.vocabulary_service import VocabularyDomainError

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
products_display_router = APIRouter(tags=["products:display"])


# ---------------------------------------------------------------------------
# DI factories
# ---------------------------------------------------------------------------
def get_effective_display_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> EffectiveDisplayService:
    return EffectiveDisplayService(session)


def get_display_pair_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DisplayPairService:
    return DisplayPairService(session)


# ---------------------------------------------------------------------------
# Error helper
# ---------------------------------------------------------------------------
def _raise_domain(e: VocabularyDomainError) -> None:
    raise HTTPException(
        status_code=e.status_code,
        detail=ProblemDetails(
            title=e.message, status=e.status_code, type=e.code
        ).model_dump(),
    )


# ===========================================================================
# Endpoints
# ===========================================================================
@products_display_router.get(
    "/{sku}/effective-display",
    response_model=EffectiveDisplayResponse,
    summary="Tags + certificaciones efectivos (serie defaults ∪ product overrides)",
    responses={404: {"model": ProblemDetails}},
)
async def get_effective_display(
    sku: str,
    _user: User = Depends(require_permissions("products:read")),
    service: EffectiveDisplayService = Depends(get_effective_display_service),
) -> EffectiveDisplayResponse:
    try:
        data = await service.compute(sku)
    except VocabularyDomainError as e:
        _raise_domain(e)
    return EffectiveDisplayResponse(
        tags=data["tags"],
        certifications=[CertificationRef(**c) for c in data["certifications"]],
    )


@products_display_router.put(
    "/{sku}/display-pair",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Establece la pareja de display (color sibling) simétricamente",
    responses={
        400: {"model": ProblemDetails},
        404: {"model": ProblemDetails},
    },
)
async def set_display_pair(
    sku: str,
    body: DisplayPairSetRequest,
    _user: User = Depends(require_permissions("products:write")),
    service: DisplayPairService = Depends(get_display_pair_service),
):
    try:
        await service.set_pair(sku, body.paired_sku)
    except VocabularyDomainError as e:
        _raise_domain(e)


@products_display_router.delete(
    "/{sku}/display-pair",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Limpia el emparejamiento de display (idempotente)",
    responses={404: {"model": ProblemDetails}},
)
async def clear_display_pair(
    sku: str,
    _user: User = Depends(require_permissions("products:write")),
    service: DisplayPairService = Depends(get_display_pair_service),
):
    try:
        await service.clear_pair(sku)
    except VocabularyDomainError as e:
        _raise_domain(e)

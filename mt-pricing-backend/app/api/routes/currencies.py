"""Currencies — API v1 admin (US-1A-05-01-S3).

Endpoints (todos requieren ``currencies:manage`` excepto el GET, que reusa
``fx:read`` ya disponible para todos los roles autenticados):

- ``GET /api/v1/currencies``                — list (todas, incluyendo inactivas)
- ``PATCH /api/v1/currencies/{code}/active`` — activate/deactivate

NO incluye POST/PUT/DELETE en S3 (ver story US-1A-05-01-S3 §Contexto:
"NO permitimos UI de creación de currencies nuevas en S3").
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_permissions
from app.db.models.user import User
from app.schemas.common import ProblemDetails
from app.schemas.currencies import CurrencyActivePatch, CurrencyResponse
from app.services.currencies import CurrencyDomainError, CurrencyService

router = APIRouter(prefix="/currencies", tags=["currencies"])


def get_currency_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> CurrencyService:
    return CurrencyService(session)


def _raise_domain(err: CurrencyDomainError) -> None:
    raise HTTPException(
        status_code=err.status_code,
        detail={"code": err.code, "title": err.message},
    )


@router.get(
    "",
    response_model=list[CurrencyResponse],
    summary="Listar todas las currencies (incluye inactivas)",
)
async def list_currencies(
    _user: User = Depends(require_permissions("fx:read")),
    service: CurrencyService = Depends(get_currency_service),
) -> list[CurrencyResponse]:
    rows = await service.list_all(only_active=False)
    return [CurrencyResponse.model_validate(r) for r in rows]


@router.patch(
    "/{code}/active",
    response_model=CurrencyResponse,
    summary="Activar/desactivar una moneda (RBAC currencies:manage)",
    responses={
        404: {"model": ProblemDetails},
        422: {
            "model": ProblemDetails,
            "description": "Intento de desactivar moneda base",
        },
    },
)
async def patch_currency_active(
    code: Annotated[str, Path(min_length=3, max_length=3, pattern=r"^[A-Za-z]{3}$")],
    data: CurrencyActivePatch,
    user: Annotated[User, Depends(require_permissions("currencies:manage"))],
    service: Annotated[CurrencyService, Depends(get_currency_service)],
) -> CurrencyResponse:
    try:
        currency = await service.set_active(
            code, active=data.active, actor=user, reason=data.reason
        )
    except CurrencyDomainError as exc:
        _raise_domain(exc)
    return CurrencyResponse.model_validate(currency)

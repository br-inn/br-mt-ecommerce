"""FX Rates — API v1 (US-1A-05-03).

Endpoints:

- ``GET /api/v1/fx-rates``  — listado paginado simple (filtro from/to/active)
- ``POST /api/v1/fx-rates`` — crea rate (TI/admin); el trigger SQL cierra el
                              previo y bloquea retroactivos sin flag.

RBAC:
- read → ``fx:read`` (cualquier rol autenticado)
- write → ``fx:manage`` (TI/admin)

Convivencia con el endpoint legacy ``/api/v1/pricing/fx-rates``: éste se mantiene
en S3 para no romper el frontend ``/admin/divisas`` antiguo, pero los nuevos
clientes (``/admin/fx-rates``) deben usar este path raíz.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_permissions
from app.db.models.user import User
from app.schemas.common import ProblemDetails
from app.schemas.fx_rates import FXRateCreate, FXRateResponse
from app.services.fx import FXRateDomainError, FXRateService

router = APIRouter(prefix="/fx-rates", tags=["fx-rates"])


def get_fx_rate_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> FXRateService:
    return FXRateService(session)


def _raise_domain(err: FXRateDomainError) -> None:
    raise HTTPException(
        status_code=err.status_code,
        detail={"code": err.code, "title": err.message},
    )


@router.get(
    "",
    response_model=list[FXRateResponse],
    summary="Lista FX rates (más reciente primero)",
    description=(
        "Devuelve la lista de FX rates con filtros opcionales por par de "
        "monedas y flag `only_active`. Ordenado por effective_from desc."
    ),
    operation_id="fxRatesList",
)
async def list_fx_rates(
    from_currency: Annotated[
        str | None, Query(min_length=3, max_length=3, pattern=r"^[A-Za-z]{3}$")
    ] = None,
    to_currency: Annotated[
        str | None, Query(min_length=3, max_length=3, pattern=r"^[A-Za-z]{3}$")
    ] = None,
    only_active: Annotated[bool, Query()] = False,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    _user: User = Depends(require_permissions("fx:read")),
    service: FXRateService = Depends(get_fx_rate_service),
) -> list[FXRateResponse]:
    rows = await service.list_rates(
        from_code=from_currency,
        to_code=to_currency,
        only_active=only_active,
        limit=limit,
    )
    return [FXRateResponse.model_validate(r) for r in rows]


@router.post(
    "",
    response_model=FXRateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crea un FX rate (TI/admin) — trigger cierra el rate previo",
    description=(
        "Crea un nuevo FX rate. El trigger SQL cierra automáticamente el "
        "rate previo. Permite retroactivo sólo con flag explícito."
    ),
    operation_id="fxRatesCreate",
    responses={
        403: {"model": ProblemDetails, "description": "Permission denied (fx:manage)"},
        422: {
            "model": ProblemDetails,
            "description": (
                "Validación: rate<=0, retroactivo sin flag, mismo effective_from, "
                "moneda inválida, etc."
            ),
        },
    },
)
async def create_fx_rate(
    data: FXRateCreate,
    user: Annotated[User, Depends(require_permissions("fx:manage"))],
    service: Annotated[FXRateService, Depends(get_fx_rate_service)],
) -> FXRateResponse:
    try:
        new_rate = await service.create_rate(
            from_code=data.from_code,
            to_code=data.to_code,
            rate=data.rate,
            effective_from=data.effective_from,
            source=data.source,
            actor=user,
            allow_retroactive=data.allow_retroactive,
            reason=data.reason,
        )
    except FXRateDomainError as exc:
        _raise_domain(exc)
    return FXRateResponse.model_validate(new_rate)

"""Schemes API v1 — exposición de cost schemes (US-1A-04-S4).

Endpoints:
- GET /schemes           — lista todos los schemes activos con su template.
- GET /schemes/{code}    — scheme concreto por código (FBA, FBM, …).

RBAC: `products:read` (lectura de catálogo — mismo nivel que costs:read para
no añadir un permiso nuevo; los schemes son datos de configuración estática).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_permissions
from app.db.models.cost_scheme import CostScheme
from app.db.models.user import User
from app.schemas.common import ProblemDetails
from app.schemas.schemes import CostComponentsTemplate, SchemeResponse

router = APIRouter(prefix="/schemes", tags=["schemes"])


def _to_response(row: CostScheme) -> SchemeResponse:
    """Convierte ORM row → SchemeResponse con template tipado."""
    raw: dict = row.cost_components_template or {}
    template = CostComponentsTemplate(
        required=raw.get("required", []),
        optional=raw.get("optional", []),
    )
    return SchemeResponse(
        code=row.code,
        name=row.name,
        description=row.description,
        cost_components_template=template,
        active=row.active,
    )


# ---------------------------------------------------------------------------
# GET /schemes — lista activos
# ---------------------------------------------------------------------------
@router.get(
    "",
    response_model=list[SchemeResponse],
    summary="Lista todos los cost schemes activos",
    description=(
        "Devuelve la lista de schemes de coste activos con su "
        "`cost_components_template` (required + optional fields). "
        "Cache: los schemes son inmutables en producción — el frontend "
        "puede usar `staleTime` largo (≥ 1 hora)."
    ),
    operation_id="schemesList",
)
async def list_schemes(
    _user: User = Depends(require_permissions("products:read")),
    session: AsyncSession = Depends(get_db_session),
) -> list[SchemeResponse]:
    stmt = select(CostScheme).where(CostScheme.active.is_(True)).order_by(CostScheme.code)
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [_to_response(r) for r in rows]


# ---------------------------------------------------------------------------
# GET /schemes/{code} — scheme individual
# ---------------------------------------------------------------------------
@router.get(
    "/{code}",
    response_model=SchemeResponse,
    summary="Obtener scheme por código",
    description=(
        "Devuelve un scheme individual por su código (FBA/FBM/DIRECT_B2C/"
        "DIRECT_B2B/MARKETPLACE). 404 si el código no existe."
    ),
    operation_id="schemesGet",
    responses={404: {"model": ProblemDetails, "description": "Scheme no existe"}},
)
async def get_scheme(
    code: str,
    _user: User = Depends(require_permissions("products:read")),
    session: AsyncSession = Depends(get_db_session),
) -> SchemeResponse:
    stmt = select(CostScheme).where(CostScheme.code == code.upper())
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "scheme_not_found", "title": f"Scheme '{code}' no existe"},
        )
    return _to_response(row)


__all__ = ["router"]

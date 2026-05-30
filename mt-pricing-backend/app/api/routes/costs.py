"""Costs API v1 — motor de costes (US-1A-04-03).

Endpoints (canónicos NUEVOS):
- POST  /costs                             — crea cost (versionado v1).
- PUT   /costs/{id}                        — versionado: anterior superseded,
                                              nueva con version+1.
- GET   /products/{sku}/costs              — costes activos del SKU (todas las
                                              schemes con breakdown desglosado).
- GET   /costs/missing?scheme_code=FBA     — SKUs sin coste activo para scheme.

Endpoints LEGACY (mantenidos para compat S2 frontend):
- GET    /costs?product_sku=&scheme=&supplier=&cursor=&limit=&include_total=
- GET    /costs/{id}
- PATCH  /costs/{id}                       — DEPRECATED (usar PUT versionado)
- DELETE /costs/{id}                       — hard delete (admin only,
                                              compat tests S2)

Convenciones (alineadas con `pricing.py`):
- Cursor-based pagination keyset (UUID id ASC).
- RBAC: read=`costs:read`, write=`costs:write`.
- Errores → ProblemDetails RFC 7807.

Cambios S3 vs S2:
- POST ahora valida breakdown contra `cost_components_template`
  (US-1A-04-03 AC#2 #3).
- POST devuelve `CostCreatedResponse` con `warnings` (campos no declarados).
- PUT versionado nuevo (US-1A-04-03 AC#6).
- `/products/{sku}/costs` nuevo (US-1A-04-03 AC#5).
- `/costs/missing` nuevo (US-1A-04-03 AC#4).
"""

from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_permissions
from app.api.pagination import decode_cursor, encode_cursor
from app.db.models.user import User
from app.repositories.audit import AuditRepository
from app.repositories.pricing import CostRepository
from app.schemas.common import Cursor, Pagination, ProblemDetails
from app.schemas.costs import (
    CostBreakdownValidationWarning,
    CostCloseRequest,
    CostCreate,
    CostCreatedResponse,
    CostMissingSkuItem,
    CostResponse,
    CostUpdate,
)
from app.services.costs.breakdown_validator import (
    BreakdownValidationError,
    MissingRequiredField,
)
from app.services.costs.cost_service import (
    CostNotFound,
    CostRangeOverlap,
    CostService,
    FXRateNotFoundAtEffectiveAt,
    SchemeNotFound,
)

router = APIRouter(prefix="/costs", tags=["costs"])


# ---------------------------------------------------------------------------
# Service factory — overridable in tests via dependency_overrides.
# ---------------------------------------------------------------------------
def get_cost_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> CostService:
    return CostService(session)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _decode_uuid_cursor(cursor: str | None) -> UUID | None:
    if not cursor:
        return None
    payload = decode_cursor(cursor)
    raw = payload.get("id")
    if not raw:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_cursor", "title": "Cursor sin clave 'id'"},
        )
    try:
        return UUID(str(raw))
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_cursor", "title": "Cursor 'id' no es UUID"},
        ) from exc


def _encode_uuid_cursor(value: UUID | None) -> str | None:
    if value is None:
        return None
    return encode_cursor({"id": str(value)})


def _to_response(cost) -> CostResponse:
    """Convierte ORM row → CostResponse (vigencia por rangos + aliases legacy).

    ``valid_from``/``valid_to`` son las columnas reales (DATE). ``effective_at``
    y ``status`` provienen de hybrids del modelo (effective_at == valid_from;
    status derivado por fecha). El campo ``effective_at`` del schema es
    ``datetime`` → lo derivamos de ``valid_from`` (medianoche).
    """
    from datetime import datetime as _dt

    eff = _dt.combine(cost.valid_from, _dt.min.time()) if cost.valid_from else None
    return CostResponse(
        id=cost.id,
        sku=cost.sku,
        scheme_code=cost.scheme_code,
        supplier_code=cost.supplier_code,
        currency_origin=cost.currency_origin,
        fx_rate_id=cost.fx_rate_id,
        breakdown=cost.breakdown or {},
        scheme_landed_aed=cost.scheme_landed_aed,
        valid_from=cost.valid_from,
        valid_to=cost.valid_to,
        effective_at=eff,
        status=cost.status,
        fx_inferred=cost.fx_inferred,
        version=cost.version,
        created_by=cost.created_by,
        updated_by=cost.updated_by,
        created_at=cost.created_at,
        updated_at=cost.updated_at,
        # legacy aliases
        product_sku=cost.sku,
        currency=cost.currency_origin,
        total=cost.scheme_landed_aed,
        fx_at=eff,
    )


# ---------------------------------------------------------------------------
# GET /costs — listado con filtros + paginación (legacy compat)
# ---------------------------------------------------------------------------
@router.get(
    "",
    response_model=Pagination[CostResponse],
    summary="Listar costos con filtros y cursor pagination",
    description=(
        "Lista paginada (cursor UUID-based) de costos con filtros por "
        "product_sku, scheme, supplier. Soporta `include_total=true` para "
        "obtener el count global (más caro)."
    ),
    operation_id="costsList",
)
async def list_costs(
    product_sku: Annotated[str | None, Query(min_length=1, max_length=128)] = None,
    sku: Annotated[str | None, Query(min_length=1, max_length=128)] = None,
    scheme: Annotated[str | None, Query(min_length=2, max_length=32)] = None,
    supplier: Annotated[str | None, Query(min_length=1, max_length=64)] = None,
    valid_on: Annotated[date | None, Query()] = None,
    include_history: Annotated[bool, Query()] = False,
    cursor: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    include_total: Annotated[bool, Query()] = False,
    _user: User = Depends(require_permissions("costs:read")),
    session: AsyncSession = Depends(get_db_session),
) -> Pagination[CostResponse]:
    """Lista costos con vigencia por rangos.

    - ``valid_on`` (ISO date): filtra a costos cuyo rango contiene la fecha
      (``valid_from <= valid_on AND (valid_to IS NULL OR valid_to >= valid_on)``).
    - ``include_history=false`` (default): sólo costos vigentes HOY.
    - ``include_history=true``: todos los rangos (orden por ``valid_from`` desc).
      Si además se pasa ``valid_on``, este filtro tiene prioridad.
    """
    effective_sku = sku or product_sku

    # Resuelve el filtro de vigencia:
    # - include_history=True  → sin filtro (historia completa).
    # - valid_on dado          → ese filtro tiene prioridad.
    # - default                → costes vigentes HOY.
    if include_history and valid_on is None:
        on: date | None = None
    else:
        on = valid_on or date.today()

    repo = CostRepository(session)
    cur = _decode_uuid_cursor(cursor)
    rows, next_cur, total = await repo.list_paginated(
        product_sku=effective_sku,
        scheme_code=scheme,
        supplier_code=supplier,
        valid_on=on,
        cursor=cur,
        limit=limit,
        include_total=include_total,
    )
    return Pagination[CostResponse](
        items=[_to_response(r) for r in rows],
        cursor=Cursor(next=_encode_uuid_cursor(next_cur)),
        page_size=limit,
        total=total,
    )


# ---------------------------------------------------------------------------
# GET /costs/missing — SKUs sin cost activo para scheme (US-1A-04-03 AC#4)
# ---------------------------------------------------------------------------
@router.get(
    "/missing",
    response_model=list[CostMissingSkuItem],
    summary="SKUs sin coste activo para un scheme",
    description=(
        "Devuelve la lista de SKUs activos que NO tienen un cost activo "
        "para el scheme dado (FBA/FBM/DIRECT_B2C/DIRECT_B2B/MARKETPLACE)."
    ),
    operation_id="costsListMissing",
)
async def missing_costs_by_scheme(
    scheme_code: Annotated[str, Query(min_length=2, max_length=32)],
    as_of: Annotated[date | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=5000)] = 1000,
    _user: User = Depends(require_permissions("costs:read")),
    svc: CostService = Depends(get_cost_service),
) -> list[CostMissingSkuItem]:
    skus = await svc.missing_cost_skus(scheme_code, as_of=as_of, limit=limit)
    return [CostMissingSkuItem(sku=s) for s in skus]


# ---------------------------------------------------------------------------
# GET /costs/as-of — coste vigente a una fecha (vigencia por rangos)
# ---------------------------------------------------------------------------
@router.get(
    "/as-of",
    response_model=CostResponse,
    summary="Coste vigente a una fecha dada para sku+scheme(+supplier)",
    description=(
        "Devuelve el coste cuyo rango de vigencia contiene `date` "
        "(`valid_from <= date AND (valid_to IS NULL OR valid_to >= date)`). "
        "404 si no hay coste vigente a esa fecha."
    ),
    operation_id="costsAsOf",
    responses={404: {"model": ProblemDetails}},
)
async def cost_as_of(
    sku: Annotated[str, Query(min_length=1, max_length=128)],
    scheme_code: Annotated[str, Query(min_length=2, max_length=32)],
    on: Annotated[date, Query(alias="date")],
    supplier_code: Annotated[str | None, Query(min_length=1, max_length=64)] = None,
    _user: User = Depends(require_permissions("costs:read")),
    svc: CostService = Depends(get_cost_service),
) -> CostResponse:
    cost = await svc.cost_as_of(
        sku=sku,
        scheme_code=scheme_code,
        supplier_code=supplier_code,
        on=on,
    )
    if cost is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "cost_not_found",
                "title": "No hay coste vigente a esa fecha",
            },
        )
    return _to_response(cost)


# ---------------------------------------------------------------------------
# POST /costs — NUEVO motor (US-1A-04-03)
# ---------------------------------------------------------------------------
@router.post(
    "",
    response_model=CostCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear coste (versionado v1) — valida breakdown vs scheme template",
    description=(
        "Crea un nuevo cost (versión 1). Valida que el breakdown contenga "
        "los campos requeridos por el `cost_components_template` del scheme. "
        "Devuelve warnings por campos no declarados."
    ),
    operation_id="costsCreate",
    responses={
        404: {"model": ProblemDetails, "description": "SKU/Scheme/Supplier inexistente"},
        422: {
            "model": ProblemDetails,
            "description": ("Validación falló (missing required field, fx_rate_not_found, etc.)"),
        },
    },
)
async def create_cost(
    data: CostCreate,
    user: Annotated[User, Depends(require_permissions("costs:write"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    svc: Annotated[CostService, Depends(get_cost_service)],
) -> CostCreatedResponse:
    try:
        result = await svc.create_cost(
            sku=data.sku,
            scheme_code=data.scheme_code,
            supplier_code=data.supplier_code,
            currency_origin=data.currency_origin,
            valid_from=data.valid_from,
            breakdown=data.breakdown,
            actor_id=user.id,
            actor_email=user.email,
            fx_rate_id=data.fx_rate_id,
            fx_inferred=data.fx_inferred,
        )
    except MissingRequiredField as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "code": exc.code,
                "title": "Campo requerido del breakdown ausente",
                "field": exc.field_name,
            },
        ) from exc
    except CostRangeOverlap as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": exc.code,
                "title": "El rango de vigencia solapa otro existente",
            },
        ) from exc
    except FXRateNotFoundAtEffectiveAt as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "code": exc.code,
                "title": "FX no disponible en valid_from",
            },
        ) from exc
    except SchemeNotFound as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": exc.code, "title": "Scheme no existe"},
        ) from exc
    except BreakdownValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": exc.code, "title": str(exc), "field": exc.field_name},
        ) from exc
    except IntegrityError as exc:
        await session.rollback()
        # Map FK violations.
        msg = str(getattr(exc, "orig", exc) or exc).lower()
        if "fx_rate_not_found_at_effective_at" in msg:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "fx_rate_not_found_at_effective_at",
                    "title": "FX no disponible en effective_at",
                },
            ) from exc
        if "products" in msg and "fkey" in msg:
            raise HTTPException(
                status_code=404,
                detail={"code": "product_not_found", "title": "SKU no existe"},
            ) from exc
        if "schemes" in msg and "fkey" in msg:
            raise HTTPException(
                status_code=422,
                detail={"code": "scheme_invalid", "title": "Scheme inválido"},
            ) from exc
        if "suppliers" in msg and "fkey" in msg:
            raise HTTPException(
                status_code=422,
                detail={"code": "supplier_invalid", "title": "Supplier inválido"},
            ) from exc
        if "currencies" in msg and "fkey" in msg:
            raise HTTPException(
                status_code=422,
                detail={"code": "currency_invalid", "title": "Currency inválida"},
            ) from exc
        raise

    return CostCreatedResponse(
        cost=_to_response(result.cost),
        warnings=[
            CostBreakdownValidationWarning(code=w["code"], field=w["field"])
            for w in result.warnings
        ],
    )


async def _apply_in_place_update(
    *,
    cost_id: UUID,
    data: CostUpdate,
    user: User,
    svc: CostService,
) -> CostCreatedResponse:
    """Corrección IN-PLACE compartida por PUT y PATCH /costs/{id}."""
    try:
        result = await svc.update_cost(
            cost_id,
            actor_id=user.id,
            actor_email=user.email,
            breakdown=data.breakdown,
            valid_from=data.valid_from,
            currency_origin=data.currency_origin,
            fx_rate_id=data.fx_rate_id,
            fx_inferred=data.fx_inferred,
        )
    except CostNotFound as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": exc.code, "title": "Coste no existe"},
        ) from exc
    except CostRangeOverlap as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": exc.code,
                "title": "El rango de vigencia solapa otro existente",
            },
        ) from exc
    except MissingRequiredField as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "code": exc.code,
                "title": "Campo requerido del breakdown ausente",
                "field": exc.field_name,
            },
        ) from exc
    except FXRateNotFoundAtEffectiveAt as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": exc.code, "title": "FX no disponible en valid_from"},
        ) from exc

    return CostCreatedResponse(
        cost=_to_response(result.cost),
        warnings=[
            CostBreakdownValidationWarning(code=w["code"], field=w["field"])
            for w in result.warnings
        ],
    )


# ---------------------------------------------------------------------------
# PUT /costs/{id} — corrección IN-PLACE (vigencia por rangos)
# ---------------------------------------------------------------------------
@router.put(
    "/{cost_id}",
    response_model=CostCreatedResponse,
    summary="Corregir coste IN-PLACE (misma fila, re-estampa FX/landed)",
    description=(
        "Corrige un cost mutando la MISMA fila (breakdown / valid_from / "
        "currency_origin). NO crea versión nueva ni toca `valid_to` (para "
        "cerrar un rango usar POST /costs/{id}/close). Si mover `valid_from` "
        "solapa otro rango → 409 `cost_range_overlap`."
    ),
    operation_id="costsUpdate",
    responses={
        404: {"model": ProblemDetails},
        409: {"model": ProblemDetails},
        422: {"model": ProblemDetails},
    },
)
async def update_cost(
    cost_id: UUID,
    data: CostUpdate,
    user: Annotated[User, Depends(require_permissions("costs:write"))],
    svc: Annotated[CostService, Depends(get_cost_service)],
) -> CostCreatedResponse:
    return await _apply_in_place_update(cost_id=cost_id, data=data, user=user, svc=svc)


# ---------------------------------------------------------------------------
# POST /costs/{id}/close — fija valid_to (descatalogar / cierre sin sucesor)
# ---------------------------------------------------------------------------
@router.post(
    "/{cost_id}/close",
    response_model=CostResponse,
    summary="Cerrar coste (fija valid_to — descatalogar sin sucesor)",
    description=(
        "Fija el `valid_to` de un coste vigente para descatalogarlo. "
        "404 si no existe; 409 si el rango resultante solapa otro existente."
    ),
    operation_id="costsClose",
    responses={
        404: {"model": ProblemDetails},
        409: {"model": ProblemDetails},
    },
)
async def close_cost(
    cost_id: UUID,
    data: CostCloseRequest,
    user: Annotated[User, Depends(require_permissions("costs:write"))],
    svc: Annotated[CostService, Depends(get_cost_service)],
) -> CostResponse:
    try:
        cost = await svc.close_cost(
            cost_id=cost_id,
            valid_to=data.valid_to,
            actor_id=user.id,
            actor_email=user.email,
        )
    except CostNotFound as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": exc.code, "title": "Coste no existe"},
        ) from exc
    except CostRangeOverlap as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": exc.code,
                "title": "El rango de vigencia solapa otro existente",
            },
        ) from exc
    return _to_response(cost)


# ---------------------------------------------------------------------------
# GET /costs/{id}
# ---------------------------------------------------------------------------
@router.get(
    "/{cost_id}",
    response_model=CostResponse,
    summary="Obtener coste por id",
    description="Devuelve un cost individual por su UUID. 404 si no existe.",
    operation_id="costsGet",
    responses={404: {"model": ProblemDetails}},
)
async def get_cost(
    cost_id: UUID,
    _user: Annotated[User, Depends(require_permissions("costs:read"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> CostResponse:
    repo = CostRepository(session)
    cost = await repo.get(cost_id)
    if cost is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "cost_not_found", "title": "Coste no existe"},
        )
    return _to_response(cost)


# ---------------------------------------------------------------------------
# PATCH /costs/{id} — corrección IN-PLACE (vigencia por rangos).
# Misma semántica que PUT; devuelve la fila corregida (sin warnings wrapper).
# ---------------------------------------------------------------------------
@router.patch(
    "/{cost_id}",
    response_model=CostResponse,
    summary="Corregir coste IN-PLACE (misma fila)",
    description=(
        "Corrección parcial IN-PLACE de un coste (breakdown / valid_from / "
        "currency_origin). NO crea versión nueva ni toca `valid_to`. Si mover "
        "`valid_from` solapa otro rango → 409 `cost_range_overlap`."
    ),
    operation_id="costsPatch",
    responses={
        404: {"model": ProblemDetails},
        409: {"model": ProblemDetails},
        422: {"model": ProblemDetails},
    },
)
async def patch_cost(
    cost_id: UUID,
    data: CostUpdate,
    user: Annotated[User, Depends(require_permissions("costs:write"))],
    svc: Annotated[CostService, Depends(get_cost_service)],
) -> CostResponse:
    result = await _apply_in_place_update(cost_id=cost_id, data=data, user=user, svc=svc)
    return result.cost


# ---------------------------------------------------------------------------
# DELETE /costs/{id} — compat tests S2 (no debería usarse en producción)
# ---------------------------------------------------------------------------
@router.delete(
    "/{cost_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Borrar coste (hard delete — sólo compat tests S2)",
    description=(
        "Hard delete de un cost. Sólo expuesto para compat con tests S2. "
        "En producción usar versionado (PUT)."
    ),
    operation_id="costsDelete",
    responses={404: {"model": ProblemDetails}},
)
async def delete_cost(
    cost_id: UUID,
    user: Annotated[User, Depends(require_permissions("costs:write"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    repo = CostRepository(session)
    cost = await repo.get(cost_id)
    if cost is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "cost_not_found", "title": "Coste no existe"},
        )
    snapshot = {
        "sku": cost.sku,
        "scheme_code": cost.scheme_code,
        "supplier_code": cost.supplier_code,
        "currency_origin": cost.currency_origin,
        "scheme_landed_aed": str(cost.scheme_landed_aed)
        if cost.scheme_landed_aed is not None
        else None,
        "version": cost.version,
    }
    await repo.delete(cost_id)
    audit = AuditRepository(session)
    await audit.record(
        entity_type="cost",
        entity_id=str(cost_id),
        action="cost.deleted",
        actor_id=user.id,
        actor_email=user.email,
        before=snapshot,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ===========================================================================
# /products/{sku}/costs — sub-resource (mounted in this same router for
# convenience; el __init__ ya registra `costs.router` con prefix '/costs',
# por lo que aquí montamos un sub-router separado y se registra en el
# aggregator).
# ===========================================================================
products_costs_router = APIRouter(prefix="/products", tags=["costs"])


@products_costs_router.get(
    "/{sku}/costs",
    response_model=list[CostResponse],
    summary="Costes vigentes del SKU agrupados por scheme",
    description=(
        "Devuelve los costs del SKU agrupados por scheme "
        "(FBA/FBM/DIRECT_B2C/DIRECT_B2B/MARKETPLACE) vigentes a la fecha "
        "`as_of` (default hoy), con breakdown desglosado."
    ),
    operation_id="productsListCosts",
)
async def list_costs_for_sku(
    sku: str,
    as_of: Annotated[date | None, Query()] = None,
    only_active: Annotated[bool, Query()] = True,
    _user: User = Depends(require_permissions("costs:read")),
    svc: CostService = Depends(get_cost_service),
) -> list[CostResponse]:
    rows = await svc.list_for_sku(sku, only_active=only_active, as_of=as_of)
    return [_to_response(r) for r in rows]


__all__ = ["products_costs_router", "router"]

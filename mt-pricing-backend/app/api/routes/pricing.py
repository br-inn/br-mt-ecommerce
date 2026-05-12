"""Pricing API v1 — motor v5.1 + workflow + state machine.

Endpoints:
- GET  /pricing/prices                   — listado paginado
- POST /pricing/prices                   — propose price (motor)
- GET  /pricing/prices/{id}              — detalle + history events
- POST /pricing/prices/{id}/approve      — gerente aprueba pending
- POST /pricing/prices/{id}/reject       — gerente rechaza
- POST /pricing/prices/{id}/revise       — comercial revisa con monto nuevo
- POST /pricing/prices/{id}/export       — TI marca exported (post-aprobación)
- POST /pricing/prices/bulk-approve      — bulk
- POST /pricing/prices/recalculate       — Celery fan-out
- POST /pricing/calculate                — preview sin persistir
- POST /pricing/simulate                 — what-if con overrides
- GET  /pricing/channels                 — list channels
- PATCH /pricing/channels/{code}/state   — change state
- GET  /pricing/fx-rates                 — list
- POST /pricing/fx-rates                 — create
"""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_permissions
from app.api.pagination import decode_cursor, encode_cursor
from app.db.enums import ChannelState
from app.db.models.user import User
from app.repositories.pricing import (
    ChannelRepository,
    CurrencyRepository,
    ExceptionRuleRepository,
    FXRateRepository,
    PriceApprovalEventRepository,
)
from app.schemas.common import Cursor, Pagination, ProblemDetails
from app.schemas.pricing import (
    ChannelResponse,
    ChannelStateUpdate,
    ExceptionRuleResponse,
    FXRateCreate,
    FXRateResponse,
    PriceApprovalEventResponse,
    PriceApprovalRequest,
    PriceBulkApproveRequest,
    PriceDetailResponse,
    PriceProposeRequest,
    PriceRejectRequest,
    PriceResponse,
    PriceReviseRequest,
    PricingCalculateRequest,
    PricingResultResponse,
    PricingSimulateRequest,
)
from app.services.pricing import PricingDomainError, PricingService

router = APIRouter(prefix="/pricing", tags=["pricing"])


# ---------------------------------------------------------------------------
# DI
# ---------------------------------------------------------------------------
def get_pricing_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PricingService:
    return PricingService(session)


def _raise_domain(err: PricingDomainError) -> None:
    detail: dict = {"code": err.code, "title": err.message}
    if err.extra:
        detail.update(err.extra)
    raise HTTPException(status_code=err.status_code, detail=detail)


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


# ---------------------------------------------------------------------------
# Calculate / simulate (preview)
# ---------------------------------------------------------------------------
@router.post(
    "/calculate",
    response_model=PricingResultResponse,
    summary="Preview de pricing sin persistir",
)
async def calculate_preview(
    data: PricingCalculateRequest,
    _user: Annotated[User, Depends(require_permissions("prices:read"))],
    service: Annotated[PricingService, Depends(get_pricing_service)],
) -> PricingResultResponse:
    try:
        result = await service.simulate_what_if(
            product_sku=data.product_sku,
            channel_code=data.channel_code,
            scheme_code=data.scheme_code,
            scenario_overrides={
                "market": data.market,
                "master_data": data.master_data,
            },
        )
    except PricingDomainError as exc:
        _raise_domain(exc)
    return PricingResultResponse(
        amount=result.amount,
        pvp_min=result.pvp_min,
        margin_pct=result.margin_pct,
        rule_applied=result.rule_applied,
        formula=result.formula,
        breakdown=result.breakdown,
        alerts=result.alerts,
        fx_at=result.fx_at,
        has_velocity_premium=result.has_velocity_premium,
        has_critical_alerts=result.has_critical_alerts,
        has_warnings=result.has_warnings,
        cap_applied=result.cap_applied,
        floor_applied=result.floor_applied,
    )


@router.post(
    "/simulate",
    response_model=PricingResultResponse,
    summary="What-if simulator con overrides arbitrarios (cost_total, fx_rate, market)",
)
async def simulate_what_if(
    data: PricingSimulateRequest,
    _user: Annotated[User, Depends(require_permissions("prices:read"))],
    service: Annotated[PricingService, Depends(get_pricing_service)],
) -> PricingResultResponse:
    try:
        result = await service.simulate_what_if(
            product_sku=data.product_sku,
            channel_code=data.channel_code,
            scheme_code=data.scheme_code,
            scenario_overrides=data.scenario_overrides or {},
        )
    except PricingDomainError as exc:
        _raise_domain(exc)
    return PricingResultResponse(
        amount=result.amount,
        pvp_min=result.pvp_min,
        margin_pct=result.margin_pct,
        rule_applied=result.rule_applied,
        formula=result.formula,
        breakdown=result.breakdown,
        alerts=result.alerts,
        fx_at=result.fx_at,
        has_velocity_premium=result.has_velocity_premium,
        has_critical_alerts=result.has_critical_alerts,
        has_warnings=result.has_warnings,
        cap_applied=result.cap_applied,
        floor_applied=result.floor_applied,
    )


# ---------------------------------------------------------------------------
# Prices CRUD + workflow
# ---------------------------------------------------------------------------
@router.get(
    "/prices",
    response_model=Pagination[PriceResponse],
    summary="Listado paginado de prices con filtros",
)
async def list_prices(
    sku: Annotated[str | None, Query(min_length=1, max_length=128)] = None,
    channel: Annotated[str | None, Query(min_length=2, max_length=64)] = None,
    scheme: Annotated[str | None, Query(min_length=2, max_length=32)] = None,
    status_filter: Annotated[str | None, Query(alias="status", max_length=32)] = None,
    cursor: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    include_total: Annotated[bool, Query()] = False,
    _user: User = Depends(require_permissions("prices:read")),
    service: PricingService = Depends(get_pricing_service),
) -> Pagination[PriceResponse]:
    cur = _decode_uuid_cursor(cursor)
    try:
        rows, next_cur, total = await service.list_prices(
            product_sku=sku,
            channel_code=channel,
            scheme_code=scheme,
            status=status_filter,
            cursor=cur,
            limit=limit,
            include_total=include_total,
        )
    except PricingDomainError as exc:
        _raise_domain(exc)
    return Pagination[PriceResponse](
        items=[PriceResponse.model_validate(r) for r in rows],
        cursor=Cursor(next=_encode_uuid_cursor(next_cur)),
        page_size=limit,
        total=total,
    )


@router.post(
    "/prices",
    response_model=PriceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Propone nuevo precio (motor v5.1 + ExceptionEvaluator)",
    responses={
        404: {"model": ProblemDetails},
        422: {"model": ProblemDetails},
    },
)
async def propose_price(
    data: PriceProposeRequest,
    user: Annotated[User, Depends(require_permissions("prices:propose"))],
    service: Annotated[PricingService, Depends(get_pricing_service)],
) -> PriceResponse:
    try:
        price = await service.propose_price(
            product_sku=data.product_sku,
            channel_code=data.channel_code,
            scheme_code=data.scheme_code,
            actor=user,
            market=data.market,
            master_data=data.master_data,
        )
    except PricingDomainError as exc:
        _raise_domain(exc)
    return PriceResponse.model_validate(price)


@router.get(
    "/prices/{price_id}",
    response_model=PriceDetailResponse,
    summary="Detalle de price + history of approval events",
    responses={404: {"model": ProblemDetails}},
)
async def get_price(
    price_id: UUID,
    _user: Annotated[User, Depends(require_permissions("prices:read"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[PricingService, Depends(get_pricing_service)],
) -> PriceDetailResponse:
    try:
        price = await service.get_price(price_id)
    except PricingDomainError as exc:
        _raise_domain(exc)
    events_repo = PriceApprovalEventRepository(session)
    events = await events_repo.list_for_price(price_id)
    detail = PriceDetailResponse.model_validate(price)
    detail.approval_events = [PriceApprovalEventResponse.model_validate(e) for e in events]
    return detail


@router.post(
    "/prices/{price_id}/approve",
    response_model=PriceResponse,
    summary="Aprueba precio (gerente_comercial)",
    responses={404: {"model": ProblemDetails}, 409: {"model": ProblemDetails}},
)
async def approve_price(
    price_id: UUID,
    data: PriceApprovalRequest,
    user: Annotated[User, Depends(require_permissions("prices:approve"))],
    service: Annotated[PricingService, Depends(get_pricing_service)],
) -> PriceResponse:
    try:
        price = await service.approve(price_id, user, reason=data.reason)
    except PricingDomainError as exc:
        _raise_domain(exc)
    return PriceResponse.model_validate(price)


@router.post(
    "/prices/{price_id}/reject",
    response_model=PriceResponse,
    summary="Rechaza precio con razón obligatoria",
    responses={404: {"model": ProblemDetails}, 409: {"model": ProblemDetails}, 422: {"model": ProblemDetails}},
)
async def reject_price(
    price_id: UUID,
    data: PriceRejectRequest,
    user: Annotated[User, Depends(require_permissions("prices:approve"))],
    service: Annotated[PricingService, Depends(get_pricing_service)],
) -> PriceResponse:
    try:
        price = await service.reject(price_id, user, reason=data.reason)
    except PricingDomainError as exc:
        _raise_domain(exc)
    return PriceResponse.model_validate(price)


@router.post(
    "/prices/{price_id}/revise",
    response_model=PriceResponse,
    summary="Revisa precio (genera nueva propuesta con monto manual)",
    responses={404: {"model": ProblemDetails}, 409: {"model": ProblemDetails}},
)
async def revise_price(
    price_id: UUID,
    data: PriceReviseRequest,
    user: Annotated[User, Depends(require_permissions("prices:propose"))],
    service: Annotated[PricingService, Depends(get_pricing_service)],
) -> PriceResponse:
    try:
        price = await service.revise(
            price_id, user, new_amount=data.new_amount, reason=data.reason
        )
    except PricingDomainError as exc:
        _raise_domain(exc)
    return PriceResponse.model_validate(price)


@router.post(
    "/prices/{price_id}/export",
    response_model=PriceResponse,
    summary="Marca como exported (post-aprobación, terminal)",
    responses={404: {"model": ProblemDetails}, 409: {"model": ProblemDetails}},
)
async def export_price(
    price_id: UUID,
    user: Annotated[User, Depends(require_permissions("prices:export"))],
    service: Annotated[PricingService, Depends(get_pricing_service)],
) -> PriceResponse:
    try:
        price = await service.export(price_id, user)
    except PricingDomainError as exc:
        _raise_domain(exc)
    return PriceResponse.model_validate(price)


@router.post(
    "/prices/bulk-approve",
    summary="Aprobación masiva con comentario obligatorio",
)
async def bulk_approve(
    data: PriceBulkApproveRequest,
    user: Annotated[User, Depends(require_permissions("prices:approve"))],
    service: Annotated[PricingService, Depends(get_pricing_service)],
) -> dict[str, Any]:
    try:
        return await service.bulk_approve(data.price_ids, data.comment, user)
    except PricingDomainError as exc:
        _raise_domain(exc)


@router.post(
    "/prices/recalculate",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger fan-out Celery para recálculo masivo",
)
async def trigger_bulk_recalc(
    user: Annotated[User, Depends(require_permissions("prices:propose"))],
    service: Annotated[PricingService, Depends(get_pricing_service)],
) -> dict[str, Any]:
    return await service.recalculate_catalog_bulk(user)


# ---------------------------------------------------------------------------
# Channels
# ---------------------------------------------------------------------------
@router.get(
    "/channels",
    response_model=list[ChannelResponse],
    summary="Listar canales con su state",
)
async def list_channels(
    state: Annotated[str | None, Query()] = None,
    _user: User = Depends(require_permissions("channels:read")),
    session: AsyncSession = Depends(get_db_session),
) -> list[ChannelResponse]:
    repo = ChannelRepository(session)
    rows = await repo.list_all(state=state)
    return [ChannelResponse.model_validate(r) for r in rows]


@router.patch(
    "/channels/{code}/state",
    response_model=ChannelResponse,
    summary="Cambia el state del canal (con audit en state_history)",
    responses={404: {"model": ProblemDetails}, 422: {"model": ProblemDetails}},
)
async def update_channel_state(
    code: Annotated[str, Path(min_length=2, max_length=64)],
    data: ChannelStateUpdate,
    user: Annotated[User, Depends(require_permissions("channels:manage"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ChannelResponse:
    valid_states = {s.value for s in ChannelState}
    if data.state not in valid_states:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "invalid_state",
                "title": f"State inválido. Permitidos: {sorted(valid_states)}",
            },
        )
    repo = ChannelRepository(session)
    channel = await repo.get_by_code(code)
    if channel is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "channel_not_found", "title": f"Canal {code!r} no existe"},
        )
    from datetime import datetime, timezone as _tz

    old_state = channel.state
    history = list(channel.state_history or [])
    history.append(
        {
            "from": old_state,
            "to": data.state,
            "at": datetime.now(tz=_tz.utc).isoformat(),
            "by": str(user.id),
            "reason": data.reason,
        }
    )
    channel.state = data.state
    channel.state_history = history
    await session.flush()

    # Audit
    from app.repositories.audit import AuditRepository

    audit = AuditRepository(session)
    await audit.record(
        entity_type="channel",
        entity_id=str(channel.id),
        action="channel.state_updated",
        actor_id=user.id,
        actor_email=user.email,
        before={"state": old_state},
        after={"state": data.state},
        reason=data.reason,
        payload_diff={"state": {"from": old_state, "to": data.state}},
    )
    return ChannelResponse.model_validate(channel)


# ---------------------------------------------------------------------------
# FX rates
# ---------------------------------------------------------------------------
@router.get(
    "/fx-rates",
    response_model=list[FXRateResponse],
    summary="Lista FX rates (más reciente primero)",
)
async def list_fx_rates(
    from_currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
    to_currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
    _user: User = Depends(require_permissions("fx:read")),
    session: AsyncSession = Depends(get_db_session),
) -> list[FXRateResponse]:
    repo = FXRateRepository(session)
    if from_currency and to_currency:
        rows = await repo.list_pair(from_currency.upper(), to_currency.upper())
    else:
        rows = await repo.list_all()
    return [FXRateResponse.model_validate(r) for r in rows]


@router.post(
    "/fx-rates",
    response_model=FXRateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crea FX rate manual (admin/TI)",
)
async def create_fx_rate(
    data: FXRateCreate,
    user: Annotated[User, Depends(require_permissions("fx:write"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> FXRateResponse:
    repo = FXRateRepository(session)

    # Cierra el período del rate anterior (efectivo) si existe.
    from datetime import datetime, timezone as _tz

    effective_from = data.effective_from or datetime.now(tz=_tz.utc)
    current = await repo.get_active(
        data.from_currency.upper(), data.to_currency.upper(), as_of=effective_from
    )
    if current is not None and current.effective_to is None:
        current.effective_to = effective_from

    new_rate = await repo.create(
        from_currency=data.from_currency.upper(),
        to_currency=data.to_currency.upper(),
        rate=data.rate,
        effective_from=effective_from,
        source=data.source,
    )

    # Audit
    from app.repositories.audit import AuditRepository

    audit = AuditRepository(session)
    await audit.record(
        entity_type="fx_rate",
        entity_id=str(new_rate.id),
        action="fx_rate.created",
        actor_id=user.id,
        actor_email=user.email,
        after={
            "from_currency": new_rate.from_currency,
            "to_currency": new_rate.to_currency,
            "rate": str(new_rate.rate),
            "effective_from": new_rate.effective_from.isoformat(),
            "source": new_rate.source,
        },
    )
    return FXRateResponse.model_validate(new_rate)


# ---------------------------------------------------------------------------
# Currencies (read-only Sprint 2 — seed AED/EUR/USD/SAR)
# ---------------------------------------------------------------------------
@router.get(
    "/currencies",
    summary="Lista currencies activas (read-only en Sprint 2)",
)
async def list_currencies(
    _user: User = Depends(require_permissions("fx:read")),
    session: AsyncSession = Depends(get_db_session),
) -> list[dict[str, Any]]:
    repo = CurrencyRepository(session)
    rows = await repo.list_active()
    return [
        {
            "code": r.code,
            "name": r.name,
            "symbol": r.symbol,
            "decimals": r.decimals,
            "is_base": r.is_base,
            "active": r.active,
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Exception rules (read-only por ahora, admin)
# ---------------------------------------------------------------------------
@router.get(
    "/exception-rules",
    response_model=list[ExceptionRuleResponse],
    summary="Listado read-only de exception_rules activas",
)
async def list_exception_rules(
    _user: User = Depends(require_permissions("prices:read")),
    session: AsyncSession = Depends(get_db_session),
) -> list[ExceptionRuleResponse]:
    repo = ExceptionRuleRepository(session)
    rows = await repo.list_active()
    return [ExceptionRuleResponse.model_validate(r) for r in rows]

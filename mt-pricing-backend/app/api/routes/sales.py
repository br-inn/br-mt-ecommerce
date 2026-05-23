"""Sales / O2C API — EP-ERP-04.

Prefix: /api/v1/sales

Endpoints:
  US-ERP-04-01 — SO CRUD + document chain
  US-ERP-04-02 — ATP check + confirm (reservation)
  US-ERP-04-03 — Credit management
  US-ERP-04-04 — Outbound deliveries + Goods Issue
  US-ERP-04-05 — Returns (RMA) + Credit Memo
  US-ERP-04-06 — Dashboard KPIs + Backorder report
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, get_db_session, require_role
from app.db.models.audit import AuditEvent
from app.db.models.billing import Invoice
from app.db.models.inventory import (
    InventoryPosition,
    StockMovement,
    StockMovementType,
)
from app.db.models.sales import (
    AtpCheckingRule,
    CreditMemo,
    CustomerCreditLimit,
    CustomerOpenItem,
    OutboundDelivery,
    OutboundDeliveryLine,
    RmaHeader,
    RmaLine,
    SalesOrder,
    SalesOrderLine,
    StockReservation,
)
from app.db.models.user import User
from app.schemas.sales import (
    ATPCheckOut,
    AtpRuleCreate,
    AtpRuleOut,
    BackorderLineOut,
    CreditCheckOut,
    CreditLimitCreate,
    CreditLimitOut,
    CreditLimitUpdate,
    CreditMemoOut,
    CustomerOpenItemOut,
    DocumentChainOut,
    O2CKpisOut,
    OutboundDeliveryCreate,
    OutboundDeliveryListOut,
    OutboundDeliveryOut,
    OutboundDeliveryStatusUpdate,
    RmaCreate,
    RmaOut,
    ReturnDeliveryCreate,
    ReturnDeliveryOut,
    SalesOrderCreate,
    SalesOrderListOut,
    SalesOrderOut,
    SalesOrderUpdate,
    StockReservationOut,
)
from app.services.atp import compute_atp_for_so

router = APIRouter(prefix="/sales", tags=["sales"])
logger = logging.getLogger(__name__)

_ZERO = Decimal("0")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _so_number() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"SO-{ts}-{uuid.uuid4().hex[:6].upper()}"


def _delivery_number() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"DEL-{ts}-{uuid.uuid4().hex[:6].upper()}"


def _rma_number() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"RMA-{ts}-{uuid.uuid4().hex[:6].upper()}"


def _memo_number() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"CM-{ts}-{uuid.uuid4().hex[:6].upper()}"


async def _get_so_or_404(db: AsyncSession, so_id: UUID) -> SalesOrder:
    result = await db.execute(
        select(SalesOrder).options(selectinload(SalesOrder.lines)).where(SalesOrder.id == so_id)
    )
    so = result.scalar_one_or_none()
    if so is None:
        raise HTTPException(status_code=404, detail="Sales order not found")
    return so


async def _get_delivery_or_404(db: AsyncSession, delivery_id: UUID) -> OutboundDelivery:
    result = await db.execute(
        select(OutboundDelivery)
        .options(selectinload(OutboundDelivery.lines))
        .where(OutboundDelivery.id == delivery_id)
    )
    delivery = result.scalar_one_or_none()
    if delivery is None:
        raise HTTPException(status_code=404, detail="Delivery not found")
    return delivery


async def _get_rma_or_404(db: AsyncSession, rma_id: UUID) -> RmaHeader:
    result = await db.execute(
        select(RmaHeader).options(selectinload(RmaHeader.lines)).where(RmaHeader.id == rma_id)
    )
    rma = result.scalar_one_or_none()
    if rma is None:
        raise HTTPException(status_code=404, detail="RMA not found")
    return rma


async def _gi_movement_type_id(db: AsyncSession) -> UUID | None:
    """Obtiene el ID del StockMovementType para GI (Goods Issue)."""
    result = await db.execute(select(StockMovementType.id).where(StockMovementType.code == "GI"))
    return result.scalar_one_or_none()


async def _gr_return_movement_type_id(db: AsyncSession) -> UUID | None:
    """Obtiene el ID del StockMovementType para GR_RETURN."""
    result = await db.execute(
        select(StockMovementType.id).where(StockMovementType.code == "GR_RETURN")
    )
    return result.scalar_one_or_none()


async def _qi_movement_type_id(db: AsyncSession) -> UUID | None:
    """Obtiene el ID del StockMovementType para QUALITY_INSPECTION."""
    result = await db.execute(
        select(StockMovementType.id).where(StockMovementType.code.in_(["QI", "QUALITY_INSPECTION"]))
    )
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# US-ERP-04-01 — Sales Orders CRUD
# ---------------------------------------------------------------------------


@router.get(
    "/orders",
    response_model=SalesOrderListOut,
    summary="Listar Sales Orders",
    operation_id="salesOrdersList",
)
async def list_sales_orders(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    status_filter: str | None = Query(None, alias="status"),
    customer_id: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
) -> SalesOrderListOut:
    query = select(SalesOrder).options(selectinload(SalesOrder.lines))
    if status_filter:
        query = query.where(SalesOrder.status == status_filter)
    if customer_id:
        query = query.where(SalesOrder.customer_id == customer_id)
    query = query.order_by(SalesOrder.created_at.desc()).offset(offset).limit(limit)

    count_query = select(func.count(SalesOrder.id))
    if status_filter:
        count_query = count_query.where(SalesOrder.status == status_filter)
    if customer_id:
        count_query = count_query.where(SalesOrder.customer_id == customer_id)

    result = await db.execute(query)
    orders = result.scalars().all()
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()
    return SalesOrderListOut(
        items=[SalesOrderOut.model_validate(o) for o in orders],
        total=total,
    )


@router.post(
    "/orders",
    response_model=SalesOrderOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear Sales Order",
    operation_id="salesOrdersCreate",
)
async def create_sales_order(
    body: SalesOrderCreate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SalesOrderOut:
    so = SalesOrder(
        so_number=_so_number(),
        customer_id=body.customer_id,
        order_type=body.order_type,
        quotation_id=body.quotation_id,
        status="draft",
        warehouse_id=body.warehouse_id,
        requested_delivery_date=body.requested_delivery_date,
        payment_terms=body.payment_terms,
        currency=body.currency,
        notes=body.notes,
        created_by=current_user.id,
    )
    db.add(so)
    await db.flush()  # get so.id

    subtotal = _ZERO
    for line_in in body.lines:
        unit_price = line_in.unit_price or _ZERO
        line_total = line_in.qty * unit_price * (1 - line_in.discount_pct / 100)
        subtotal += line_total
        sol = SalesOrderLine(
            so_id=so.id,
            product_sku=line_in.product_sku,
            qty=line_in.qty,
            uom=line_in.uom,
            unit_price=line_in.unit_price,
            discount_pct=line_in.discount_pct,
            line_total=line_total,
            requested_delivery_date=line_in.requested_delivery_date,
            status="open",
        )
        db.add(sol)

    so.subtotal = subtotal
    so.total_amount = subtotal  # simplified (no tax engine here)
    await db.commit()
    await db.refresh(so)
    # Reload with lines
    result = await db.execute(
        select(SalesOrder).options(selectinload(SalesOrder.lines)).where(SalesOrder.id == so.id)
    )
    so = result.scalar_one()
    return SalesOrderOut.model_validate(so)


@router.get(
    "/orders/{so_id}",
    response_model=SalesOrderOut,
    summary="Detalle Sales Order",
    operation_id="salesOrdersGet",
)
async def get_sales_order(
    so_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SalesOrderOut:
    so = await _get_so_or_404(db, so_id)
    return SalesOrderOut.model_validate(so)


@router.patch(
    "/orders/{so_id}",
    response_model=SalesOrderOut,
    summary="Actualizar Sales Order",
    operation_id="salesOrdersUpdate",
)
async def update_sales_order(
    so_id: UUID,
    body: SalesOrderUpdate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SalesOrderOut:
    so = await _get_so_or_404(db, so_id)
    if body.status is not None:
        so.status = body.status
    if body.requested_delivery_date is not None:
        so.requested_delivery_date = body.requested_delivery_date
    if body.payment_terms is not None:
        so.payment_terms = body.payment_terms
    if body.notes is not None:
        so.notes = body.notes
    if body.warehouse_id is not None:
        so.warehouse_id = body.warehouse_id
    await db.commit()
    await db.refresh(so)
    result = await db.execute(
        select(SalesOrder).options(selectinload(SalesOrder.lines)).where(SalesOrder.id == so.id)
    )
    so = result.scalar_one()
    return SalesOrderOut.model_validate(so)


@router.get(
    "/orders/{so_id}/chain",
    response_model=DocumentChainOut,
    summary="Cadena documental de un SO (SO + deliveries + invoices)",
    operation_id="salesOrdersChain",
)
async def get_document_chain(
    so_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> DocumentChainOut:
    so = await _get_so_or_404(db, so_id)

    # Load deliveries and invoices in parallel
    del_result, inv_result = await asyncio.gather(
        db.execute(
            select(OutboundDelivery)
            .options(selectinload(OutboundDelivery.lines))
            .where(OutboundDelivery.so_id == so_id)
        ),
        db.execute(select(Invoice).where(Invoice.so_id == so_id)),
    )
    deliveries = del_result.scalars().all()
    invoices = inv_result.scalars().all()

    return DocumentChainOut(
        so=SalesOrderOut.model_validate(so),
        deliveries=[OutboundDeliveryOut.model_validate(d) for d in deliveries],
        invoices=invoices,
    )


# ---------------------------------------------------------------------------
# US-ERP-04-02 — ATP check + confirm reservation
# ---------------------------------------------------------------------------


@router.post(
    "/orders/{so_id}/atp-check",
    response_model=ATPCheckOut,
    summary="Ejecutar ATP check para todas las líneas del SO",
    operation_id="salesOrdersAtpCheck",
)
async def atp_check(
    so_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ATPCheckOut:
    so = await _get_so_or_404(db, so_id)
    lines = await compute_atp_for_so(db, so)
    return ATPCheckOut(so_id=so_id, lines=lines)


@router.post(
    "/orders/{so_id}/confirm",
    response_model=SalesOrderOut,
    summary="Confirmar SO — reserva stock ATP-OK",
    operation_id="salesOrdersConfirm",
)
async def confirm_sales_order(
    so_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SalesOrderOut:
    so = await _get_so_or_404(db, so_id)
    if so.status not in ("draft",):
        raise HTTPException(status_code=400, detail=f"Cannot confirm SO in status '{so.status}'")

    atp_lines = await compute_atp_for_so(db, so)

    has_available = False
    for atp_result in atp_lines:
        if atp_result.status == "available" and so.warehouse_id:
            # Find matching SO line
            sol_result = await db.execute(
                select(SalesOrderLine).where(SalesOrderLine.id == atp_result.so_line_id)
            )
            sol = sol_result.scalar_one_or_none()
            if sol is None:
                continue
            reservation = StockReservation(
                so_line_id=sol.id,
                product_sku=sol.product_sku,
                warehouse_id=so.warehouse_id,
                qty=atp_result.atp_qty,
                status="active",
            )
            db.add(reservation)
            sol.status = "confirmed"
            sol.confirmed_qty = atp_result.atp_qty
            has_available = True
        elif atp_result.status in ("partial", "backorder"):
            # Leave line as open (backorder)
            pass

    so.status = "confirmed"
    await db.commit()
    result = await db.execute(
        select(SalesOrder).options(selectinload(SalesOrder.lines)).where(SalesOrder.id == so.id)
    )
    so = result.scalar_one()
    return SalesOrderOut.model_validate(so)


# ---------------------------------------------------------------------------
# US-ERP-04-03 — Credit Management
# ---------------------------------------------------------------------------


@router.post(
    "/orders/{so_id}/credit-check",
    response_model=CreditCheckOut,
    summary="Verificar crédito disponible para el SO",
    operation_id="salesOrdersCreditCheck",
)
async def credit_check(
    so_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CreditCheckOut:
    so = await _get_so_or_404(db, so_id)

    # Orders ≤ AED 500 skip credit check (low-value fast path)
    _LOW_VALUE_THRESHOLD = Decimal("500")
    if (so.total_amount or _ZERO) <= _LOW_VALUE_THRESHOLD:
        return CreditCheckOut(
            status="skipped",
            exposure=so.total_amount or _ZERO,
            limit=None,
            available=None,
            skipped=True,
            reason="order_below_aed_500_threshold",
        )

    # Get credit limit
    cl_result = await db.execute(
        select(CustomerCreditLimit).where(CustomerCreditLimit.customer_id == so.customer_id)
    )
    cl = cl_result.scalar_one_or_none()

    # Sum open items
    open_items_result = await db.execute(
        select(func.coalesce(func.sum(CustomerOpenItem.amount), _ZERO)).where(
            CustomerOpenItem.customer_id == so.customer_id,
            CustomerOpenItem.status != "paid",
        )
    )
    open_exposure = open_items_result.scalar_one() or _ZERO
    so_amount = so.total_amount or _ZERO
    total_exposure = open_exposure + so_amount

    if cl is None:
        # No limit configured — pass with warning
        return CreditCheckOut(
            status="warning",
            exposure=total_exposure,
            limit=None,
            available=None,
        )

    limit = cl.credit_limit or _ZERO

    if cl.is_blocked or total_exposure > limit:
        # Block the SO
        so.status = "on_credit_hold"
        await db.commit()
        available = max(limit - open_exposure, _ZERO)
        return CreditCheckOut(
            status="blocked",
            exposure=total_exposure,
            limit=limit,
            available=available,
        )

    warning_threshold = limit * Decimal("0.9")
    status_val = "warning" if total_exposure >= warning_threshold else "ok"
    available = limit - total_exposure
    return CreditCheckOut(
        status=status_val,
        exposure=total_exposure,
        limit=limit,
        available=available,
    )


@router.post(
    "/credit-limits",
    response_model=CreditLimitOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear límite de crédito para un cliente",
    operation_id="salesCreditLimitsCreate",
)
async def create_credit_limit(
    body: CreditLimitCreate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CreditLimitOut:
    existing = await db.execute(
        select(CustomerCreditLimit).where(CustomerCreditLimit.customer_id == body.customer_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Credit limit already exists for this customer")
    cl = CustomerCreditLimit(
        customer_id=body.customer_id,
        credit_limit=body.credit_limit,
        currency=body.currency,
        credit_horizon_days=body.credit_horizon_days,
    )
    db.add(cl)
    await db.commit()
    await db.refresh(cl)
    return CreditLimitOut.model_validate(cl)


@router.patch(
    "/credit-limits/{customer_id}",
    response_model=CreditLimitOut,
    summary="Actualizar límite de crédito",
    operation_id="salesCreditLimitsUpdate",
)
async def update_credit_limit(
    customer_id: str,
    body: CreditLimitUpdate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CreditLimitOut:
    result = await db.execute(
        select(CustomerCreditLimit).where(CustomerCreditLimit.customer_id == customer_id)
    )
    cl = result.scalar_one_or_none()
    if cl is None:
        raise HTTPException(status_code=404, detail="Credit limit not found")
    if body.credit_limit is not None:
        cl.credit_limit = body.credit_limit
    if body.currency is not None:
        cl.currency = body.currency
    if body.credit_horizon_days is not None:
        cl.credit_horizon_days = body.credit_horizon_days
    if body.is_blocked is not None:
        cl.is_blocked = body.is_blocked
    if body.block_reason is not None:
        cl.block_reason = body.block_reason
    await db.commit()
    await db.refresh(cl)
    return CreditLimitOut.model_validate(cl)


@router.post(
    "/credit-limits/{customer_id}/release-block",
    response_model=CreditLimitOut,
    summary="Desbloquear crédito de un cliente (rol gerente)",
    operation_id="salesCreditLimitsReleaseBlock",
)
async def release_credit_block(
    customer_id: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(require_role("gerente"))],
) -> CreditLimitOut:
    result = await db.execute(
        select(CustomerCreditLimit).where(CustomerCreditLimit.customer_id == customer_id)
    )
    cl = result.scalar_one_or_none()
    if cl is None:
        raise HTTPException(status_code=404, detail="Credit limit not found")
    cl.is_blocked = False
    cl.block_reason = None
    await db.commit()
    await db.refresh(cl)
    return CreditLimitOut.model_validate(cl)


@router.post(
    "/orders/{so_id}/release-credit-hold",
    response_model=SalesOrderOut,
    summary="Liberar bloqueo de crédito de un SO específico (rol gerente)",
    operation_id="salesOrdersReleaseCreditHold",
)
async def release_so_credit_hold(
    so_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(require_role("gerente"))],
    reason: str = Body(..., embed=True, min_length=10),
) -> SalesOrderOut:
    so = await _get_so_or_404(db, so_id)
    if so.status != "on_credit_hold":
        raise HTTPException(
            status_code=400,
            detail=f"SO is not on credit hold (current status: '{so.status}')",
        )
    so.status = "confirmed"

    # Audit trail
    audit_evt = AuditEvent(
        actor_id=current_user.id,
        actor_email=current_user.email,
        actor_role="gerente",
        entity_type="sales_order",
        entity_id=str(so.id),
        action="release_credit_hold",
        before={"status": "on_credit_hold"},
        after={"status": "confirmed"},
        reason=reason,
    )
    db.add(audit_evt)

    await db.commit()
    await db.refresh(so)
    return SalesOrderOut.model_validate(so)


# ---------------------------------------------------------------------------
# US-ERP-04-04 — Outbound Deliveries
# ---------------------------------------------------------------------------


@router.get(
    "/deliveries",
    response_model=OutboundDeliveryListOut,
    summary="Listar entregas de salida",
    operation_id="salesDeliveriesList",
)
async def list_deliveries(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    so_id: UUID | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
) -> OutboundDeliveryListOut:
    query = select(OutboundDelivery).options(selectinload(OutboundDelivery.lines))
    if so_id:
        query = query.where(OutboundDelivery.so_id == so_id)
    if status_filter:
        query = query.where(OutboundDelivery.status == status_filter)
    query = query.order_by(OutboundDelivery.created_at.desc()).offset(offset).limit(limit)

    count_query = select(func.count(OutboundDelivery.id))
    if so_id:
        count_query = count_query.where(OutboundDelivery.so_id == so_id)
    if status_filter:
        count_query = count_query.where(OutboundDelivery.status == status_filter)

    result = await db.execute(query)
    deliveries = result.scalars().all()
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()
    return OutboundDeliveryListOut(
        items=[OutboundDeliveryOut.model_validate(d) for d in deliveries],
        total=total,
    )


@router.post(
    "/deliveries",
    response_model=OutboundDeliveryOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear entrega de salida desde un SO",
    operation_id="salesDeliveriesCreate",
)
async def create_delivery(
    body: OutboundDeliveryCreate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> OutboundDeliveryOut:
    so = await _get_so_or_404(db, body.so_id)
    if so.status not in ("confirmed", "in_fulfillment", "partially_delivered"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot create delivery for SO in status '{so.status}'",
        )

    delivery = OutboundDelivery(
        delivery_number=_delivery_number(),
        so_id=so.id,
        warehouse_id=body.warehouse_id or so.warehouse_id,
        status="pending_pick",
        partial_delivery_allowed=body.partial_delivery_allowed,
    )
    db.add(delivery)
    await db.flush()

    # Determine which SO lines to include
    if body.line_so_line_ids:
        lines_to_include = [l for l in so.lines if l.id in set(body.line_so_line_ids)]
    else:
        lines_to_include = [l for l in so.lines if l.status in ("open", "confirmed")]

    for sol in lines_to_include:
        dl = OutboundDeliveryLine(
            delivery_id=delivery.id,
            so_line_id=sol.id,
            product_sku=sol.product_sku,
            qty_planned=sol.confirmed_qty or sol.qty,
            qty_picked=_ZERO,
        )
        db.add(dl)

    # Update SO status
    if so.status == "confirmed":
        so.status = "in_fulfillment"

    await db.commit()
    result = await db.execute(
        select(OutboundDelivery)
        .options(selectinload(OutboundDelivery.lines))
        .where(OutboundDelivery.id == delivery.id)
    )
    delivery = result.scalar_one()
    return OutboundDeliveryOut.model_validate(delivery)


@router.patch(
    "/deliveries/{delivery_id}/status",
    response_model=OutboundDeliveryOut,
    summary="Avanzar status de una entrega",
    operation_id="salesDeliveriesStatusUpdate",
)
async def update_delivery_status(
    delivery_id: UUID,
    body: OutboundDeliveryStatusUpdate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> OutboundDeliveryOut:
    delivery = await _get_delivery_or_404(db, delivery_id)

    allowed_transitions: dict[str, list[str]] = {
        "pending_pick": ["picking", "cancelled"],
        "picking": ["packed", "cancelled"],
        "packed": ["goods_issued", "cancelled"],
    }
    allowed = allowed_transitions.get(delivery.status, [])
    if body.status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot transition delivery from '{delivery.status}' to '{body.status}'",
        )
    delivery.status = body.status
    await db.commit()
    await db.refresh(delivery)
    result = await db.execute(
        select(OutboundDelivery)
        .options(selectinload(OutboundDelivery.lines))
        .where(OutboundDelivery.id == delivery.id)
    )
    delivery = result.scalar_one()
    return OutboundDeliveryOut.model_validate(delivery)


@router.post(
    "/deliveries/{delivery_id}/goods-issue",
    response_model=OutboundDeliveryOut,
    summary="Confirmar Goods Issue — reduce stock, consume reservas, crea open item",
    operation_id="salesDeliveriesGoodsIssue",
)
async def goods_issue(
    delivery_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> OutboundDeliveryOut:
    delivery = await _get_delivery_or_404(db, delivery_id)
    if delivery.status != "packed":
        raise HTTPException(
            status_code=400,
            detail=f"Goods issue requires delivery in 'packed' status, current: '{delivery.status}'",
        )

    gi_mt_id = await _gi_movement_type_id(db)
    so = await _get_so_or_404(db, delivery.so_id)

    for dl in delivery.lines:
        qty = dl.qty_picked if dl.qty_picked > _ZERO else dl.qty_planned

        # 1. Create stock movement (GI = OUT)
        if gi_mt_id:
            movement = StockMovement(
                movement_type_id=gi_mt_id,
                product_sku=dl.product_sku,
                warehouse_id=delivery.warehouse_id,
                qty=qty,
                direction="OUT",
                reference_doc="OUTBOUND_DELIVERY",
                reference_id=delivery.id,
            )
            db.add(movement)

        # 1b. Decrement unrestricted InventoryPosition.qty_on_hand
        await db.execute(
            update(InventoryPosition)
            .where(
                InventoryPosition.sku == dl.product_sku,
                InventoryPosition.warehouse_id == delivery.warehouse_id,
                InventoryPosition.stock_type == "unrestricted",
            )
            .values(qty_on_hand=InventoryPosition.qty_on_hand - qty)
        )

        # 2. Consume active reservations for this SO line
        res_result = await db.execute(
            select(StockReservation).where(
                StockReservation.so_line_id == dl.so_line_id,
                StockReservation.status == "active",
            )
        )
        for reservation in res_result.scalars().all():
            reservation.status = "consumed"

        # 3. Update SO line status
        sol_result = await db.execute(
            select(SalesOrderLine).where(SalesOrderLine.id == dl.so_line_id)
        )
        sol = sol_result.scalar_one_or_none()
        if sol:
            sol.status = "delivered"

    # 4. Create customer open item
    open_item = CustomerOpenItem(
        customer_id=so.customer_id,
        so_id=so.id,
        document_type="so",
        amount=so.total_amount or _ZERO,
        due_date=date.today() + timedelta(days=30),
        status="open",
    )
    db.add(open_item)

    # 5. Update delivery
    delivery.status = "goods_issued"
    delivery.shipped_at = datetime.now(timezone.utc)

    # 6. Update SO status
    # Check if all lines delivered
    all_delivered = all(l.status == "delivered" for l in so.lines if l.status != "cancelled")
    so.status = "delivered" if all_delivered else "partially_delivered"

    await db.commit()
    result = await db.execute(
        select(OutboundDelivery)
        .options(selectinload(OutboundDelivery.lines))
        .where(OutboundDelivery.id == delivery.id)
    )
    delivery = result.scalar_one()
    return OutboundDeliveryOut.model_validate(delivery)


# ---------------------------------------------------------------------------
# US-ERP-04-05 — Returns (RMA)
# ---------------------------------------------------------------------------


@router.post(
    "/returns",
    response_model=RmaOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear RMA (Return Merchandise Authorization)",
    operation_id="salesReturnsCreate",
)
async def create_rma(
    body: RmaCreate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> RmaOut:
    # Verify original SO exists
    await _get_so_or_404(db, body.original_so_id)

    rma = RmaHeader(
        rma_number=_rma_number(),
        original_so_id=body.original_so_id,
        customer_id=body.customer_id,
        return_type=body.return_type,
        status="requested",
        reason=body.reason,
    )
    db.add(rma)
    await db.flush()

    for line_in in body.lines:
        rma_line = RmaLine(
            rma_id=rma.id,
            so_line_id=line_in.so_line_id,
            product_sku=line_in.product_sku,
            qty_returned=line_in.qty_returned,
            lot_id=line_in.lot_id,
            condition=line_in.condition,
        )
        db.add(rma_line)

    await db.commit()
    result = await db.execute(
        select(RmaHeader).options(selectinload(RmaHeader.lines)).where(RmaHeader.id == rma.id)
    )
    rma = result.scalar_one()
    return RmaOut.model_validate(rma)


@router.post(
    "/returns/{rma_id}/approve",
    response_model=RmaOut,
    summary="Aprobar RMA (rol gerente)",
    operation_id="salesReturnsApprove",
)
async def approve_rma(
    rma_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(require_role("gerente"))],
) -> RmaOut:
    rma = await _get_rma_or_404(db, rma_id)
    if rma.status != "requested":
        raise HTTPException(
            status_code=400, detail=f"RMA not in 'requested' status: '{rma.status}'"
        )
    rma.status = "approved"
    await db.commit()
    await db.refresh(rma)
    result = await db.execute(
        select(RmaHeader).options(selectinload(RmaHeader.lines)).where(RmaHeader.id == rma.id)
    )
    rma = result.scalar_one()
    return RmaOut.model_validate(rma)


@router.post(
    "/returns/{rma_id}/receive-goods",
    response_model=RmaOut,
    summary="Confirmar recepción de devolución — crea ReturnDelivery + movimientos de stock",
    operation_id="salesReturnsReceiveGoods",
)
async def receive_return_goods(
    rma_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    body: ReturnDeliveryCreate = ReturnDeliveryCreate(),
) -> RmaOut:
    from datetime import date as _date
    from app.db.models.sales import ReturnDelivery

    rma = await _get_rma_or_404(db, rma_id)
    if rma.status != "approved":
        raise HTTPException(status_code=400, detail=f"RMA not approved: '{rma.status}'")

    # Create ReturnDelivery record (VEN-18)
    delivery = ReturnDelivery(
        rma_id=rma_id,
        warehouse_id=body.warehouse_id,
        received_date=body.received_date or _date.today(),
        received_by=current_user.id,
        notes=body.notes,
    )
    db.add(delivery)

    gr_return_mt_id = await _gr_return_movement_type_id(db)
    qi_mt_id = await _qi_movement_type_id(db)

    # Get original SO warehouse
    so = await _get_so_or_404(db, rma.original_so_id)

    for line in rma.lines:
        if line.condition == "resalable":
            mt_id = gr_return_mt_id
        elif line.condition in ("damaged", "to_dispose"):
            mt_id = qi_mt_id
        else:
            mt_id = gr_return_mt_id

        if mt_id and so.warehouse_id:
            movement = StockMovement(
                movement_type_id=mt_id,
                product_sku=line.product_sku,
                warehouse_id=so.warehouse_id,
                qty=line.qty_returned,
                direction="IN",
                reference_doc="RMA",
                reference_id=rma.id,
            )
            db.add(movement)

    rma.status = "goods_received"
    await db.commit()
    result = await db.execute(
        select(RmaHeader).options(selectinload(RmaHeader.lines)).where(RmaHeader.id == rma.id)
    )
    rma = result.scalar_one()
    return RmaOut.model_validate(rma)


@router.post(
    "/returns/{rma_id}/issue-credit",
    response_model=CreditMemoOut,
    summary="Emitir credit memo automático desde RMA aprobado",
    operation_id="salesReturnsIssueCredit",
)
async def issue_credit_memo(
    rma_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CreditMemoOut:
    rma = await _get_rma_or_404(db, rma_id)
    if rma.status != "goods_received":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot issue credit: RMA status is '{rma.status}', expected 'goods_received'",
        )

    # Calculate amount from original SO lines
    total_credit = _ZERO
    for rma_line in rma.lines:
        sol_result = await db.execute(
            select(SalesOrderLine).where(SalesOrderLine.id == rma_line.so_line_id)
        )
        sol = sol_result.scalar_one_or_none()
        if sol and sol.unit_price:
            line_amount = rma_line.qty_returned * sol.unit_price * (1 - sol.discount_pct / 100)
            total_credit += line_amount

    memo = CreditMemo(
        memo_number=_memo_number(),
        rma_id=rma.id,
        customer_id=rma.customer_id,
        amount=total_credit,
        currency="AED",
        status="pending",
    )
    db.add(memo)
    rma.status = "credit_issued"
    await db.commit()
    await db.refresh(memo)
    return CreditMemoOut.model_validate(memo)


# ---------------------------------------------------------------------------
# US-ERP-04-06 — Dashboard KPIs + Backorder report
# ---------------------------------------------------------------------------


@router.get(
    "/kpis",
    response_model=O2CKpisOut,
    summary="KPIs O2C: open SOs, backorders, OTD%, AOV, credit holds, RMA",
    operation_id="salesKpis",
)
async def get_kpis(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> O2CKpisOut:
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    first_of_month = datetime.now(timezone.utc).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )

    # Run 9 independent count queries in parallel (1 round-trip to DB)
    (
        open_so_result,
        backorder_result,
        total_deliveries_result,
        avg_result,
        credit_holds_result,
        rma_result,
        revenue_mtd_result,
        order_count_mtd_result,
        fill_rate_result,
    ) = await asyncio.gather(
        db.execute(
            select(func.count(SalesOrder.id)).where(
                SalesOrder.status.in_(["confirmed", "in_fulfillment", "partially_delivered"])
            )
        ),
        db.execute(
            select(func.count(SalesOrderLine.id)).where(
                SalesOrderLine.status == "open",
            )
        ),
        db.execute(
            select(func.count(OutboundDelivery.id)).where(
                OutboundDelivery.status == "goods_issued",
                OutboundDelivery.shipped_at >= thirty_days_ago,
            )
        ),
        db.execute(
            select(func.coalesce(func.avg(SalesOrder.total_amount), _ZERO)).where(
                SalesOrder.created_at >= thirty_days_ago,
                SalesOrder.total_amount.is_not(None),
            )
        ),
        db.execute(select(func.count(SalesOrder.id)).where(SalesOrder.status == "on_credit_hold")),
        db.execute(
            select(func.count(RmaHeader.id)).where(
                RmaHeader.status.in_(["requested", "approved", "goods_received"])
            )
        ),
        db.execute(
            select(func.coalesce(func.sum(SalesOrder.total_amount), _ZERO)).where(
                SalesOrder.created_at >= first_of_month,
                SalesOrder.status.not_in(["cancelled", "on_credit_hold"]),
                SalesOrder.total_amount.is_not(None),
            )
        ),
        db.execute(
            select(func.count(SalesOrder.id)).where(
                SalesOrder.created_at >= first_of_month,
                SalesOrder.status.not_in(["cancelled"]),
            )
        ),
        db.execute(
            select(func.count(OutboundDeliveryLine.id)).where(
                OutboundDeliveryLine.qty_picked >= OutboundDeliveryLine.qty_planned,
            )
        ),
    )

    open_so_count = open_so_result.scalar_one() or 0
    backorder_count = backorder_result.scalar_one() or 0
    total_deliveries = total_deliveries_result.scalar_one() or 0
    avg_order_value = avg_result.scalar_one() or _ZERO
    open_credit_holds = credit_holds_result.scalar_one() or 0
    rma_open_count = rma_result.scalar_one() or 0
    revenue_mtd = revenue_mtd_result.scalar_one() or _ZERO
    order_count_mtd = order_count_mtd_result.scalar_one() or 0
    # fill_rate: lines fully fulfilled / total lines (simple ratio)
    fill_rate_numerator = fill_rate_result.scalar_one() or 0
    total_lines_result = await db.execute(select(func.count(OutboundDeliveryLine.id)))
    total_lines = total_lines_result.scalar_one() or 0
    fill_rate_pct = round((fill_rate_numerator / total_lines * 100) if total_lines > 0 else 0.0, 2)

    # on_time delivery count — only if there are deliveries to avoid extra query
    on_time_count = 0
    if total_deliveries > 0:
        on_time_result = await db.execute(
            select(func.count(OutboundDelivery.id))
            .join(SalesOrder, OutboundDelivery.so_id == SalesOrder.id)
            .where(
                OutboundDelivery.status == "goods_issued",
                OutboundDelivery.shipped_at >= thirty_days_ago,
                OutboundDelivery.shipped_at <= SalesOrder.requested_delivery_date,
            )
        )
        on_time_count = on_time_result.scalar_one() or 0

    otd_pct = (on_time_count / total_deliveries * 100) if total_deliveries > 0 else 0.0

    return O2CKpisOut(
        open_so_count=open_so_count,
        backorder_count=backorder_count,
        on_time_delivery_pct=round(otd_pct, 2),
        avg_order_value=avg_order_value,
        open_credit_holds=open_credit_holds,
        rma_open_count=rma_open_count,
        revenue_mtd=revenue_mtd,
        order_count_mtd=order_count_mtd,
        fill_rate_pct=fill_rate_pct,
    )


@router.get(
    "/backorders",
    response_model=list[BackorderLineOut],
    summary="Líneas SO en backorder con fecha disponible estimada",
    operation_id="salesBackorders",
)
async def get_backorders(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: int = Query(100, le=500),
) -> list[BackorderLineOut]:
    result = await db.execute(
        select(SalesOrderLine, SalesOrder)
        .join(SalesOrder, SalesOrderLine.so_id == SalesOrder.id)
        .where(
            SalesOrderLine.status == "open",
            SalesOrder.status.in_(["confirmed", "in_fulfillment"]),
        )
        .order_by(SalesOrder.requested_delivery_date.asc().nulls_last())
        .limit(limit)
    )
    rows = result.all()

    backorders = []
    for sol, so in rows:
        # Simple first_available_date heuristic: +30 days from today
        first_available = date.today() + timedelta(days=30)
        backorders.append(
            BackorderLineOut(
                so_line_id=sol.id,
                so_number=so.so_number,
                product_sku=sol.product_sku,
                qty=sol.qty,
                confirmed_qty=sol.confirmed_qty,
                first_available_date=first_available,
                customer_id=so.customer_id,
                requested_delivery_date=sol.requested_delivery_date or so.requested_delivery_date,
            )
        )
    return backorders

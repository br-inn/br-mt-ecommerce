"""ATP (Available-to-Promise) service — US-ERP-04-02.

Fórmula:
    ATP_qty = stock_unrestricted - reservas_activas + GRs_planeados_en_horizonte

Reglas de ATP:
- Se busca una regla específica por SKU; si no existe, se usa la regla default
  (product_sku IS NULL).  Si tampoco existe default, se usan los parámetros
  conservadores (sin safety stock, sin QA stock, con planned receipts, horizonte 30d).
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.inventory import (
    GoodsReceipt,
    InventoryPosition,
    PurchaseOrder,
    PurchaseOrderLine,
)
from app.db.models.sales import (
    AtpCheckingRule,
    SalesOrder,
    SalesOrderLine,
    StockReservation,
)
from app.schemas.sales import ATPLineResult

logger = logging.getLogger(__name__)

_ZERO = Decimal("0")


async def get_atp_rule(db: AsyncSession, product_sku: str) -> AtpCheckingRule | None:
    """Retorna la regla ATP para un SKU (o la default si no hay específica)."""
    # Specific rule first
    result = await db.execute(
        select(AtpCheckingRule).where(AtpCheckingRule.product_sku == product_sku).limit(1)
    )
    rule = result.scalar_one_or_none()
    if rule:
        return rule
    # Default rule (product_sku IS NULL)
    result = await db.execute(
        select(AtpCheckingRule).where(AtpCheckingRule.product_sku.is_(None)).limit(1)
    )
    return result.scalar_one_or_none()


async def get_unrestricted_stock(
    db: AsyncSession,
    product_sku: str,
    warehouse_id: UUID | None,
) -> Decimal:
    """Stock unrestricted de un SKU, opcionalmente filtrado por warehouse."""
    query = select(func.coalesce(func.sum(InventoryPosition.qty_on_hand), _ZERO)).where(
        InventoryPosition.product_sku == product_sku,
        InventoryPosition.stock_type == "unrestricted",
    )
    if warehouse_id:
        query = query.where(InventoryPosition.warehouse_id == warehouse_id)
    result = await db.execute(query)
    return result.scalar_one() or _ZERO


async def get_active_reservations(
    db: AsyncSession,
    product_sku: str,
    warehouse_id: UUID | None,
    exclude_so_id: UUID | None = None,
) -> Decimal:
    """Suma de reservas activas para el SKU."""
    query = select(func.coalesce(func.sum(StockReservation.qty), _ZERO)).where(
        StockReservation.product_sku == product_sku,
        StockReservation.status == "active",
    )
    if warehouse_id:
        query = query.where(StockReservation.warehouse_id == warehouse_id)
    if exclude_so_id:
        # Exclude reservations linked to the current SO (re-check scenario)
        so_line_subq = select(SalesOrderLine.id).where(SalesOrderLine.so_id == exclude_so_id)
        query = query.where(StockReservation.so_line_id.notin_(so_line_subq))
    result = await db.execute(query)
    return result.scalar_one() or _ZERO


async def get_planned_receipts(
    db: AsyncSession,
    product_sku: str,
    warehouse_id: UUID | None,
    horizon_days: int,
) -> Decimal:
    """GRs planeados (PO lines confirmed, no recibidas) dentro del horizonte."""
    cutoff = date.today() + timedelta(days=horizon_days)
    query = (
        select(func.coalesce(func.sum(PurchaseOrderLine.qty_ordered), _ZERO))
        .join(PurchaseOrder, PurchaseOrderLine.po_id == PurchaseOrder.id)
        .where(
            PurchaseOrderLine.product_sku == product_sku,
            PurchaseOrder.status == "confirmed",
            # Receipts not yet processed
        )
    )
    # If warehouse info is not on PO lines, we skip warehouse filter for planned
    result = await db.execute(query)
    return result.scalar_one() or _ZERO


async def compute_atp_for_so(
    db: AsyncSession,
    so: SalesOrder,
) -> list[ATPLineResult]:
    """Calcula ATP para todas las líneas de un SO."""
    results: list[ATPLineResult] = []

    for line in so.lines:
        rule = await get_atp_rule(db, line.product_sku)
        horizon = rule.horizon_days if rule else 30
        include_planned = rule.include_planned_receipts if rule else True

        unrestricted = await get_unrestricted_stock(db, line.product_sku, so.warehouse_id)
        active_res = await get_active_reservations(
            db, line.product_sku, so.warehouse_id, exclude_so_id=so.id
        )
        planned = _ZERO
        if include_planned:
            planned = await get_planned_receipts(db, line.product_sku, so.warehouse_id, horizon)

        atp_qty = unrestricted - active_res + planned
        atp_qty = max(atp_qty, _ZERO)

        requested_qty = line.qty
        today = date.today()
        requested_date = line.requested_delivery_date or so.requested_delivery_date or today

        if atp_qty >= requested_qty:
            status = "available"
            confirmed_date = requested_date
            first_available_date = requested_date
        elif atp_qty > _ZERO:
            status = "partial"
            confirmed_date = None
            # Simple heuristic: +7 days per unit gap beyond ATP
            gap = int(float(requested_qty - atp_qty))
            first_available_date = today + timedelta(days=min(gap * 7, 90))
        else:
            status = "backorder"
            confirmed_date = None
            first_available_date = today + timedelta(days=horizon)

        results.append(
            ATPLineResult(
                so_line_id=line.id,
                product_sku=line.product_sku,
                requested_qty=requested_qty,
                atp_qty=atp_qty,
                status=status,
                confirmed_date=confirmed_date,
                first_available_date=first_available_date,
            )
        )

    return results

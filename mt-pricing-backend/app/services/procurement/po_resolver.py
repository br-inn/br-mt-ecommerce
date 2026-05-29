"""Resolve or create a PurchaseOrder for an invoice's Order No. (F0.5, hybrid)."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.inventory import PurchaseOrder, PurchaseOrderLine
from app.repositories.purchase_order import PurchaseOrderRepository
from app.schemas.purchase_orders import PurchaseOrderCreate, PurchaseOrderLineCreate

_SUPPLIER = "mt_spain"
_SCHEME = "DIRECT_B2C"


async def resolve_or_create_po(
    session: AsyncSession,
    po_number: str,
    lines: list[tuple[str, Decimal, Decimal]],  # (sku, qty, unit_price_eur)
) -> PurchaseOrder:
    existing = (
        await session.execute(select(PurchaseOrder).where(PurchaseOrder.po_number == po_number))
    ).scalar_one_or_none()

    repo = PurchaseOrderRepository(session)
    if existing is not None:
        if existing.status == "draft":
            await repo.confirm(existing.id)
        return existing

    po = await repo.create(
        PurchaseOrderCreate(
            po_number=po_number,
            supplier_code=_SUPPLIER,
            currency="EUR",
            lines=[
                PurchaseOrderLineCreate(
                    sku=sku, scheme_code=_SCHEME, qty_ordered=qty, unit_price=price
                )
                for sku, qty, price in lines
            ],
        )
    )
    await repo.confirm(po.id)
    return po


async def find_po_line(session: AsyncSession, po_id: object, sku: str) -> PurchaseOrderLine | None:
    # Load purchase_order eagerly so GoodsReceiptRepository.create() can access
    # pol.purchase_order without hitting a lazy="noload" AttributeError.
    return (
        await session.execute(
            select(PurchaseOrderLine)
            .options(selectinload(PurchaseOrderLine.purchase_order))
            .where(
                PurchaseOrderLine.po_id == po_id,
                PurchaseOrderLine.sku == sku,
                PurchaseOrderLine.scheme_code == _SCHEME,
            )
        )
    ).scalar_one_or_none()

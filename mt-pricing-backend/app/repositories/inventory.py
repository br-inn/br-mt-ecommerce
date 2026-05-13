"""InventoryRepository — EP-INV-01 (US-INV-01-05).

Consultas de solo lectura sobre inventory_positions, goods_receipts y
purchase_order_lines para el dashboard de inventario.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.inventory import (
    GoodsReceipt,
    InventoryPosition,
    PurchaseOrder,
    PurchaseOrderLine,
)
from app.schemas.inventory import (
    InventoryPositionRead,
    InventorySummary,
    MAPHistoryPoint,
)


class InventoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # List positions
    # ------------------------------------------------------------------

    async def list_positions(
        self,
        *,
        sku: str | None = None,
        supplier_code: str | None = None,
        scheme_code: str | None = None,
        has_stock: bool | None = None,
    ) -> list[InventoryPositionRead]:
        """Lista posiciones con filtros opcionales.

        Hace un outer-join con products para traer el nombre del producto.
        """
        # Importación diferida para evitar circular imports con models
        from app.db.models.product import Product  # noqa: PLC0415

        stmt = (
            select(
                InventoryPosition,
                Product.erp_name.label("product_name"),
            )
            .outerjoin(Product, Product.sku == InventoryPosition.sku)
            .order_by(InventoryPosition.sku, InventoryPosition.scheme_code)
        )

        conditions: list[Any] = []
        if sku is not None:
            conditions.append(InventoryPosition.sku == sku)
        if supplier_code is not None:
            conditions.append(InventoryPosition.supplier_code == supplier_code)
        if scheme_code is not None:
            conditions.append(InventoryPosition.scheme_code == scheme_code)
        if has_stock is True:
            conditions.append(InventoryPosition.qty_on_hand > 0)
        elif has_stock is False:
            conditions.append(InventoryPosition.qty_on_hand == 0)

        if conditions:
            stmt = stmt.where(and_(*conditions))

        result = await self.session.execute(stmt)
        rows = result.all()

        out: list[InventoryPositionRead] = []
        for pos, product_name in rows:
            data = InventoryPositionRead.model_validate(pos)
            data.product_name = product_name
            out.append(data)
        return out

    # ------------------------------------------------------------------
    # Get by SKU
    # ------------------------------------------------------------------

    async def get_positions_by_sku(
        self, sku: str
    ) -> list[InventoryPositionRead]:
        """Devuelve todas las combinaciones scheme × supplier para un SKU."""
        return await self.list_positions(sku=sku)

    # ------------------------------------------------------------------
    # MAP history
    # ------------------------------------------------------------------

    async def get_map_history(
        self, sku: str, *, limit: int = 50
    ) -> list[MAPHistoryPoint]:
        """Historial de cambios MAP para un SKU (procesos completados).

        JOIN:
          goods_receipts gr
          → purchase_order_lines pol ON gr.po_line_id = pol.id
          → purchase_orders po ON pol.po_id = po.id
        WHERE pol.sku = :sku AND gr.status = 'processed' AND gr.map_after IS NOT NULL
        ORDER BY gr.received_at DESC
        LIMIT :limit
        """
        stmt = (
            select(
                GoodsReceipt.id.label("gr_id"),
                GoodsReceipt.map_before,
                GoodsReceipt.map_after,
                GoodsReceipt.qty_received,
                GoodsReceipt.received_at,
                PurchaseOrder.po_number,
            )
            .join(
                PurchaseOrderLine,
                GoodsReceipt.po_line_id == PurchaseOrderLine.id,
            )
            .join(
                PurchaseOrder,
                PurchaseOrderLine.po_id == PurchaseOrder.id,
            )
            .where(
                and_(
                    PurchaseOrderLine.sku == sku,
                    GoodsReceipt.status == "processed",
                    GoodsReceipt.map_after.is_not(None),
                )
            )
            .order_by(GoodsReceipt.received_at.desc())
            .limit(limit)
        )

        result = await self.session.execute(stmt)
        rows = result.all()

        return [
            MAPHistoryPoint(
                gr_id=row.gr_id,
                map_before=row.map_before,
                map_after=row.map_after,
                qty_received=row.qty_received,
                received_at=row.received_at,
                po_number=row.po_number,
            )
            for row in rows
        ]

    # ------------------------------------------------------------------
    # Summary / KPIs
    # ------------------------------------------------------------------

    async def get_summary(self) -> InventorySummary:
        """Agrega KPIs de inventario para el widget de dashboard."""
        # Total SKUs con stock (qty_on_hand > 0)
        skus_with_stock_stmt = select(
            func.count(InventoryPosition.id)
        ).where(InventoryPosition.qty_on_hand > 0)

        # Valor total inventario AED
        total_value_stmt = select(
            func.coalesce(
                func.sum(InventoryPosition.total_stock_value_aed), Decimal("0")
            )
        )

        # SKUs sin coste (qty_on_hand > 0 pero map_aed NULL)
        skus_without_cost_stmt = select(
            func.count(InventoryPosition.id)
        ).where(
            and_(
                InventoryPosition.qty_on_hand > 0,
                InventoryPosition.map_aed.is_(None),
            )
        )

        # GRs pendientes con más de 5 minutos de antigüedad
        five_min_ago = datetime.now(tz=timezone.utc) - timedelta(minutes=5)
        pending_gr_stmt = select(func.count(GoodsReceipt.id)).where(
            and_(
                GoodsReceipt.status == "pending",
                GoodsReceipt.created_at < five_min_ago,
            )
        )

        skus_result = await self.session.execute(skus_with_stock_stmt)
        value_result = await self.session.execute(total_value_stmt)
        no_cost_result = await self.session.execute(skus_without_cost_stmt)
        pending_result = await self.session.execute(pending_gr_stmt)

        return InventorySummary(
            total_skus_with_stock=skus_result.scalar_one() or 0,
            total_stock_value_aed=value_result.scalar_one() or Decimal("0"),
            skus_without_cost=no_cost_result.scalar_one() or 0,
            pending_gr_count=pending_result.scalar_one() or 0,
        )

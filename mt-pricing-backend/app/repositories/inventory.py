"""InventoryRepository — EP-INV-01 + EP-ERP-02.

Cubre:
  - Posiciones de inventario (lecturas + filtros 5D)
  - Movement Types y Stock Movements
  - Lot tracking y trazabilidad
  - Warehouse CRUD
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import and_, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.inventory import (
    GoodsReceipt,
    InventoryLot,
    InventoryPosition,
    JournalEntry,
    PurchaseOrder,
    PurchaseOrderLine,
    StockMovement,
    StockMovementType,
    Warehouse,
    WarehouseLocation,
    WarehouseZone,
)
from app.schemas.inventory import (
    InventoryAvailabilityRead,
    InventoryLotRead,
    InventoryPositionRead,
    InventorySummary,
    JournalEntryRead,
    LotTraceabilityRead,
    MAPHistoryPoint,
    StockMovementCreate,
    StockMovementRead,
    StockMovementTypeRead,
    TraceabilityDownstream,
    TraceabilityUpstream,
    WarehouseCreate,
    WarehouseLocationCreate,
    WarehouseLocationRead,
    WarehouseRead,
    WarehouseZoneCreate,
    WarehouseZoneRead,
)


class InventoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # -----------------------------------------------------------------------
    # EP-INV-01: Positions
    # -----------------------------------------------------------------------

    async def list_positions(
        self,
        *,
        sku: str | None = None,
        supplier_code: str | None = None,
        scheme_code: str | None = None,
        has_stock: bool | None = None,
        stock_type: str | None = None,
        warehouse_id: UUID | None = None,
        zone_id: UUID | None = None,
    ) -> list[InventoryPositionRead]:
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
        if stock_type is not None:
            conditions.append(InventoryPosition.stock_type == stock_type)
        if warehouse_id is not None:
            conditions.append(InventoryPosition.warehouse_id == warehouse_id)
        if zone_id is not None:
            # Filtrar por zone_id via location JOIN (si aplica)
            stmt = stmt.outerjoin(
                WarehouseLocation,
                WarehouseLocation.id == InventoryPosition.location_id,
            )
            conditions.append(WarehouseLocation.zone_id == zone_id)

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

    async def get_positions_by_sku(
        self, sku: str
    ) -> list[InventoryPositionRead]:
        return await self.list_positions(sku=sku)

    async def get_availability(self, sku: str) -> list[InventoryAvailabilityRead]:
        """Stock unrestricted de un SKU, agrupado por warehouse."""
        stmt = (
            select(
                InventoryPosition.product_id,
                InventoryPosition.sku,
                InventoryPosition.warehouse_id,
                func.sum(InventoryPosition.qty_on_hand).label("qty_available"),
            )
            .where(
                and_(
                    InventoryPosition.sku == sku,
                    InventoryPosition.stock_type == "unrestricted",
                    InventoryPosition.qty_on_hand > 0,
                )
            )
            .group_by(
                InventoryPosition.product_id,
                InventoryPosition.sku,
                InventoryPosition.warehouse_id,
            )
        )
        result = await self.session.execute(stmt)
        rows = result.all()
        return [
            InventoryAvailabilityRead(
                product_id=row.product_id,
                sku=row.sku,
                warehouse_id=row.warehouse_id,
                qty_available=row.qty_available,
            )
            for row in rows
        ]

    async def get_map_history(
        self, sku: str, *, limit: int = 50
    ) -> list[MAPHistoryPoint]:
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

    async def get_summary(self) -> InventorySummary:
        skus_with_stock_stmt = select(
            func.count(InventoryPosition.id)
        ).where(InventoryPosition.qty_on_hand > 0)

        total_value_stmt = select(
            func.coalesce(
                func.sum(InventoryPosition.total_stock_value_aed), Decimal("0")
            )
        )

        skus_without_cost_stmt = select(
            func.count(InventoryPosition.id)
        ).where(
            and_(
                InventoryPosition.qty_on_hand > 0,
                InventoryPosition.map_aed.is_(None),
            )
        )

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

    # -----------------------------------------------------------------------
    # US-ERP-02-01: Movement Types + Movements
    # -----------------------------------------------------------------------

    async def list_movement_types(self) -> list[StockMovementTypeRead]:
        stmt = (
            select(StockMovementType)
            .where(StockMovementType.is_active.is_(True))
            .order_by(StockMovementType.code)
        )
        result = await self.session.execute(stmt)
        return [
            StockMovementTypeRead.model_validate(row)
            for row in result.scalars().all()
        ]

    async def create_movement(
        self, payload: StockMovementCreate, posted_by: UUID
    ) -> StockMovementRead:
        movement_type = await self.session.get(StockMovementType, payload.movement_type_id)
        if not movement_type:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"movement_type_id {payload.movement_type_id} no encontrado",
            )

        movement = StockMovement(
            movement_type_id=payload.movement_type_id,
            product_id=payload.product_id,
            qty=payload.qty,
            lot_id=payload.lot_id,
            warehouse_id=payload.warehouse_id,
            location_id=payload.location_id,
            reference_id=payload.reference_id,
            reference_type=payload.reference_type,
            posted_by=posted_by,
            notes=payload.notes,
        )
        self.session.add(movement)
        await self.session.flush()

        if movement_type.posts_accounting:
            # Asiento genérico — cuentas por configurar según plan contable del cliente
            entry = JournalEntry(
                source_movement_id=movement.id,
                debit_account="1300",   # Inventario (activo)
                credit_account="4000",  # Proveedor / contraparte
                amount=abs(payload.qty),
                currency="AED",
            )
            self.session.add(entry)
            await self.session.flush()

        await self.session.refresh(movement)

        journal_entries = await self.session.execute(
            select(JournalEntry).where(
                JournalEntry.source_movement_id == movement.id
            )
        )
        entries = [
            JournalEntryRead.model_validate(e)
            for e in journal_entries.scalars().all()
        ]

        result = StockMovementRead.model_validate(movement)
        result.journal_entries = entries
        return result

    async def reverse_movement(
        self, movement_id: UUID, posted_by: UUID
    ) -> StockMovementRead:
        original = await self.session.get(StockMovement, movement_id)
        if not original:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"movement {movement_id} no encontrado",
            )

        reverse_payload = StockMovementCreate(
            movement_type_id=original.movement_type_id,
            product_id=original.product_id,
            qty=-original.qty,
            lot_id=original.lot_id,
            warehouse_id=original.warehouse_id,
            location_id=original.location_id,
            reference_id=original.reference_id,
            reference_type=original.reference_type,
            notes=f"Reversal de {movement_id}",
        )
        reversal = await self.create_movement(reverse_payload, posted_by)

        # Marcar el movimiento de reversión apuntando al original
        rev_obj = await self.session.get(StockMovement, reversal.id)
        if rev_obj:
            rev_obj.reversal_of = movement_id
            await self.session.flush()

        return reversal

    async def list_movements(self, *, limit: int = 50) -> list[StockMovementRead]:
        stmt = (
            select(StockMovement)
            .order_by(StockMovement.posted_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return [
            StockMovementRead.model_validate(m)
            for m in result.scalars().all()
        ]

    # -----------------------------------------------------------------------
    # US-ERP-02-03: Lots
    # -----------------------------------------------------------------------

    async def list_lots(
        self,
        *,
        product_id: UUID | None = None,
        quality_status: str | None = None,
    ) -> list[InventoryLotRead]:
        conditions: list[Any] = []
        if product_id is not None:
            conditions.append(InventoryLot.product_id == product_id)
        if quality_status is not None:
            conditions.append(InventoryLot.quality_status == quality_status)

        stmt = select(InventoryLot).order_by(InventoryLot.created_at.desc())
        if conditions:
            stmt = stmt.where(and_(*conditions))

        result = await self.session.execute(stmt)
        return [
            InventoryLotRead.model_validate(lot)
            for lot in result.scalars().all()
        ]

    async def get_lot(self, lot_id: UUID) -> InventoryLotRead:
        lot = await self.session.get(InventoryLot, lot_id)
        if not lot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"lot {lot_id} no encontrado",
            )
        return InventoryLotRead.model_validate(lot)

    async def patch_lot_quality(
        self, lot_id: UUID, quality_status: str
    ) -> InventoryLotRead:
        valid = {"released", "hold", "blocked"}
        if quality_status not in valid:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"quality_status debe ser uno de: {valid}",
            )
        lot = await self.session.get(InventoryLot, lot_id)
        if not lot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"lot {lot_id} no encontrado",
            )
        lot.quality_status = quality_status
        await self.session.flush()
        return InventoryLotRead.model_validate(lot)

    async def get_lot_traceability(self, lot_id: UUID) -> LotTraceabilityRead:
        lot = await self.session.get(InventoryLot, lot_id)
        if not lot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"lot {lot_id} no encontrado",
            )

        # Upstream: PO line → PO → supplier
        po_number: str | None = None
        supplier_code: str | None = None
        if lot.po_line_id:
            po_line_result = await self.session.execute(
                select(PurchaseOrderLine, PurchaseOrder)
                .join(PurchaseOrder, PurchaseOrderLine.po_id == PurchaseOrder.id)
                .where(PurchaseOrderLine.id == lot.po_line_id)
            )
            row = po_line_result.first()
            if row:
                _, po = row
                po_number = po.po_number
                supplier_code = po.supplier_code

        upstream = TraceabilityUpstream(
            lot_id=lot.id,
            lot_number=lot.lot_number,
            po_line_id=lot.po_line_id,
            po_number=po_number,
            supplier_code=supplier_code,
        )

        # Downstream: stock movements que usaron este lote y son salidas
        movements_result = await self.session.execute(
            select(StockMovement, StockMovementType)
            .join(
                StockMovementType,
                StockMovement.movement_type_id == StockMovementType.id,
            )
            .where(
                and_(
                    StockMovement.lot_id == lot_id,
                    StockMovementType.direction == "OUT",
                )
            )
            .order_by(StockMovement.posted_at.desc())
        )
        downstream = [
            TraceabilityDownstream(
                movement_id=sm.id,
                movement_type_code=smt.code,
                qty=sm.qty,
                reference_id=sm.reference_id,
                reference_type=sm.reference_type,
                posted_at=sm.posted_at,
            )
            for sm, smt in movements_result.all()
        ]

        return LotTraceabilityRead(
            lot=InventoryLotRead.model_validate(lot),
            upstream=upstream,
            downstream=downstream,
        )

    # -----------------------------------------------------------------------
    # US-ERP-02-04: Warehouses CRUD
    # -----------------------------------------------------------------------

    async def list_warehouses(self) -> list[WarehouseRead]:
        stmt = select(Warehouse).order_by(Warehouse.code)
        result = await self.session.execute(stmt)
        return [
            WarehouseRead.model_validate(wh)
            for wh in result.scalars().all()
        ]

    async def create_warehouse(self, payload: WarehouseCreate) -> WarehouseRead:
        wh = Warehouse(
            code=payload.code,
            name=payload.name,
            address=payload.address,
        )
        self.session.add(wh)
        await self.session.flush()
        return WarehouseRead.model_validate(wh)

    async def list_zones(self, warehouse_id: UUID) -> list[WarehouseZoneRead]:
        stmt = (
            select(WarehouseZone)
            .where(WarehouseZone.warehouse_id == warehouse_id)
            .order_by(WarehouseZone.code)
        )
        result = await self.session.execute(stmt)
        return [
            WarehouseZoneRead.model_validate(z)
            for z in result.scalars().all()
        ]

    async def create_zone(
        self, warehouse_id: UUID, payload: WarehouseZoneCreate
    ) -> WarehouseZoneRead:
        zone = WarehouseZone(
            warehouse_id=warehouse_id,
            code=payload.code,
            name=payload.name,
            zone_type=payload.zone_type,
        )
        self.session.add(zone)
        await self.session.flush()
        return WarehouseZoneRead.model_validate(zone)

    async def list_locations(self, zone_id: UUID) -> list[WarehouseLocationRead]:
        stmt = (
            select(WarehouseLocation)
            .where(WarehouseLocation.zone_id == zone_id)
            .order_by(WarehouseLocation.bin_code)
        )
        result = await self.session.execute(stmt)
        return [
            WarehouseLocationRead.model_validate(loc)
            for loc in result.scalars().all()
        ]

    async def create_location(
        self, zone_id: UUID, payload: WarehouseLocationCreate
    ) -> WarehouseLocationRead:
        loc = WarehouseLocation(
            zone_id=zone_id,
            bin_code=payload.bin_code,
            max_weight=payload.max_weight,
        )
        self.session.add(loc)
        await self.session.flush()
        return WarehouseLocationRead.model_validate(loc)

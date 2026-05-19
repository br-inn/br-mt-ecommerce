"""PurchaseOrderRepository — EP-INV-01 (US-INV-01-03)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.pagination import decode_cursor, encode_cursor
from app.db.models.inventory import GoodsReceipt, PurchaseOrder, PurchaseOrderLine
from app.schemas.purchase_orders import (
    PurchaseOrderCreate,
    PurchaseOrderUpdate,
)


def _encode_id_cursor(value: UUID | None) -> str | None:
    if value is None:
        return None
    return encode_cursor({"id": str(value)})


def _decode_id_cursor(cursor: str | None) -> UUID | None:
    if not cursor:
        return None
    payload = decode_cursor(cursor)
    raw = payload.get("id")
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_cursor", "title": "Cursor sin clave 'id'"},
        )
    try:
        return UUID(str(raw))
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_cursor", "title": "Cursor 'id' no es UUID"},
        ) from exc


class PurchaseOrderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------
    async def create(
        self, po_data: PurchaseOrderCreate, *, created_by: UUID | None = None
    ) -> PurchaseOrder:
        po = PurchaseOrder(
            po_number=po_data.po_number,
            supplier_code=po_data.supplier_code,
            currency=po_data.currency,
            po_type=po_data.po_type,
            notes=po_data.notes,
            status="draft",
            created_by=created_by,
        )
        self.session.add(po)
        await self.session.flush()

        for line_data in po_data.lines:
            price_source = "manual"
            unit_price = line_data.unit_price
            if po_data.supplier_code and line_data.sku:
                pir = await self._find_pir_by_sku(po_data.supplier_code, line_data.sku)
                if pir is not None:
                    unit_price = pir.price
                    price_source = "pir"

            line = PurchaseOrderLine(
                po_id=po.id,
                sku=line_data.sku,
                scheme_code=line_data.scheme_code,
                qty_ordered=line_data.qty_ordered,
                unit_price=unit_price,
                landed_cost_breakdown=line_data.landed_cost_breakdown,
                price_source=price_source,
            )
            self.session.add(line)

        await self.session.flush()
        return po

    async def _find_pir_by_sku(self, supplier_code: str, sku: str) -> Any:
        from datetime import date as _date

        from sqlalchemy import and_, or_

        from app.db.models.procurement import VendorProductCondition

        today = _date.today()
        stmt = (
            select(VendorProductCondition)
            .where(
                and_(
                    VendorProductCondition.vendor_id == supplier_code,
                    VendorProductCondition.product_sku == sku,
                    VendorProductCondition.is_active.is_(True),
                    VendorProductCondition.valid_from <= today,
                    or_(
                        VendorProductCondition.valid_to.is_(None),
                        VendorProductCondition.valid_to >= today,
                    ),
                )
            )
            .order_by(VendorProductCondition.valid_from.desc())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------
    async def get(self, po_id: UUID) -> PurchaseOrder | None:
        stmt = select(PurchaseOrder).where(PurchaseOrder.id == po_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_detail(self, po_id: UUID) -> PurchaseOrder | None:
        """Carga PO + lines eager, incluye gr_count como atributo."""
        stmt = (
            select(PurchaseOrder)
            .where(PurchaseOrder.id == po_id)
            .options(selectinload(PurchaseOrder.lines))
        )
        result = await self.session.execute(stmt)
        po = result.scalar_one_or_none()
        if po is None:
            return None
        po.gr_count = await self._count_grs(po_id)  # type: ignore[attr-defined]
        return po

    async def _count_grs(self, po_id: UUID) -> int:
        """Cuenta los GoodsReceipts asociados al PO via sus líneas."""
        from app.db.models.inventory import PurchaseOrderLine as POLine

        sub = select(POLine.id).where(POLine.po_id == po_id)
        stmt = select(func.count()).where(GoodsReceipt.po_line_id.in_(sub))
        result = await self.session.execute(stmt)
        return int(result.scalar_one() or 0)

    async def _has_processed_grs(self, po_id: UUID) -> bool:
        """True si hay GRs con status='processed' asociados al PO."""
        from app.db.models.inventory import PurchaseOrderLine as POLine

        sub = select(POLine.id).where(POLine.po_id == po_id)
        stmt = select(func.count()).where(
            GoodsReceipt.po_line_id.in_(sub),
            GoodsReceipt.status == "processed",
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one() or 0) > 0

    # ------------------------------------------------------------------
    # List
    # ------------------------------------------------------------------
    async def list(
        self,
        *,
        supplier_code: str | None = None,
        status: str | None = None,
        q: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[PurchaseOrder], str | None]:
        stmt = select(PurchaseOrder)

        clauses: list[Any] = []
        if supplier_code:
            clauses.append(PurchaseOrder.supplier_code == supplier_code)
        if status:
            clauses.append(PurchaseOrder.status == status)
        if q:
            clauses.append(PurchaseOrder.po_number.ilike(f"%{q}%"))
        if clauses:
            from sqlalchemy import and_
            stmt = stmt.where(and_(*clauses))

        cursor_uuid = _decode_id_cursor(cursor)
        if cursor_uuid is not None:
            stmt = stmt.where(PurchaseOrder.id > cursor_uuid)

        stmt = stmt.order_by(PurchaseOrder.id.asc()).limit(limit + 1)
        result = await self.session.execute(stmt)
        rows = list(result.scalars().all())

        next_cursor: str | None = None
        if len(rows) > limit:
            next_cursor = _encode_id_cursor(rows[limit - 1].id)
            rows = rows[:limit]

        return rows, next_cursor

    # ------------------------------------------------------------------
    # Update (solo draft)
    # ------------------------------------------------------------------
    async def update(self, po_id: UUID, update_data: PurchaseOrderUpdate) -> PurchaseOrder:
        po = await self.get(po_id)
        if po is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "po_not_found", "title": "Purchase Order no existe"},
            )
        if po.status != "draft":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "po_not_draft",
                    "title": f"Solo se pueden editar POs en estado 'draft' (actual: {po.status})",
                },
            )
        payload = update_data.model_dump(exclude_unset=True)
        for k, v in payload.items():
            setattr(po, k, v)
        await self.session.flush()
        return po

    # ------------------------------------------------------------------
    # Confirm (draft → confirmed)
    # ------------------------------------------------------------------
    async def confirm(self, po_id: UUID) -> PurchaseOrder:
        from datetime import datetime, timezone

        po = await self.get(po_id)
        if po is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "po_not_found", "title": "Purchase Order no existe"},
            )
        if po.status != "draft":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "po_not_draft",
                    "title": f"Solo se pueden confirmar POs en estado 'draft' (actual: {po.status})",
                },
            )
        stmt = select(func.count()).where(
            PurchaseOrderLine.po_id == po_id,
        )
        result = await self.session.execute(stmt)
        line_count = int(result.scalar_one() or 0)
        if line_count == 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "po_no_lines",
                    "title": "El PO debe tener al menos 1 línea con qty_ordered > 0",
                },
            )
        po.status = "confirmed"
        po.confirmed_at = datetime.now(tz=timezone.utc)
        await self.session.flush()
        return po

    # ------------------------------------------------------------------
    # Cancel (→ cancelled, valida sin GRs procesados)
    # ------------------------------------------------------------------
    async def cancel(self, po_id: UUID) -> PurchaseOrder:
        po = await self.get(po_id)
        if po is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "po_not_found", "title": "Purchase Order no existe"},
            )
        if po.status == "cancelled":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "po_already_cancelled", "title": "El PO ya está cancelado"},
            )
        if await self._has_processed_grs(po_id):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "po_has_processed_grs",
                    "title": "No se puede cancelar un PO con GRs procesados",
                },
            )
        po.status = "cancelled"
        await self.session.flush()
        return po

    # ------------------------------------------------------------------
    # Delete (solo draft)
    # ------------------------------------------------------------------
    async def delete(self, po_id: UUID) -> None:
        po = await self.get(po_id)
        if po is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "po_not_found", "title": "Purchase Order no existe"},
            )
        if po.status != "draft":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "po_not_draft",
                    "title": f"Solo se pueden eliminar POs en estado 'draft' (actual: {po.status})",
                },
            )
        await self.session.delete(po)
        await self.session.flush()

    # ------------------------------------------------------------------
    # Lines
    # ------------------------------------------------------------------
    async def add_line(
        self, po_id: UUID, line_data: Any
    ) -> PurchaseOrderLine:
        po = await self.get(po_id)
        if po is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "po_not_found", "title": "Purchase Order no existe"},
            )
        if po.status != "draft":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "po_not_draft",
                    "title": f"Solo se pueden agregar líneas en estado 'draft' (actual: {po.status})",
                },
            )
        line = PurchaseOrderLine(
            po_id=po_id,
            sku=line_data.sku,
            scheme_code=line_data.scheme_code,
            qty_ordered=line_data.qty_ordered,
            unit_price=line_data.unit_price,
            landed_cost_breakdown=line_data.landed_cost_breakdown,
        )
        self.session.add(line)
        await self.session.flush()
        return line

    async def get_line(self, po_id: UUID, line_id: UUID) -> PurchaseOrderLine | None:
        stmt = select(PurchaseOrderLine).where(
            PurchaseOrderLine.id == line_id,
            PurchaseOrderLine.po_id == po_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_line(
        self, po_id: UUID, line_id: UUID, update_data: Any
    ) -> PurchaseOrderLine:
        po = await self.get(po_id)
        if po is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "po_not_found", "title": "Purchase Order no existe"},
            )
        if po.status != "draft":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "po_not_draft",
                    "title": f"Solo se pueden editar líneas en estado 'draft' (actual: {po.status})",
                },
            )
        line = await self.get_line(po_id, line_id)
        if line is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "line_not_found", "title": "Línea no existe en este PO"},
            )
        payload = update_data.model_dump(exclude_unset=True)
        for k, v in payload.items():
            setattr(line, k, v)
        await self.session.flush()
        return line

    async def delete_line(self, po_id: UUID, line_id: UUID) -> None:
        po = await self.get(po_id)
        if po is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "po_not_found", "title": "Purchase Order no existe"},
            )
        if po.status != "draft":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "po_not_draft",
                    "title": f"Solo se pueden eliminar líneas en estado 'draft' (actual: {po.status})",
                },
            )
        line = await self.get_line(po_id, line_id)
        if line is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "line_not_found", "title": "Línea no existe en este PO"},
            )
        await self.session.delete(line)
        await self.session.flush()

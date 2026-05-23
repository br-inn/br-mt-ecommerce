"""GoodsReceiptRepository — EP-INV-01 (US-INV-01-04)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.pagination import decode_cursor, encode_cursor
from app.db.models.inventory import (
    GoodsReceipt,
    PurchaseOrder,
    PurchaseOrderLine,
)
from app.schemas.goods_receipts import GoodsReceiptCreate, GoodsReceiptStatusRead


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


class GoodsReceiptRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    async def create(
        self,
        gr_data: GoodsReceiptCreate,
        *,
        received_by: UUID | None = None,
    ) -> GoodsReceipt:
        """Valida, crea el GR (status=pending), actualiza qty_received en la línea
        y el status del PO. No hace commit — el caller (route) es responsable.
        """
        # 1. Cargar la línea con su PO
        stmt = (
            select(PurchaseOrderLine)
            .options(selectinload(PurchaseOrderLine.purchase_order))
            .where(PurchaseOrderLine.id == gr_data.po_line_id)
        )
        result = await self.session.execute(stmt)
        pol = result.scalar_one_or_none()

        if pol is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "po_line_not_found",
                    "title": "Línea de PO no encontrada",
                },
            )

        po = pol.purchase_order
        if po.status not in ("confirmed", "partial"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "po_not_open",
                    "title": (
                        f"Solo se puede recibir contra POs en estado 'confirmed' o 'partial' "
                        f"(estado actual: {po.status})"
                    ),
                },
            )

        # 2. Validar qty > 0 (el schema Field(gt=0) ya lo garantiza, pero chequeamos en repo)
        if gr_data.qty_received <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "qty_invalid", "title": "qty_received debe ser > 0"},
            )

        # 3. Validar que no se reciba más de lo pedido (salvo force=True)
        pending = pol.qty_ordered - pol.qty_received
        if gr_data.qty_received > pending and not gr_data.force:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "qty_exceeds_ordered",
                    "title": (
                        f"qty_received ({gr_data.qty_received}) supera la cantidad pendiente "
                        f"({pending}). Usa force=true para sobrepasar."
                    ),
                },
            )

        # 4. INSERT GoodsReceipt con status='pending'
        gr = GoodsReceipt(
            po_line_id=gr_data.po_line_id,
            qty_received=gr_data.qty_received,
            received_by=received_by,
            actual_unit_price=gr_data.actual_unit_price,
            actual_breakdown=gr_data.actual_breakdown or {},
            notes=gr_data.notes,
            status="pending",
        )
        if gr_data.received_at is not None:
            gr.received_at = gr_data.received_at

        self.session.add(gr)
        await self.session.flush()  # Obtener gr.id antes de usarlo

        # 5. UPDATE po_line.qty_received
        pol.qty_received = pol.qty_received + gr_data.qty_received
        await self.session.flush()

        # 6. UPDATE PO status
        await self._update_po_status(po)
        await self.session.flush()

        # Eager-load la relación po_line para que el serializer pueda acceder a ella
        await self.session.refresh(gr, ["po_line_id"])
        # Re-query con eager load para devolver po_line
        gr_loaded = await self.get(gr.id)
        assert gr_loaded is not None
        return gr_loaded

    async def _update_po_status(self, po: PurchaseOrder) -> None:
        """Recalcula el estado del PO basado en sus líneas."""
        stmt = select(PurchaseOrderLine).where(PurchaseOrderLine.po_id == po.id)
        result = await self.session.execute(stmt)
        lines = result.scalars().all()

        if not lines:
            return

        all_received = all(line.qty_received >= line.qty_ordered for line in lines)
        po.status = "received" if all_received else "partial"

    # ------------------------------------------------------------------
    # Get
    # ------------------------------------------------------------------

    async def get(self, gr_id: UUID) -> GoodsReceipt | None:
        stmt = (
            select(GoodsReceipt)
            .options(
                selectinload(GoodsReceipt.po_line).selectinload(PurchaseOrderLine.purchase_order)
            )
            .where(GoodsReceipt.id == gr_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    # ------------------------------------------------------------------
    # Get Status (endpoint polling ligero)
    # ------------------------------------------------------------------

    async def get_status(self, gr_id: UUID) -> GoodsReceiptStatusRead:
        gr = await self.session.get(GoodsReceipt, gr_id)
        if gr is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "gr_not_found", "title": "Goods Receipt no encontrado"},
            )
        error_summary: str | None = None
        if gr.status == "error" and gr.notes:
            error_summary = gr.notes[:200]

        return GoodsReceiptStatusRead(
            gr_id=gr.id,
            status=gr.status,
            map_before=gr.map_before,
            map_after=gr.map_after,
            processed_at=gr.processed_at,
            error_summary=error_summary,
        )

    # ------------------------------------------------------------------
    # List
    # ------------------------------------------------------------------

    async def list(
        self,
        *,
        sku: str | None = None,
        po_id: UUID | None = None,
        status_filter: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[GoodsReceipt], str | None]:
        stmt = select(GoodsReceipt).options(
            selectinload(GoodsReceipt.po_line).selectinload(PurchaseOrderLine.purchase_order)
        )

        clauses: list[Any] = []
        if sku:
            # Filtra por SKU de la línea asociada
            sub = select(PurchaseOrderLine.id).where(PurchaseOrderLine.sku == sku)
            clauses.append(GoodsReceipt.po_line_id.in_(sub))
        if po_id:
            # Filtra por PO — todas las líneas de ese PO
            sub_po = select(PurchaseOrderLine.id).where(PurchaseOrderLine.po_id == po_id)
            clauses.append(GoodsReceipt.po_line_id.in_(sub_po))
        if status_filter:
            clauses.append(GoodsReceipt.status == status_filter)

        if clauses:
            stmt = stmt.where(and_(*clauses))

        cursor_uuid = _decode_id_cursor(cursor)
        if cursor_uuid is not None:
            stmt = stmt.where(GoodsReceipt.id > cursor_uuid)

        stmt = stmt.order_by(GoodsReceipt.id.asc()).limit(limit + 1)
        result = await self.session.execute(stmt)
        rows = list(result.scalars().all())

        next_cursor: str | None = None
        if len(rows) > limit:
            next_cursor = _encode_id_cursor(rows[limit - 1].id)
            rows = rows[:limit]

        return rows, next_cursor

    # ------------------------------------------------------------------
    # Mark error
    # ------------------------------------------------------------------

    async def mark_error(self, gr_id: UUID, error_msg: str) -> None:
        gr = await self.session.get(GoodsReceipt, gr_id)
        if gr is None:
            return
        gr.status = "error"
        gr.notes = error_msg[:4000]
        await self.session.flush()

    # ------------------------------------------------------------------
    # Retry
    # ------------------------------------------------------------------

    async def retry(self, gr_id: UUID) -> GoodsReceipt:
        gr = await self.session.get(GoodsReceipt, gr_id)
        if gr is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "gr_not_found", "title": "Goods Receipt no encontrado"},
            )
        if gr.status != "error":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "gr_not_error",
                    "title": (
                        f"Solo se puede reintentar un GR en estado 'error' "
                        f"(estado actual: {gr.status})"
                    ),
                },
            )
        gr.status = "pending"
        gr.processed_at = None
        await self.session.flush()

        # Devolver con eager load
        loaded = await self.get(gr_id)
        assert loaded is not None
        return loaded

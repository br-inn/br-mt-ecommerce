"""Orchestrate invoice ingestion → goods receipts (F0.5)."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.product import Product
from app.repositories.goods_receipt import GoodsReceiptRepository
from app.schemas.goods_receipts import GoodsReceiptCreate
from app.schemas.invoice_imports import (
    InvoiceIngestItem,
    InvoiceIngestResult,
    InvoiceParseResult,
)
from app.services.procurement.cost_builder import build_actual_breakdown
from app.services.procurement.po_resolver import find_po_line, resolve_or_create_po


class InvoiceIngestService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def ingest(
        self,
        *,
        commercial: InvoiceParseResult,
        import_inv: InvoiceParseResult,
        tariff_pct: Decimal,
        confirm: bool,
    ) -> InvoiceIngestResult:
        import_by_code = {ln.code: ln for ln in import_inv.lines}
        order_no = commercial.order_refs[0] if commercial.order_refs else None
        result = InvoiceIngestResult()

        for line in commercial.lines:
            imp = import_by_code.get(line.code)
            import_value = imp.unit_price if imp else Decimal("0")
            breakdown = build_actual_breakdown(line.unit_price, import_value, tariff_pct)
            duty = Decimal(breakdown["import_duty_eur"])
            item = InvoiceIngestItem(
                code=line.code,
                commercial_eur=line.unit_price,
                import_value_eur=import_value,
                duty_eur=duty,
                qty=line.quantity,
                po_number=order_no,
                po_action="matched",
                status="ok",
            )
            if not confirm:
                result.items.append(item)
                continue
            try:
                if order_no is None:
                    raise ValueError("invoice has no Order No.")
                po = await resolve_or_create_po(
                    self._session,
                    order_no,
                    [(line.code, line.quantity, line.unit_price)],
                )
                item.po_action = "matched" if po.status == "partial" else "created"
                pol = await find_po_line(self._session, po.id, line.code)
                if pol is None:
                    raise ValueError(f"no PO line for sku {line.code}")
                gr_repo = GoodsReceiptRepository(self._session)
                await gr_repo.create(
                    GoodsReceiptCreate(
                        po_line_id=pol.id,
                        qty_received=line.quantity,
                        actual_breakdown=breakdown,
                        notes=(
                            f"invoice={commercial.invoice_number} incoterm={commercial.incoterms}"
                        ),
                    )
                )
                if line.intrastat_code:
                    await self._session.execute(
                        update(Product)
                        .where(Product.sku == line.code)
                        .values(hs_code=line.intrastat_code)
                    )
                result.created += 1
            except Exception as e:
                item.status = "error"
                item.detail = str(e)
                result.errors += 1
            result.items.append(item)

        return result

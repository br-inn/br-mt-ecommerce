"""Orchestrate invoice ingestion → goods receipts (F0.5)."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select as _select
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.db.models.procurement import VendorInvoice
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
        result = InvoiceIngestResult()

        already: set[str] = set()
        if commercial.invoice_number:
            seen = (
                (
                    await self._session.execute(
                        _select(VendorInvoice.match_details).where(
                            VendorInvoice.invoice_number == commercial.invoice_number
                        )
                    )
                )
                .scalars()
                .all()
            )
            for md in seen:
                already.update((md or {}).get("codes", []))

        for line in commercial.lines:
            # FIX 2: resolve po_number per line; fall back to single ref or error
            po_number: str | None = line.order_no
            if po_number is None:
                if len(commercial.order_refs) == 1:
                    po_number = commercial.order_refs[0]
                # else: po_number stays None → error recorded below

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
                po_number=po_number,
                po_action="matched",
                status="ok",
            )

            # FIX 3: flag missing import line
            if imp is None:
                item.detail = "no matching import line; duty=0"

            if confirm and line.code in already:
                item.status = "skipped"
                result.skipped += 1
                result.items.append(item)
                continue
            if not confirm:
                result.items.append(item)
                continue
            try:
                if po_number is None:
                    raise ValueError("cannot determine Order No. for line")
                po, was_created = await resolve_or_create_po(
                    self._session,
                    po_number,
                    [(line.code, line.quantity, line.unit_price)],
                )
                # FIX 4: set po_action from was_created, not from post-receipt status
                item.po_action = "created" if was_created else "matched"
                item.po_number = po_number
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

        if confirm and result.created:
            import datetime as _dt

            from app.db.models.inventory import PurchaseOrder

            ok_items = [i for i in result.items if i.status == "ok"]
            ok_codes = [i.code for i in ok_items]
            new_total = sum(
                (Decimal(str(i.commercial_eur)) * Decimal(str(i.qty)) for i in ok_items),
                Decimal("0"),
            )

            # FIX 1: upsert VendorInvoice — merge codes if row already exists
            inv_number = commercial.invoice_number or ""
            existing_vi = (
                await self._session.execute(
                    _select(VendorInvoice).where(VendorInvoice.invoice_number == inv_number)
                )
            ).scalar_one_or_none()

            if existing_vi is not None:
                # Merge new ok-codes into existing match_details (dedup)
                md = existing_vi.match_details or {}
                existing_codes: list[str] = md.get("codes", [])
                merged = existing_codes + [c for c in ok_codes if c not in existing_codes]
                md["codes"] = merged
                existing_vi.match_details = md
                existing_vi.total_amount = existing_vi.total_amount + new_total
                flag_modified(existing_vi, "match_details")
            else:
                # Derive a representative PO id for the marker row.
                # Use the PO of the first ok item (or the single order_ref if available).
                first_po_number = next((i.po_number for i in ok_items if i.po_number), None) or (
                    commercial.order_refs[0] if commercial.order_refs else None
                )
                po_row = None
                if first_po_number:
                    po_row = (
                        await self._session.execute(
                            _select(PurchaseOrder).where(PurchaseOrder.po_number == first_po_number)
                        )
                    ).scalar_one_or_none()

                if po_row is None:
                    # Fallback: skip VendorInvoice creation if no PO can be found
                    await self._session.flush()
                    return result

                self._session.add(
                    VendorInvoice(
                        invoice_number=inv_number,
                        vendor_id="mt_spain",
                        po_id=po_row.id,
                        invoice_date=_dt.date.today(),
                        total_amount=new_total,
                        currency="EUR",
                        status="pending",
                        match_details={"codes": ok_codes},
                    )
                )
            await self._session.flush()

        return result

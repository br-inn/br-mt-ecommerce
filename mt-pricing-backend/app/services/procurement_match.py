"""Three-way match service — US-ERP-03-04.

Compara factura vs GR vs PO y aplica tolerancias configuradas.

Nota sobre el modelo de inventario existente:
- PurchaseOrder     — no tiene total_amount; se calcula desde líneas.
- PurchaseOrderLine — campos: qty_ordered, qty_received, unit_price.
- GoodsReceipt      — por línea de PO; campo: qty_received.
- VendorInvoice     — nueva tabla; po_id apunta a purchase_orders.id,
                       gr_id no existe en el modelo anterior (tabla nueva).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.inventory import GoodsReceipt, PurchaseOrder, PurchaseOrderLine
from app.db.models.procurement import InvoiceTolerance, VendorInvoice


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pct_diff(a: Decimal, b: Decimal) -> Decimal:
    """Retorna diferencia porcentual (a - b) / b * 100. Cero si b == 0."""
    if b == 0:
        return Decimal("0")
    return ((a - b) / b * 100).quantize(Decimal("0.0001"))


# ---------------------------------------------------------------------------
# Core function
# ---------------------------------------------------------------------------


async def perform_three_way_match(
    invoice_id: UUID,
    session: AsyncSession,
) -> dict[str, Any]:
    """Ejecuta 3-way match y persiste resultado en invoice.match_details.

    Algoritmo:
    1. Suma qty_ordered y (qty_ordered * unit_price) de las PO lines.
    2. Suma qty_received de los GoodsReceipts ligados a esas PO lines.
    3. Compara invoice.total_amount vs PO amount calculado.
    4. Aplica tolerancias activas de InvoiceTolerance.
    5. Retorna status: matched / tolerance_ok / blocked.

    Returns:
        dict con breakdown del match y nuevo status de la factura.
    """
    # 1. Cargar factura
    invoice: VendorInvoice | None = await session.get(VendorInvoice, invoice_id)
    if invoice is None:
        raise ValueError(f"Factura {invoice_id} no encontrada")

    if invoice.status != "pending":
        raise ValueError(
            f"Solo facturas en estado 'pending' pueden ejecutar 3-way match "
            f"(actual: {invoice.status})"
        )

    # 2. Cargar PO
    po: PurchaseOrder | None = await session.get(PurchaseOrder, invoice.po_id)
    if po is None:
        raise ValueError(f"PO {invoice.po_id} no encontrada")

    # 3. Cargar líneas de PO
    po_lines_result = await session.execute(
        select(PurchaseOrderLine).where(PurchaseOrderLine.po_id == invoice.po_id)
    )
    po_lines = list(po_lines_result.scalars().all())
    if not po_lines:
        raise ValueError(f"PO {invoice.po_id} no tiene líneas")

    po_total_qty = sum(l.qty_ordered for l in po_lines)
    po_total_amount = sum(l.qty_ordered * l.unit_price for l in po_lines)
    po_line_ids = [l.id for l in po_lines]

    # Para precio unitario de referencia (solo aplica si hay 1 línea)
    po_unit_price: Decimal | None = po_lines[0].unit_price if len(po_lines) == 1 else None

    # 4. Cargar GRs ligados a las líneas de esta PO
    gr_result = await session.execute(
        select(GoodsReceipt).where(GoodsReceipt.po_line_id.in_(po_line_ids))
    )
    grs = list(gr_result.scalars().all())
    gr_total_qty: Decimal | None = sum(g.qty_received for g in grs) if grs else None

    # 5. Cantidad facturada estimada (solo disponible si PO es de 1 línea)
    invoice_qty: Decimal | None = None
    if po_unit_price and po_unit_price > 0:
        invoice_qty = (invoice.total_amount / po_unit_price).quantize(Decimal("0.0001"))

    # 6. Diferencias porcentuales
    ref_qty = gr_total_qty if gr_total_qty is not None else po_total_qty
    qty_diff_pct = _pct_diff(invoice_qty, ref_qty) if invoice_qty is not None else Decimal("0")
    price_diff_pct = _pct_diff(invoice.total_amount, po_total_amount)

    # 7. Cargar tolerancias activas
    tol_result = await session.execute(
        select(InvoiceTolerance).where(InvoiceTolerance.is_active.is_(True))
    )
    tolerances = list(tol_result.scalars().all())

    # Tolerancia aplicable: preferir vendor_invoice, fallback a cualquier activa
    applied_tol: InvoiceTolerance | None = next(
        (t for t in tolerances if t.document_type == "vendor_invoice"), None
    ) or (tolerances[0] if tolerances else None)

    applied_tolerance_key: str | None = None
    pct_limit: Decimal | None = None
    absolute_limit: Decimal | None = None
    if applied_tol:
        applied_tolerance_key = applied_tol.tolerance_key
        pct_limit = applied_tol.pct_limit
        absolute_limit = applied_tol.absolute_limit

    # 8. Determinar status
    abs_amount_diff = abs(invoice.total_amount - po_total_amount)

    if price_diff_pct == 0 and qty_diff_pct == 0:
        new_status = "matched"
    elif pct_limit is not None or absolute_limit is not None:
        within_pct = pct_limit is None or abs(price_diff_pct) <= pct_limit
        within_abs = absolute_limit is None or abs_amount_diff <= absolute_limit
        new_status = "tolerance_ok" if (within_pct and within_abs) else "blocked"
    else:
        # Sin tolerancias configuradas: cualquier diferencia → blocked
        new_status = "blocked"

    # 9. Construir breakdown
    match_details: dict[str, Any] = {
        "po_qty": str(po_total_qty),
        "gr_qty": str(gr_total_qty) if gr_total_qty is not None else None,
        "invoice_qty": str(invoice_qty) if invoice_qty is not None else None,
        "po_price": str(po_total_amount),
        "invoice_price": str(invoice.total_amount),
        "qty_diff_pct": str(qty_diff_pct),
        "price_diff_pct": str(price_diff_pct),
        "applied_tolerance": applied_tolerance_key,
        "pct_limit": str(pct_limit) if pct_limit is not None else None,
        "absolute_limit": str(absolute_limit) if absolute_limit is not None else None,
        "status": new_status,
    }

    # 10. Persistir
    invoice.status = new_status
    invoice.payment_block = new_status == "blocked"
    invoice.match_details = match_details
    session.add(invoice)

    return match_details

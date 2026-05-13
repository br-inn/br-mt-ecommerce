"""Billing service — EP-ERP-05.

Lógica de negocio:
- Crear/leer facturas y líneas
- Post invoice → FI entries + customer_open_items
- Cancel / reverse invoice
- Dunning check
- ZATCA QR + XML stub
- AR aging
- Billing KPIs
"""

from __future__ import annotations

import base64
import hashlib
import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.billing import (
    DunningHistory,
    DunningLevel,
    EInvoiceSubmission,
    Invoice,
    InvoiceLine,
    PaymentPromise,
)
from app.schemas.billing import (
    ARAgingBucket,
    BillingKPIs,
    EInvoiceSubmitRequest,
    InvoiceCreate,
    InvoicePatch,
    PaymentPromiseCreate,
    PaymentPromisePatch,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _compute_line_totals(
    qty: Decimal,
    unit_price: Decimal,
    discount_pct: Decimal,
    tax_rate: Decimal,
) -> tuple[Decimal, Decimal]:
    """Retorna (line_total, tax_amount). line_total incluye impuesto."""
    net = qty * unit_price * (1 - discount_pct / 100)
    tax = net * (tax_rate / 100)
    return (net + tax).quantize(Decimal("0.0001")), tax.quantize(Decimal("0.0001"))


def _generate_invoice_number(prefix: str = "INV") -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    short = str(uuid4()).split("-")[0].upper()
    return f"{prefix}-{ts}-{short}"


def _zatca_qr(
    seller_name: str,
    vat_number: str,
    invoice_date: str,
    total: str,
    vat_amount: str,
) -> str:
    """SHA-256 de campos clave, base64-encoded."""
    payload = f"{seller_name}|{vat_number}|{invoice_date}|{total}|{vat_amount}"
    digest = hashlib.sha256(payload.encode()).digest()
    return base64.b64encode(digest).decode()


def _build_xml_stub(invoice: Invoice) -> str:
    """XML payload básico — stub con campos clave del invoice."""
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f"<Invoice>\n"
        f"  <ID>{invoice.invoice_number}</ID>\n"
        f"  <IssueDate>{invoice.invoice_date}</IssueDate>\n"
        f"  <CustomerID>{invoice.customer_id}</CustomerID>\n"
        f"  <TotalAmount>{invoice.total_amount}</TotalAmount>\n"
        f"  <TaxAmount>{invoice.tax_amount}</TaxAmount>\n"
        f"  <Currency>{invoice.currency}</Currency>\n"
        f"</Invoice>"
    )


# ---------------------------------------------------------------------------
# Invoice CRUD
# ---------------------------------------------------------------------------

async def create_invoice(session: AsyncSession, data: InvoiceCreate) -> Invoice:
    invoice = Invoice(
        invoice_number=data.invoice_number or _generate_invoice_number(),
        invoice_type=data.invoice_type,
        delivery_id=data.delivery_id,
        so_id=data.so_id,
        customer_id=data.customer_id,
        invoice_date=data.invoice_date or date.today(),
        due_date=data.due_date,
        currency=data.currency,
        payment_terms=data.payment_terms,
    )
    # Compute lines
    subtotal = Decimal("0")
    total_tax = Decimal("0")
    for ld in data.lines:
        lt, ta = _compute_line_totals(ld.qty, ld.unit_price, ld.discount_pct, ld.tax_rate)
        net = ld.qty * ld.unit_price * (1 - ld.discount_pct / 100)
        net = net.quantize(Decimal("0.0001"))
        subtotal += net
        total_tax += ta
        line = InvoiceLine(
            product_sku=ld.product_sku,
            so_line_id=ld.so_line_id,
            description=ld.description,
            qty=ld.qty,
            unit_price=ld.unit_price,
            discount_pct=ld.discount_pct,
            tax_rate=ld.tax_rate,
            line_total=lt,
            tax_amount=ta,
        )
        invoice.lines.append(line)

    invoice.subtotal = subtotal
    invoice.tax_amount = total_tax
    invoice.total_amount = subtotal + total_tax

    session.add(invoice)
    await session.flush()
    await session.refresh(invoice)
    return invoice


async def list_invoices(
    session: AsyncSession,
    customer_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Invoice]:
    q = select(Invoice)
    if customer_id:
        q = q.where(Invoice.customer_id == customer_id)
    if status:
        q = q.where(Invoice.status == status)
    q = q.order_by(Invoice.created_at.desc()).limit(limit).offset(offset)
    result = await session.execute(q)
    return list(result.scalars().all())


async def get_invoice(session: AsyncSession, invoice_id: UUID) -> Invoice | None:
    result = await session.execute(select(Invoice).where(Invoice.id == invoice_id))
    return result.scalar_one_or_none()


async def patch_invoice(
    session: AsyncSession,
    invoice: Invoice,
    data: InvoicePatch,
) -> Invoice:
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(invoice, field, value)
    await session.flush()
    await session.refresh(invoice)
    return invoice


async def get_invoice_chain(session: AsyncSession, invoice: Invoice) -> dict[str, Any]:
    chain: dict[str, Any] = {"invoice": invoice, "so": None, "delivery": None}
    if invoice.so_id:
        from app.db.models.sales import SalesOrder
        r = await session.execute(select(SalesOrder).where(SalesOrder.id == invoice.so_id))
        so = r.scalar_one_or_none()
        if so:
            chain["so"] = {
                "id": str(so.id),
                "so_number": so.so_number,
                "customer_id": so.customer_id,
                "status": so.status,
                "total_amount": str(so.total_amount) if so.total_amount else None,
            }
    if invoice.delivery_id:
        from app.db.models.sales import OutboundDelivery
        r = await session.execute(
            select(OutboundDelivery).where(OutboundDelivery.id == invoice.delivery_id)
        )
        dlv = r.scalar_one_or_none()
        if dlv:
            chain["delivery"] = {
                "id": str(dlv.id),
                "delivery_number": dlv.delivery_number,
                "status": dlv.status,
                "shipped_at": dlv.shipped_at.isoformat() if dlv.shipped_at else None,
            }
    return chain


async def create_invoice_from_delivery(
    session: AsyncSession,
    delivery_id: UUID,
    created_by: UUID | None = None,
) -> Invoice:
    """Crea invoice copiando precio del SO lines asociados al delivery."""
    from app.db.models.sales import OutboundDelivery, OutboundDeliveryLine, SalesOrderLine

    r = await session.execute(
        select(OutboundDelivery).where(OutboundDelivery.id == delivery_id)
    )
    delivery = r.scalar_one_or_none()
    if not delivery:
        raise ValueError(f"Delivery {delivery_id} not found")

    # Load delivery lines
    r2 = await session.execute(
        select(OutboundDeliveryLine).where(OutboundDeliveryLine.delivery_id == delivery_id)
    )
    dlv_lines = list(r2.scalars().all())

    inv_lines: list[InvoiceLineCreate_] = []
    for dl in dlv_lines:
        # Get unit_price from SO line
        r3 = await session.execute(
            select(SalesOrderLine).where(SalesOrderLine.id == dl.so_line_id)
        )
        sol = r3.scalar_one_or_none()
        unit_price = sol.unit_price if sol else Decimal("0")
        discount_pct = sol.discount_pct if sol else Decimal("0")

        inv_lines.append(
            InvoiceLineCreate_(
                product_sku=dl.product_sku,
                so_line_id=dl.so_line_id,
                qty=dl.qty_planned,
                unit_price=unit_price,
                discount_pct=discount_pct,
            )
        )

    inv_number = _generate_invoice_number("INV")
    # Get customer_id from SO
    customer_id = "unknown"
    if delivery.so_id:
        from app.db.models.sales import SalesOrder
        r4 = await session.execute(select(SalesOrder).where(SalesOrder.id == delivery.so_id))
        so = r4.scalar_one_or_none()
        if so:
            customer_id = so.customer_id

    invoice = Invoice(
        invoice_number=inv_number,
        invoice_type="STANDARD",
        delivery_id=delivery_id,
        so_id=delivery.so_id,
        customer_id=customer_id,
        invoice_date=date.today(),
        currency="AED",
        payment_terms="NET30",
        created_by=created_by,
    )
    subtotal = Decimal("0")
    total_tax = Decimal("0")
    for il in inv_lines:
        lt, ta = _compute_line_totals(il.qty, il.unit_price, il.discount_pct, Decimal("5"))
        net = il.qty * il.unit_price * (1 - il.discount_pct / 100)
        net = net.quantize(Decimal("0.0001"))
        subtotal += net
        total_tax += ta
        line = InvoiceLine(
            product_sku=il.product_sku,
            so_line_id=il.so_line_id,
            qty=il.qty,
            unit_price=il.unit_price,
            discount_pct=il.discount_pct,
            tax_rate=Decimal("5"),
            line_total=lt,
            tax_amount=ta,
        )
        invoice.lines.append(line)

    invoice.subtotal = subtotal
    invoice.tax_amount = total_tax
    invoice.total_amount = subtotal + total_tax

    session.add(invoice)
    await session.flush()
    await session.refresh(invoice)
    return invoice


# Internal simple dataclass for from_delivery helper
class InvoiceLineCreate_:
    def __init__(
        self,
        product_sku: str,
        so_line_id: UUID | None,
        qty: Decimal,
        unit_price: Decimal,
        discount_pct: Decimal,
    ) -> None:
        self.product_sku = product_sku
        self.so_line_id = so_line_id
        self.qty = qty
        self.unit_price = unit_price
        self.discount_pct = discount_pct


# ---------------------------------------------------------------------------
# US-ERP-05-02 — Post / Cancel / Reverse
# ---------------------------------------------------------------------------

async def post_invoice(session: AsyncSession, invoice: Invoice) -> Invoice:
    """Postea invoice: status → posted, FI entries, customer_open_items."""
    if invoice.status != "draft":
        raise ValueError(f"Cannot post invoice in status '{invoice.status}'")

    invoice.status = "posted"
    await session.flush()

    # Graceful insert into financial_entries if table exists (EP-ERP-06)
    try:
        await session.execute(
            text(
                """
                DO $$
                BEGIN
                  IF EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'financial_entries'
                  ) THEN
                    INSERT INTO financial_entries
                      (id, entry_date, description, debit_account, credit_account, amount, currency, reference_id, reference_type, created_at)
                    VALUES
                      (gen_random_uuid(), CURRENT_DATE, :desc_ar, 'AR', NULL,       :total,    :curr, :inv_id, 'INVOICE', now()),
                      (gen_random_uuid(), CURRENT_DATE, :desc_rev, NULL, 'REVENUE', :subtotal, :curr, :inv_id, 'INVOICE', now()),
                      (gen_random_uuid(), CURRENT_DATE, :desc_tax, NULL, 'TAX_PAYABLE', :tax,  :curr, :inv_id, 'INVOICE', now());
                  END IF;
                END $$;
                """
            ),
            {
                "desc_ar": f"AR {invoice.invoice_number}",
                "desc_rev": f"Revenue {invoice.invoice_number}",
                "desc_tax": f"Tax Payable {invoice.invoice_number}",
                "total": str(invoice.total_amount or 0),
                "subtotal": str(invoice.subtotal or 0),
                "tax": str(invoice.tax_amount or 0),
                "curr": invoice.currency,
                "inv_id": str(invoice.id),
            },
        )
    except Exception:
        logger.warning("financial_entries insert skipped (EP-ERP-06 not deployed yet)")

    # Upsert customer_open_items
    try:
        await session.execute(
            text(
                """
                INSERT INTO customer_open_items
                  (id, customer_id, invoice_id, document_type, amount, due_date, status)
                VALUES
                  (gen_random_uuid(), :customer_id, :invoice_id, 'INVOICE', :amount, :due_date, 'open')
                ON CONFLICT (invoice_id) DO UPDATE
                  SET amount = EXCLUDED.amount,
                      due_date = EXCLUDED.due_date,
                      status = 'open'
                """
            ),
            {
                "customer_id": invoice.customer_id,
                "invoice_id": str(invoice.id),
                "amount": str(invoice.total_amount or 0),
                "due_date": invoice.due_date or date.today(),
            },
        )
    except Exception:
        logger.warning("customer_open_items upsert failed (constraint or table issue)")

    await session.refresh(invoice)
    return invoice


async def cancel_invoice(session: AsyncSession, invoice: Invoice) -> Invoice:
    """Cancela invoice (status → cancelled)."""
    if invoice.status not in ("draft", "posted"):
        raise ValueError(f"Cannot cancel invoice in status '{invoice.status}'")
    invoice.status = "cancelled"

    # Reverse FI entry (graceful)
    if invoice.status == "posted":
        try:
            await session.execute(
                text(
                    """
                    DO $$
                    BEGIN
                      IF EXISTS (
                        SELECT 1 FROM information_schema.tables
                        WHERE table_schema='public' AND table_name='financial_entries'
                      ) THEN
                        INSERT INTO financial_entries
                          (id, entry_date, description, credit_account, debit_account, amount, currency, reference_id, reference_type, created_at)
                        VALUES
                          (gen_random_uuid(), CURRENT_DATE, :desc, 'AR', NULL, :total, :curr, :inv_id, 'INVOICE_CANCEL', now());
                      END IF;
                    END $$;
                    """
                ),
                {
                    "desc": f"Cancel {invoice.invoice_number}",
                    "total": str(invoice.total_amount or 0),
                    "curr": invoice.currency,
                    "inv_id": str(invoice.id),
                },
            )
        except Exception:
            pass

    await session.flush()
    await session.refresh(invoice)
    return invoice


async def reverse_invoice(session: AsyncSession, invoice: Invoice) -> Invoice:
    """Crea Credit Memo por el negativo del monto original."""
    if invoice.status != "posted":
        raise ValueError("Can only reverse posted invoices")

    credit_memo = Invoice(
        invoice_number=_generate_invoice_number("CM"),
        invoice_type="CREDIT_MEMO",
        so_id=invoice.so_id,
        delivery_id=invoice.delivery_id,
        customer_id=invoice.customer_id,
        invoice_date=date.today(),
        due_date=invoice.due_date,
        currency=invoice.currency,
        payment_terms=invoice.payment_terms,
        subtotal=-(invoice.subtotal or Decimal("0")),
        tax_amount=-(invoice.tax_amount or Decimal("0")),
        total_amount=-(invoice.total_amount or Decimal("0")),
        status="draft",
        created_by=invoice.created_by,
    )
    invoice.status = "reversed"
    session.add(credit_memo)
    await session.flush()
    await session.refresh(credit_memo)
    return credit_memo


# ---------------------------------------------------------------------------
# US-ERP-05-03 — Dunning
# ---------------------------------------------------------------------------

async def get_dunning_invoices(
    session: AsyncSession,
    customer_id: str | None = None,
    level: int | None = None,
) -> list[dict[str, Any]]:
    """Invoices en mora con su nivel de dunning calculado."""
    today = date.today()
    q = select(Invoice).where(
        Invoice.status == "posted",
        Invoice.due_date < today,
    )
    if customer_id:
        q = q.where(Invoice.customer_id == customer_id)
    result = await session.execute(q)
    invoices = list(result.scalars().all())

    # Load dunning levels
    dl_result = await session.execute(
        select(DunningLevel).where(DunningLevel.is_active == True).order_by(DunningLevel.level)  # noqa: E712
    )
    levels = list(dl_result.scalars().all())

    output = []
    for inv in invoices:
        if inv.due_date is None:
            continue
        days_overdue = (today - inv.due_date).days
        current_level = 0
        for dl in reversed(levels):
            if days_overdue >= dl.days_overdue:
                current_level = dl.level
                break
        if level is not None and current_level != level:
            continue
        output.append(
            {
                "invoice_id": str(inv.id),
                "invoice_number": inv.invoice_number,
                "customer_id": inv.customer_id,
                "due_date": inv.due_date.isoformat(),
                "days_overdue": days_overdue,
                "dunning_level": current_level,
                "total_amount": str(inv.total_amount),
            }
        )
    return output


async def escalate_dunning(
    session: AsyncSession,
    invoice: Invoice,
    notes: str | None = None,
) -> DunningHistory:
    """Sube manualmente el nivel de dunning de una invoice."""
    today = date.today()
    if invoice.due_date is None or invoice.due_date >= today:
        raise ValueError("Invoice is not overdue")

    days_overdue = (today - invoice.due_date).days
    dl_result = await session.execute(
        select(DunningLevel).where(DunningLevel.is_active == True).order_by(DunningLevel.level.desc())  # noqa: E712
    )
    levels = list(dl_result.scalars().all())
    current_level = 0
    for dl in reversed(levels):
        if days_overdue >= dl.days_overdue:
            current_level = dl.level
            break
    next_level = min(current_level + 1, max(dl.level for dl in levels))

    history = DunningHistory(
        invoice_id=invoice.id,
        customer_id=invoice.customer_id,
        dunning_level=next_level,
        notes=notes,
    )
    session.add(history)
    await session.flush()
    await session.refresh(history)
    return history


# ---------------------------------------------------------------------------
# US-ERP-05-04 — E-Invoice / ZATCA
# ---------------------------------------------------------------------------

async def submit_e_invoice(
    session: AsyncSession,
    invoice: Invoice,
    req: EInvoiceSubmitRequest,
) -> EInvoiceSubmission:
    xml_payload = _build_xml_stub(invoice)
    qr_code: str | None = None

    if req.standard == "ZATCA_PHASE2":
        seller_name = req.seller_name or "MT Middle East"
        vat_number = req.vat_number or "300000000000003"
        qr_code = _zatca_qr(
            seller_name=seller_name,
            vat_number=vat_number,
            invoice_date=str(invoice.invoice_date),
            total=str(invoice.total_amount or 0),
            vat_amount=str(invoice.tax_amount or 0),
        )

    submission = EInvoiceSubmission(
        invoice_id=invoice.id,
        standard=req.standard,
        submission_ref=f"{req.standard}-{uuid4().hex[:8].upper()}",
        submitted_at=datetime.now(timezone.utc),
        status="submitted",
        xml_payload=xml_payload,
        qr_code=qr_code,
        retry_count=0,
    )
    invoice.e_invoice_status = "pending"
    session.add(submission)
    await session.flush()
    await session.refresh(submission)
    return submission


async def retry_e_invoice(
    session: AsyncSession,
    submission_id: UUID,
) -> EInvoiceSubmission:
    r = await session.execute(
        select(EInvoiceSubmission).where(EInvoiceSubmission.id == submission_id)
    )
    sub = r.scalar_one_or_none()
    if not sub:
        raise ValueError(f"Submission {submission_id} not found")
    if sub.status not in ("rejected", "pending"):
        raise ValueError(f"Cannot retry submission in status '{sub.status}'")
    sub.status = "submitted"
    sub.retry_count += 1
    sub.submitted_at = datetime.now(timezone.utc)
    await session.flush()
    await session.refresh(sub)
    return sub


# ---------------------------------------------------------------------------
# US-ERP-05-05 — AR Aging + Payment Promises
# ---------------------------------------------------------------------------

async def get_ar_aging(
    session: AsyncSession,
    as_of_date: date | None = None,
) -> list[ARAgingBucket]:
    ref_date = as_of_date or date.today()

    q = select(Invoice).where(
        Invoice.status == "posted",
        Invoice.total_amount != None,  # noqa: E711
    )
    result = await session.execute(q)
    invoices = list(result.scalars().all())

    buckets: dict[str, ARAgingBucket] = {}
    for inv in invoices:
        cid = inv.customer_id
        if cid not in buckets:
            buckets[cid] = ARAgingBucket(customer_id=cid)
        b = buckets[cid]
        amount = inv.total_amount or Decimal("0")
        if inv.due_date is None or inv.due_date >= ref_date:
            b.current += amount
        else:
            days_late = (ref_date - inv.due_date).days
            if days_late <= 30:
                b.days_1_30 += amount
            elif days_late <= 60:
                b.days_31_60 += amount
            elif days_late <= 90:
                b.days_61_90 += amount
            else:
                b.days_90_plus += amount
        b.total_outstanding += amount

    return list(buckets.values())


async def create_payment_promise(
    session: AsyncSession,
    data: PaymentPromiseCreate,
    created_by: UUID | None = None,
) -> PaymentPromise:
    pp = PaymentPromise(
        invoice_id=data.invoice_id,
        customer_id=data.customer_id,
        promised_date=data.promised_date,
        promised_amount=data.promised_amount,
        notes=data.notes,
        status="active",
        created_by=created_by,
    )
    session.add(pp)
    await session.flush()
    await session.refresh(pp)
    return pp


async def patch_payment_promise(
    session: AsyncSession,
    promise_id: UUID,
    data: PaymentPromisePatch,
) -> PaymentPromise:
    r = await session.execute(
        select(PaymentPromise).where(PaymentPromise.id == promise_id)
    )
    pp = r.scalar_one_or_none()
    if not pp:
        raise ValueError(f"PaymentPromise {promise_id} not found")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(pp, field, value)
    await session.flush()
    await session.refresh(pp)
    return pp


# ---------------------------------------------------------------------------
# US-ERP-05-06 — KPIs
# ---------------------------------------------------------------------------

async def get_billing_kpis(session: AsyncSession) -> BillingKPIs:
    today = date.today()
    kpis = BillingKPIs()

    # Overdue invoices
    r_overdue = await session.execute(
        select(
            func.count(Invoice.id).label("cnt"),
            func.coalesce(func.sum(Invoice.total_amount), 0).label("total"),
        ).where(
            Invoice.status == "posted",
            Invoice.due_date < today,
        )
    )
    row_overdue = r_overdue.one()
    kpis.overdue_invoice_count = row_overdue.cnt or 0
    kpis.overdue_amount = Decimal(str(row_overdue.total or 0))

    # AR total (all posted)
    r_ar = await session.execute(
        select(func.coalesce(func.sum(Invoice.total_amount), 0)).where(Invoice.status == "posted")
    )
    ar_total = Decimal(str(r_ar.scalar() or 0))

    # Revenue last 30 days
    try:
        r_rev = await session.execute(
            text(
                """
                SELECT COALESCE(SUM(total_amount), 0) as rev
                FROM invoices
                WHERE status = 'posted'
                AND created_at >= NOW() - INTERVAL '30 days'
                """
            )
        )
        rev_30d = Decimal(str(r_rev.scalar() or 0))
    except Exception:
        rev_30d = Decimal("0")

    # DSO
    if rev_30d > 0:
        kpis.dso = (ar_total / rev_30d * 30).quantize(Decimal("0.01"))

    # CEI — collected in 30d (sum of open_items closed in period — approximate via cancelled/reversed)
    try:
        r_coll = await session.execute(
            text(
                """
                SELECT COALESCE(SUM(total_amount), 0) as collected
                FROM invoices
                WHERE status IN ('cancelled','reversed')
                AND updated_at >= NOW() - INTERVAL '30 days'
                """
            )
        )
        collected_30d = Decimal(str(r_coll.scalar() or 0))
        opening_ar = ar_total  # approximation
        denom = opening_ar + rev_30d
        if denom > 0:
            kpis.cei = (collected_30d / denom * 100).quantize(Decimal("0.01"))
    except Exception:
        pass

    # Time to invoice avg hours
    try:
        r_tti = await session.execute(
            text(
                """
                SELECT AVG(
                  EXTRACT(EPOCH FROM (i.created_at - d.shipped_at)) / 3600
                ) as avg_hours
                FROM invoices i
                JOIN outbound_deliveries d ON d.id = i.delivery_id
                WHERE d.shipped_at IS NOT NULL
                AND i.created_at IS NOT NULL
                """
            )
        )
        avg_hours = r_tti.scalar()
        if avg_hours is not None:
            kpis.time_to_invoice_avg_hours = Decimal(str(avg_hours)).quantize(Decimal("0.01"))
    except Exception:
        pass

    # E-invoice compliance
    try:
        r_compliance = await session.execute(
            text(
                """
                SELECT
                  COUNT(*) FILTER (WHERE e_invoice_status = 'compliant') AS accepted,
                  COUNT(*) AS total
                FROM invoices
                WHERE status = 'posted'
                """
            )
        )
        comp_row = r_compliance.one()
        if comp_row.total and comp_row.total > 0:
            kpis.e_invoice_compliance_pct = (
                Decimal(str(comp_row.accepted)) / Decimal(str(comp_row.total)) * 100
            ).quantize(Decimal("0.01"))
    except Exception:
        pass

    return kpis

"""Integration: invoice ingestion creates PO + goods receipts."""

from __future__ import annotations

import os
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = [pytest.mark.integration]


@pytest.fixture(autouse=True, scope="module")
def _migrate(postgres_container: str) -> None:
    from alembic.config import Config
    from alembic import command

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", os.environ["ALEMBIC_DATABASE_URL"])
    command.upgrade(cfg, "head")


async def _seed_product(db_session: AsyncSession, sku: str) -> None:
    """Insert product if it doesn't exist; reset hs_code to None either way."""
    from app.db.models.product import Product
    from app.db.models.vocabularies import Brand, Family

    existing = (
        await db_session.execute(select(Product).where(Product.sku == sku))
    ).scalar_one_or_none()
    if existing is None:
        suffix = uuid.uuid4().hex[:8]
        fam = Family(code=f"fam-{suffix}", name="F")
        brand = Brand(code=f"brand-{suffix}", name="B")
        db_session.add_all([fam, brand])
        await db_session.flush()
        db_session.add(
            Product(
                sku=sku,
                family="F",
                family_id=fam.id,
                brand_id=brand.id,
                pe_eur=Decimal("10"),
                catalog_pvp_eur=Decimal("40"),
                units_per_box=1,
                weight=Decimal("0.2"),
                ceiling_basis="catalog_pvp",
            )
        )
        await db_session.flush()
    else:
        # Reset hs_code so the ingest assertion is meaningful.
        existing.hs_code = None
        await db_session.flush()


async def test_ingest_creates_po_and_goods_receipt(db_session: AsyncSession):
    from app.db.models.inventory import GoodsReceipt, PurchaseOrder, PurchaseOrderLine
    from app.db.models.product import Product
    from app.schemas.invoice_imports import InvoiceLine, InvoiceParseResult
    from app.services.procurement.invoice_ingest_service import InvoiceIngestService

    await _seed_product(db_session, "310912015")
    commercial = InvoiceParseResult(
        invoice_number="INV-TEST-1",
        incoterms="DAP",
        order_refs=["POTEST1"],
        lines=[
            InvoiceLine(
                code="310912015",
                description="VALVE",
                quantity=Decimal("10"),
                unit_price=Decimal("34.804"),
                intrastat_code="84818081",
            )
        ],
    )
    import_inv = InvoiceParseResult(
        invoice_number="INV-TEST-1-IMP",
        incoterms="DAP",
        order_refs=["POTEST1"],
        lines=[
            InvoiceLine(
                code="310912015",
                description="VALVE",
                quantity=Decimal("10"),
                unit_price=Decimal("30.0"),
            )
        ],
    )
    svc = InvoiceIngestService(db_session)
    result = await svc.ingest(
        commercial=commercial, import_inv=import_inv, tariff_pct=Decimal("5"), confirm=True
    )

    assert result.created == 1
    po = (
        await db_session.execute(select(PurchaseOrder).where(PurchaseOrder.po_number == "POTEST1"))
    ).scalar_one()
    assert po.status in ("confirmed", "partial", "received")
    pol = (
        await db_session.execute(select(PurchaseOrderLine).where(PurchaseOrderLine.po_id == po.id))
    ).scalar_one()
    gr = (
        await db_session.execute(select(GoodsReceipt).where(GoodsReceipt.po_line_id == pol.id))
    ).scalar_one()
    assert gr.actual_breakdown["commercial_eur"] == "34.804"
    assert gr.actual_breakdown["import_duty_eur"] == "1.5000"
    assert "hs_code" not in gr.actual_breakdown
    prod = (
        await db_session.execute(select(Product).where(Product.sku == "310912015"))
    ).scalar_one()
    assert prod.hs_code == "84818081"


async def test_ingest_preview_does_not_persist(db_session: AsyncSession):
    from app.db.models.inventory import PurchaseOrder
    from app.schemas.invoice_imports import InvoiceLine, InvoiceParseResult
    from app.services.procurement.invoice_ingest_service import InvoiceIngestService

    await _seed_product(db_session, "310912020")
    commercial = InvoiceParseResult(
        invoice_number="INV-PREV",
        incoterms="DAP",
        order_refs=["POPREV"],
        lines=[
            InvoiceLine(
                code="310912020",
                description="V",
                quantity=Decimal("5"),
                unit_price=Decimal("47.194"),
                intrastat_code="84818081",
            )
        ],
    )
    import_inv = InvoiceParseResult(
        invoice_number="INV-PREV-IMP",
        incoterms="DAP",
        order_refs=["POPREV"],
        lines=[
            InvoiceLine(
                code="310912020", description="V", quantity=Decimal("5"), unit_price=Decimal("40")
            )
        ],
    )
    svc = InvoiceIngestService(db_session)
    result = await svc.ingest(
        commercial=commercial, import_inv=import_inv, tariff_pct=Decimal("5"), confirm=False
    )
    assert result.items[0].duty_eur == Decimal("2.0000")
    po = (
        await db_session.execute(select(PurchaseOrder).where(PurchaseOrder.po_number == "POPREV"))
    ).scalar_one_or_none()
    assert po is None


async def test_ingest_is_idempotent_per_invoice(db_session: AsyncSession):
    from app.schemas.invoice_imports import InvoiceLine, InvoiceParseResult
    from app.services.procurement.invoice_ingest_service import InvoiceIngestService

    await _seed_product(db_session, "310912025")
    commercial = InvoiceParseResult(
        invoice_number="INV-IDEM", incoterms="DAP", order_refs=["POIDEM"],
        lines=[InvoiceLine(code="310912025", description="V", quantity=Decimal("3"),
                           unit_price=Decimal("68.208"), intrastat_code="84818081")],
    )
    import_inv = InvoiceParseResult(
        invoice_number="INV-IDEM-IMP", incoterms="DAP", order_refs=["POIDEM"],
        lines=[InvoiceLine(code="310912025", description="V", quantity=Decimal("3"),
                           unit_price=Decimal("60"))],
    )
    svc = InvoiceIngestService(db_session)
    r1 = await svc.ingest(commercial=commercial, import_inv=import_inv,
                          tariff_pct=Decimal("5"), confirm=True)
    r2 = await svc.ingest(commercial=commercial, import_inv=import_inv,
                          tariff_pct=Decimal("5"), confirm=True)
    assert r1.created == 1
    assert r2.created == 0 and r2.skipped == 1


# ---------------------------------------------------------------------------
# FIX 1 — partial re-ingest merges VendorInvoice marker, no IntegrityError
# ---------------------------------------------------------------------------

async def test_partial_reingest_merges_marker_no_crash(db_session: AsyncSession):
    """Re-ingesting the same invoice_number with a new code must NOT create a
    second VendorInvoice row (UNIQUE constraint). Instead it merges codes and
    increments total_amount on the existing row."""
    from app.db.models.procurement import VendorInvoice
    from app.schemas.invoice_imports import InvoiceLine, InvoiceParseResult
    from app.services.procurement.invoice_ingest_service import InvoiceIngestService

    await _seed_product(db_session, "310912030")
    await _seed_product(db_session, "310912031")

    svc = InvoiceIngestService(db_session)

    # First ingest: only code A (single-ref invoice, PO POPART1)
    r1 = await svc.ingest(
        commercial=InvoiceParseResult(
            invoice_number="INV-PARTIAL",
            incoterms="DAP",
            order_refs=["POPART1"],
            lines=[
                InvoiceLine(
                    code="310912030", description="A",
                    quantity=Decimal("2"), unit_price=Decimal("10"),
                    order_no="POPART1",
                )
            ],
        ),
        import_inv=InvoiceParseResult(
            invoice_number="INV-PARTIAL-IMP",
            incoterms="DAP",
            order_refs=["POPART1"],
            lines=[],
        ),
        tariff_pct=Decimal("5"),
        confirm=True,
    )
    assert r1.created == 1

    # Second ingest: same invoice_number; code A is already ingested (skip),
    # code B is new and belongs to a DIFFERENT PO (POPART2) — realistic partial
    # re-ingest where the invoice spans two purchase orders.
    r2 = await svc.ingest(
        commercial=InvoiceParseResult(
            invoice_number="INV-PARTIAL",
            incoterms="DAP",
            order_refs=["POPART1", "POPART2"],
            lines=[
                InvoiceLine(
                    code="310912030", description="A",
                    quantity=Decimal("2"), unit_price=Decimal("10"),
                    order_no="POPART1",
                ),
                InvoiceLine(
                    code="310912031", description="B",
                    quantity=Decimal("3"), unit_price=Decimal("20"),
                    order_no="POPART2",
                ),
            ],
        ),
        import_inv=InvoiceParseResult(
            invoice_number="INV-PARTIAL-IMP",
            incoterms="DAP",
            order_refs=["POPART1", "POPART2"],
            lines=[],
        ),
        tariff_pct=Decimal("5"),
        confirm=True,
    )
    assert r2.created == 1   # only B is new
    assert r2.skipped == 1   # A is skipped (already ingested)

    # Exactly ONE VendorInvoice row for INV-PARTIAL, codes contain both A and B
    rows = (
        await db_session.execute(
            select(VendorInvoice).where(VendorInvoice.invoice_number == "INV-PARTIAL")
        )
    ).scalars().all()
    assert len(rows) == 1, "must not create duplicate VendorInvoice rows"
    codes = rows[0].match_details["codes"]
    assert "310912030" in codes
    assert "310912031" in codes


# ---------------------------------------------------------------------------
# FIX 2 — multi-PO invoice routes each line to its own PO
# ---------------------------------------------------------------------------

async def test_multi_po_invoice_routes_lines_to_own_po(db_session: AsyncSession):
    """Each line carries its own order_no; the service must create two distinct
    POs and route the GR to the correct one."""
    from app.db.models.inventory import GoodsReceipt, PurchaseOrder, PurchaseOrderLine
    from app.schemas.invoice_imports import InvoiceLine, InvoiceParseResult
    from app.services.procurement.invoice_ingest_service import InvoiceIngestService

    await _seed_product(db_session, "310912040")
    await _seed_product(db_session, "310912041")

    svc = InvoiceIngestService(db_session)
    result = await svc.ingest(
        commercial=InvoiceParseResult(
            invoice_number="INV-MULTI-PO",
            incoterms="DAP",
            order_refs=["POA-MULTI", "POB-MULTI"],
            lines=[
                InvoiceLine(
                    code="310912040", description="X",
                    quantity=Decimal("5"), unit_price=Decimal("15"),
                    order_no="POA-MULTI",
                ),
                InvoiceLine(
                    code="310912041", description="Y",
                    quantity=Decimal("7"), unit_price=Decimal("25"),
                    order_no="POB-MULTI",
                ),
            ],
        ),
        import_inv=InvoiceParseResult(
            invoice_number="INV-MULTI-PO-IMP",
            incoterms="DAP",
            order_refs=["POA-MULTI", "POB-MULTI"],
            lines=[],
        ),
        tariff_pct=Decimal("5"),
        confirm=True,
    )
    assert result.created == 2
    assert result.errors == 0

    po_a = (
        await db_session.execute(
            select(PurchaseOrder).where(PurchaseOrder.po_number == "POA-MULTI")
        )
    ).scalar_one()
    po_b = (
        await db_session.execute(
            select(PurchaseOrder).where(PurchaseOrder.po_number == "POB-MULTI")
        )
    ).scalar_one()
    assert po_a.id != po_b.id

    # Each PO has the correct line
    pol_a = (
        await db_session.execute(
            select(PurchaseOrderLine).where(
                PurchaseOrderLine.po_id == po_a.id,
                PurchaseOrderLine.sku == "310912040",
            )
        )
    ).scalar_one()
    pol_b = (
        await db_session.execute(
            select(PurchaseOrderLine).where(
                PurchaseOrderLine.po_id == po_b.id,
                PurchaseOrderLine.sku == "310912041",
            )
        )
    ).scalar_one()

    gr_a = (
        await db_session.execute(
            select(GoodsReceipt).where(GoodsReceipt.po_line_id == pol_a.id)
        )
    ).scalar_one()
    gr_b = (
        await db_session.execute(
            select(GoodsReceipt).where(GoodsReceipt.po_line_id == pol_b.id)
        )
    ).scalar_one()
    assert gr_a.actual_breakdown["commercial_eur"] == "15"
    assert gr_b.actual_breakdown["commercial_eur"] == "25"


# ---------------------------------------------------------------------------
# FIX 2 — line with no order_no when invoice has multiple refs → error
# ---------------------------------------------------------------------------

async def test_multi_po_line_without_order_no_is_error(db_session: AsyncSession):
    """A line with order_no=None on a multi-ref invoice must produce an error
    item rather than silently collapsing to refs[0]."""
    from app.schemas.invoice_imports import InvoiceLine, InvoiceParseResult
    from app.services.procurement.invoice_ingest_service import InvoiceIngestService

    await _seed_product(db_session, "310912050")

    svc = InvoiceIngestService(db_session)
    result = await svc.ingest(
        commercial=InvoiceParseResult(
            invoice_number="INV-NO-ORDER",
            incoterms="DAP",
            order_refs=["PO-X1", "PO-X2"],
            lines=[
                InvoiceLine(
                    code="310912050", description="Z",
                    quantity=Decimal("1"), unit_price=Decimal("10"),
                    order_no=None,  # explicitly ambiguous
                ),
            ],
        ),
        import_inv=InvoiceParseResult(
            invoice_number="INV-NO-ORDER-IMP",
            incoterms="DAP",
            order_refs=[],
            lines=[],
        ),
        tariff_pct=Decimal("5"),
        confirm=True,
    )
    assert result.errors == 1
    assert result.created == 0
    assert result.items[0].status == "error"
    assert "cannot determine Order No." in (result.items[0].detail or "")


# ---------------------------------------------------------------------------
# FIX 3 — missing import line surfaces in item detail
# ---------------------------------------------------------------------------

async def test_missing_import_line_detail(db_session: AsyncSession):
    """When a commercial line has no matching import line the item must still
    be status='ok' but detail must contain the advisory message."""
    from app.schemas.invoice_imports import InvoiceLine, InvoiceParseResult
    from app.services.procurement.invoice_ingest_service import InvoiceIngestService

    await _seed_product(db_session, "310912060")

    svc = InvoiceIngestService(db_session)
    result = await svc.ingest(
        commercial=InvoiceParseResult(
            invoice_number="INV-NO-IMP",
            incoterms="DAP",
            order_refs=["PO-NOIMP"],
            lines=[
                InvoiceLine(
                    code="310912060", description="W",
                    quantity=Decimal("1"), unit_price=Decimal("50"),
                    order_no="PO-NOIMP",
                )
            ],
        ),
        import_inv=InvoiceParseResult(
            invoice_number="INV-NO-IMP-IMP",
            incoterms="DAP",
            order_refs=[],
            lines=[],  # no matching import line
        ),
        tariff_pct=Decimal("5"),
        confirm=False,
    )
    assert result.items[0].status == "ok"
    assert result.items[0].duty_eur == Decimal("0")
    assert "no matching import line" in (result.items[0].detail or "")

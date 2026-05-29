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

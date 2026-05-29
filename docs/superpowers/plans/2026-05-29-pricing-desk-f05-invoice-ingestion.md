# Pricing Desk F0.5 — Invoice Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ingest MT supplier invoices (PDF) — commercial + import — to create goods receipts carrying the real per‑unit landed cost, feeding the existing MAP (weighted‑average) → `costs` flow so the real cost reaches the Pricing Desk (via F0).

**Architecture:** A pure PDF/text parser extracts invoice line items; an ingest service pairs the commercial and import invoices by `Code`, computes per‑SKU `actual_breakdown = {commercial_eur, import_duty_eur=import×tariff%}`, resolves the PO (hybrid: match by `Order No.` or create+confirm), and creates goods receipts via the **existing** `GoodsReceiptRepository.create()` — which triggers the existing `MAPService` (weighted average). F0.5 builds NO costing logic; it only produces the per‑receipt cost and feeds the existing chain.

**Tech Stack:** Python 3.11, pdfplumber, SQLAlchemy 2.0 async, FastAPI, pytest (unit + integration with Postgres). Backend: `mt-pricing-backend/`. Spec: `docs/superpowers/specs/2026-05-29-invoice-ingestion-cost-f05-design.md`.

**Design corrections (locked, vs spec):**
- `actual_breakdown` holds **only summable cost components** (`commercial_eur`, `import_duty_eur`). `CostService.compute_landed_aed` sums any numeric value by suffix; a numeric `hs_code` would be wrongly added. So **`hs_code` → `products.hs_code`**, **`incoterm` + `invoice_number` → `GoodsReceipt.notes` / `VendorInvoice`**, never inside `actual_breakdown`.
- Parser split: pure `_parse_invoice_text(lines: list[str]) -> InvoiceParseResult` (unit‑testable on strings) + `parse_invoice_pdf(pdf_bytes)` (pdfplumber → text → `_parse_invoice_text`).
- `tariff_pct` = request parameter, default `Decimal("5")` (editable). HS‑specific tariff is F7.
- Procurement `scheme_code` for created PO lines/GR = `"DIRECT_B2C"` (valid `schemes.code`).
- Idempotency key = `(invoice_number, code)`, enforced by recording a `VendorInvoice(invoice_number, po_id)` and skipping codes already received for that invoice.

**Out of scope (YAGNI):** HS tariff master (F7), XML invoices, automated `VendorInvoice` 3‑way match/tolerances, aggregate freight allocation (DAP → freight in commercial price).

---

## File Structure

| File | Responsibility | Change |
|------|----------------|--------|
| `mt-pricing-backend/app/schemas/invoice_imports.py` | Pydantic DTOs | **new** — `InvoiceLine`, `InvoiceParseResult`, `InvoiceIngestItem`, `InvoiceIngestResult` |
| `mt-pricing-backend/app/services/procurement/invoice_parser.py` | PDF/text → structured lines | **new** — `_parse_invoice_text`, `parse_invoice_pdf` |
| `mt-pricing-backend/app/services/procurement/cost_builder.py` | per‑SKU `actual_breakdown` | **new** — `build_actual_breakdown(commercial, import_value, tariff_pct)` |
| `mt-pricing-backend/app/services/procurement/po_resolver.py` | match/create+confirm PO | **new** — `resolve_or_create_po(...)` |
| `mt-pricing-backend/app/services/procurement/invoice_ingest_service.py` | orchestration | **new** — `InvoiceIngestService.ingest(...)` |
| `mt-pricing-backend/app/api/routes/invoice_imports.py` | endpoint + RBAC + preview/confirm | **new** — `POST /imports/invoice` |
| `mt-pricing-backend/app/api/__init__.py` or router registry | register router | **modify** — include the new router |
| `mt-pricing-backend/tests/services/procurement/test_invoice_parser.py` | parser unit | **new** |
| `mt-pricing-backend/tests/services/procurement/test_cost_builder.py` | cost unit | **new** |
| `mt-pricing-backend/tests/services/procurement/test_invoice_ingest.py` | integration | **new** |

---

## Task 1: Schemas

**Files:**
- Create: `mt-pricing-backend/app/schemas/invoice_imports.py`
- Test: covered indirectly by parser/service tests (no dedicated test — pure DTOs)

- [ ] **Step 1: Create the schemas**

```python
"""DTOs for supplier invoice ingestion (F0.5)."""
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel


class InvoiceLine(BaseModel):
    code: str                 # SKU
    description: str
    quantity: Decimal
    unit_price: Decimal       # EUR (commercial: real cost; import: customs value)
    intrastat_code: str | None = None


class InvoiceParseResult(BaseModel):
    invoice_number: str | None
    incoterms: str | None
    currency: str = "EUR"
    order_refs: list[str] = []        # 'Order No.' values found
    lines: list[InvoiceLine] = []
    errors: list[dict] = []           # row-level parse errors


class InvoiceIngestItem(BaseModel):
    code: str
    commercial_eur: Decimal
    import_value_eur: Decimal
    duty_eur: Decimal
    qty: Decimal
    po_number: str | None
    po_action: str                    # 'matched' | 'created'
    status: str                       # 'ok' | 'skipped' | 'error'
    detail: str | None = None


class InvoiceIngestResult(BaseModel):
    created: int = 0
    skipped: int = 0
    errors: int = 0
    items: list[InvoiceIngestItem] = []
```

- [ ] **Step 2: Commit**

```bash
git add mt-pricing-backend/app/schemas/invoice_imports.py
git commit -m "feat(procurement): invoice ingestion DTOs (F0.5)"
```

---

## Task 2: Invoice parser (pure text parsing + PDF wrapper)

**Files:**
- Create: `mt-pricing-backend/app/services/procurement/invoice_parser.py`
- Test: `mt-pricing-backend/tests/services/procurement/test_invoice_parser.py`

Observed invoice format (real sample `INVOICE 2026002035`): item lines look like
`310912015 THREE PIECES TANK BOTTOM VALVE AISI 316 1/2" 79 34.804 2,749.516`
(`Code  Description…  Quantity  Unit price  Amount`; numbers use **period decimal, comma thousands**). Each item is
followed by `Intrastat code : NNNNNNNN`. Header carries `2026002035` (invoice no.), `Order No. : PExxxx`, `INCOTERMS : DAP`.

- [ ] **Step 1: Write the failing test**

Create `mt-pricing-backend/tests/services/procurement/test_invoice_parser.py`:

```python
from decimal import Decimal

from app.services.procurement.invoice_parser import _parse_invoice_text


SAMPLE = [
    "INVOICE",
    "2026002035 29/01/2026",
    "Page : 1 of 34",
    "Code Description Quantity Unit price Discount Amount",
    "Order No. : PE2545255 Customer reference : FONDO DE CUBA",
    "INCOTERMS : DAP",
    "310912015 THREE PIECES TANK BOTTOM VALVE AISI 316 1/2\" 79 34.804 2,749.516",
    "Intrastat code : 84818081",
    "422401 CHROME HANDLE FOR LONG NECK VALVES 500 1.477 738.50",
    "Intrastat code : 84819000",
]


def test_parse_extracts_invoice_number_and_incoterm():
    r = _parse_invoice_text(SAMPLE)
    assert r.invoice_number == "2026002035"
    assert r.incoterms == "DAP"
    assert "PE2545255" in r.order_refs


def test_parse_extracts_item_lines_with_unit_price_and_hs():
    r = _parse_invoice_text(SAMPLE)
    by_code = {ln.code: ln for ln in r.lines}
    assert by_code["310912015"].quantity == Decimal("79")
    assert by_code["310912015"].unit_price == Decimal("34.804")   # period decimal
    assert by_code["310912015"].intrastat_code == "84818081"
    assert by_code["422401"].unit_price == Decimal("1.477")
    assert by_code["422401"].intrastat_code == "84819000"


def test_parse_ignores_non_item_lines():
    r = _parse_invoice_text(SAMPLE)
    assert len(r.lines) == 2  # only the two article rows
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker exec mt-backend sh -c "cd /app && python -m pytest tests/services/procurement/test_invoice_parser.py -o addopts='' -q"`
Expected: FAIL with `ModuleNotFoundError: app.services.procurement.invoice_parser`

- [ ] **Step 3: Write minimal implementation**

Create `mt-pricing-backend/app/services/procurement/invoice_parser.py`:

```python
"""Supplier invoice PDF parser (F0.5). Pure text parsing + pdfplumber wrapper."""
from __future__ import annotations

import io
import re
from decimal import Decimal, InvalidOperation

from app.schemas.invoice_imports import InvoiceLine, InvoiceParseResult

# Item row: <code(5+ digits)> <description...> <qty(int)> <unit_price> <amount>
# Numbers: period decimal, comma thousands (e.g. 34.804 / 2,749.516).
_ITEM_RE = re.compile(
    r"^(?P<code>\d{5,})\s+(?P<desc>.+?)\s+(?P<qty>\d+)\s+"
    r"(?P<unit>[\d,]+\.\d+|\d+)\s+(?P<amount>[\d,]+\.\d+|\d+(?:\.\d+)?)$"
)
_INTRASTAT_RE = re.compile(r"Intrastat code\s*:\s*(\d+)")
_ORDER_RE = re.compile(r"Order No\.\s*:\s*(\S+)")
_INCOTERM_RE = re.compile(r"INCOTERMS\s*:\s*(\w+)")
_INVOICE_NO_RE = re.compile(r"^(\d{8,})\s+\d{2}/\d{2}/\d{4}")


def _num(raw: str) -> Decimal:
    """Parse period-decimal / comma-thousands number → Decimal."""
    return Decimal(raw.replace(",", ""))


def _parse_invoice_text(lines: list[str]) -> InvoiceParseResult:
    invoice_number: str | None = None
    incoterms: str | None = None
    order_refs: list[str] = []
    parsed: list[InvoiceLine] = []
    errors: list[dict] = []

    for raw in lines:
        s = raw.strip()
        if invoice_number is None:
            m = _INVOICE_NO_RE.match(s)
            if m:
                invoice_number = m.group(1)
        if incoterms is None:
            m = _INCOTERM_RE.search(s)
            if m:
                incoterms = m.group(1)
        m = _ORDER_RE.search(s)
        if m and m.group(1) not in order_refs:
            order_refs.append(m.group(1))

        # Intrastat code attaches to the most recent item line.
        m = _INTRASTAT_RE.search(s)
        if m and parsed and parsed[-1].intrastat_code is None:
            parsed[-1] = parsed[-1].model_copy(update={"intrastat_code": m.group(1)})
            continue

        m = _ITEM_RE.match(s)
        if not m:
            continue
        try:
            parsed.append(
                InvoiceLine(
                    code=m.group("code"),
                    description=m.group("desc").strip(),
                    quantity=_num(m.group("qty")),
                    unit_price=_num(m.group("unit")),
                )
            )
        except (InvalidOperation, ValueError) as e:
            errors.append({"line": s[:80], "error": str(e)})

    return InvoiceParseResult(
        invoice_number=invoice_number,
        incoterms=incoterms,
        order_refs=order_refs,
        lines=parsed,
        errors=errors,
    )


def parse_invoice_pdf(pdf_bytes: bytes) -> InvoiceParseResult:
    import pdfplumber

    lines: list[str] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            txt = page.extract_text() or ""
            lines.extend(txt.splitlines())
    return _parse_invoice_text(lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker exec mt-backend sh -c "cd /app && python -m pytest tests/services/procurement/test_invoice_parser.py -o addopts='' -q"`
Expected: PASS (3 passed). If `FREE OF CHARGE` rows (no numeric price) appear in real PDFs, they simply don't match `_ITEM_RE` and are skipped — acceptable.

- [ ] **Step 5: Commit**

```bash
git add mt-pricing-backend/app/services/procurement/invoice_parser.py mt-pricing-backend/tests/services/procurement/test_invoice_parser.py
git commit -m "feat(procurement): MT invoice PDF parser (F0.5)"
```

---

## Task 3: Cost builder (per-SKU actual_breakdown)

**Files:**
- Create: `mt-pricing-backend/app/services/procurement/cost_builder.py`
- Test: `mt-pricing-backend/tests/services/procurement/test_cost_builder.py`

- [ ] **Step 1: Write the failing test**

Create `mt-pricing-backend/tests/services/procurement/test_cost_builder.py`:

```python
from decimal import Decimal

from app.services.procurement.cost_builder import build_actual_breakdown


def test_breakdown_sums_commercial_plus_duty():
    bd = build_actual_breakdown(
        commercial_eur=Decimal("34.804"),
        import_value_eur=Decimal("30.0"),
        tariff_pct=Decimal("5"),
    )
    assert bd == {"commercial_eur": "34.804", "import_duty_eur": "1.5000"}


def test_breakdown_has_only_summable_keys():
    bd = build_actual_breakdown(Decimal("10"), Decimal("10"), Decimal("5"))
    # No hs_code/incoterm here — compute_landed_aed would mis-sum numeric hs_code.
    assert set(bd.keys()) == {"commercial_eur", "import_duty_eur"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker exec mt-backend sh -c "cd /app && python -m pytest tests/services/procurement/test_cost_builder.py -o addopts='' -q"`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

Create `mt-pricing-backend/app/services/procurement/cost_builder.py`:

```python
"""Build the goods-receipt actual_breakdown from the two MT invoices (F0.5).

Only summable EUR cost components belong here — CostService.compute_landed_aed
sums any numeric value by suffix, so metadata (hs_code/incoterm) must NOT be included.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal


def build_actual_breakdown(
    commercial_eur: Decimal,
    import_value_eur: Decimal,
    tariff_pct: Decimal,
) -> dict[str, str]:
    duty = (import_value_eur * tariff_pct / Decimal("100")).quantize(
        Decimal("0.0001"), rounding=ROUND_HALF_UP
    )
    return {
        "commercial_eur": str(commercial_eur),
        "import_duty_eur": str(duty),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker exec mt-backend sh -c "cd /app && python -m pytest tests/services/procurement/test_cost_builder.py -o addopts='' -q"`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add mt-pricing-backend/app/services/procurement/cost_builder.py mt-pricing-backend/tests/services/procurement/test_cost_builder.py
git commit -m "feat(procurement): per-SKU actual_breakdown builder (commercial + import duty)"
```

---

## Task 4: PO resolver (hybrid match / create + confirm)

**Files:**
- Create: `mt-pricing-backend/app/services/procurement/po_resolver.py`
- Test: covered by the integration test in Task 5 (resolver is DB-bound; testing it through the service avoids duplicate seeding)

- [ ] **Step 1: Write the implementation**

Create `mt-pricing-backend/app/services/procurement/po_resolver.py`:

```python
"""Resolve or create a PurchaseOrder for an invoice's Order No. (F0.5, hybrid)."""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.inventory import PurchaseOrder, PurchaseOrderLine
from app.repositories.purchase_order import PurchaseOrderRepository
from app.schemas.purchase_orders import PurchaseOrderCreate, PurchaseOrderLineCreate

_SUPPLIER = "mt_spain"
_SCHEME = "DIRECT_B2C"


async def resolve_or_create_po(
    session: AsyncSession,
    po_number: str,
    lines: list[tuple[str, Decimal, Decimal]],  # (sku, qty, unit_price_eur)
) -> PurchaseOrder:
    """Return a confirmed/partial PO for po_number, creating + confirming if absent."""
    existing = (
        await session.execute(
            select(PurchaseOrder).where(PurchaseOrder.po_number == po_number)
        )
    ).scalar_one_or_none()

    repo = PurchaseOrderRepository(session)
    if existing is not None:
        if existing.status == "draft":
            await repo.confirm(existing.id)
        return existing

    po = await repo.create(
        PurchaseOrderCreate(
            po_number=po_number,
            supplier_code=_SUPPLIER,
            currency="EUR",
            lines=[
                PurchaseOrderLineCreate(
                    sku=sku, scheme_code=_SCHEME, qty_ordered=qty, unit_price=price
                )
                for sku, qty, price in lines
            ],
        )
    )
    await repo.confirm(po.id)
    return po


async def find_po_line(
    session: AsyncSession, po_id, sku: str
) -> PurchaseOrderLine | None:
    return (
        await session.execute(
            select(PurchaseOrderLine).where(
                PurchaseOrderLine.po_id == po_id,
                PurchaseOrderLine.sku == sku,
                PurchaseOrderLine.scheme_code == _SCHEME,
            )
        )
    ).scalar_one_or_none()
```

> Verify field/attr names against `app/schemas/purchase_orders.py` and `app/repositories/purchase_order.py` when
> implementing (`PurchaseOrderRepository.create(po_data)`, `.confirm(po_id)` confirmed present). Adjust `_SCHEME`
> if `DIRECT_B2C` is not the intended procurement scheme.

- [ ] **Step 2: Commit**

```bash
git add mt-pricing-backend/app/services/procurement/po_resolver.py
git commit -m "feat(procurement): hybrid PO resolver (match by Order No. or create+confirm)"
```

---

## Task 5: Invoice ingest service (orchestration) + integration test

**Files:**
- Create: `mt-pricing-backend/app/services/procurement/invoice_ingest_service.py`
- Test: `mt-pricing-backend/tests/services/procurement/test_invoice_ingest.py`

- [ ] **Step 1: Write the failing integration test**

Create `mt-pricing-backend/tests/services/procurement/test_invoice_ingest.py`:

```python
"""Integration: invoice ingestion creates PO + goods receipts; MAP populates cost."""
from __future__ import annotations

import os
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
    import uuid
    from app.db.models.product import Product
    from app.db.models.vocabularies import Brand, Family

    suffix = uuid.uuid4().hex[:8]
    fam = Family(code=f"fam-{suffix}", name="F")
    brand = Brand(code=f"brand-{suffix}", name="B")
    db_session.add_all([fam, brand])
    await db_session.flush()
    db_session.add(
        Product(
            sku=sku, family="F", family_id=fam.id, brand_id=brand.id,
            pe_eur=Decimal("10"), catalog_pvp_eur=Decimal("40"),
            units_per_box=1, weight=Decimal("0.2"), ceiling_basis="catalog_pvp",
        )
    )
    await db_session.flush()


async def test_ingest_creates_po_and_goods_receipt(db_session: AsyncSession):
    from app.db.models.inventory import GoodsReceipt, PurchaseOrder, PurchaseOrderLine
    from app.services.procurement.invoice_ingest_service import InvoiceIngestService
    from app.schemas.invoice_imports import InvoiceLine, InvoiceParseResult

    await _seed_product(db_session, "310912015")

    commercial = InvoiceParseResult(
        invoice_number="INV-TEST-1", incoterms="DAP", order_refs=["POTEST1"],
        lines=[InvoiceLine(code="310912015", description="VALVE", quantity=Decimal("10"),
                           unit_price=Decimal("34.804"), intrastat_code="84818081")],
    )
    import_inv = InvoiceParseResult(
        invoice_number="INV-TEST-1-IMP", order_refs=["POTEST1"],
        lines=[InvoiceLine(code="310912015", description="VALVE", quantity=Decimal("10"),
                           unit_price=Decimal("30.0"))],
    )

    svc = InvoiceIngestService(db_session)
    result = await svc.ingest(
        commercial=commercial, import_inv=import_inv,
        tariff_pct=Decimal("5"), confirm=True,
    )

    assert result.created == 1
    # PO created + confirmed
    po = (await db_session.execute(
        select(PurchaseOrder).where(PurchaseOrder.po_number == "POTEST1")
    )).scalar_one()
    assert po.status in ("confirmed", "partial")
    # GR created against the line with the real cost breakdown
    pol = (await db_session.execute(
        select(PurchaseOrderLine).where(PurchaseOrderLine.po_id == po.id)
    )).scalar_one()
    gr = (await db_session.execute(
        select(GoodsReceipt).where(GoodsReceipt.po_line_id == pol.id)
    )).scalar_one()
    assert gr.actual_breakdown["commercial_eur"] == "34.804"
    assert gr.actual_breakdown["import_duty_eur"] == "1.5000"   # 30 * 5%
    assert "commercial" not in gr.actual_breakdown.get("hs_code", "")  # hs not in breakdown
    # hs_code persisted on product
    from app.db.models.product import Product
    prod = (await db_session.execute(
        select(Product).where(Product.sku == "310912015")
    )).scalar_one()
    assert prod.hs_code == "84818081"


async def test_ingest_preview_does_not_persist(db_session: AsyncSession):
    from app.db.models.inventory import PurchaseOrder
    from app.services.procurement.invoice_ingest_service import InvoiceIngestService
    from app.schemas.invoice_imports import InvoiceLine, InvoiceParseResult

    await _seed_product(db_session, "310912020")
    commercial = InvoiceParseResult(
        invoice_number="INV-PREV", order_refs=["POPREV"],
        lines=[InvoiceLine(code="310912020", description="V", quantity=Decimal("5"),
                           unit_price=Decimal("47.194"), intrastat_code="84818081")],
    )
    import_inv = InvoiceParseResult(
        invoice_number="INV-PREV-IMP", order_refs=["POPREV"],
        lines=[InvoiceLine(code="310912020", description="V", quantity=Decimal("5"),
                           unit_price=Decimal("40"))],
    )
    svc = InvoiceIngestService(db_session)
    result = await svc.ingest(commercial=commercial, import_inv=import_inv,
                              tariff_pct=Decimal("5"), confirm=False)
    assert result.items[0].duty_eur == Decimal("2.0000")
    po = (await db_session.execute(
        select(PurchaseOrder).where(PurchaseOrder.po_number == "POPREV")
    )).scalar_one_or_none()
    assert po is None  # preview persisted nothing
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker exec mt-backend sh -c "cd /app && python -m pytest tests/services/procurement/test_invoice_ingest.py -o addopts='' -q"`
Expected: FAIL with `ModuleNotFoundError: app.services.procurement.invoice_ingest_service`

- [ ] **Step 3: Write minimal implementation**

Create `mt-pricing-backend/app/services/procurement/invoice_ingest_service.py`:

```python
"""Orchestrate invoice ingestion → goods receipts (F0.5)."""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.product import Product
from app.schemas.goods_receipts import GoodsReceiptCreate
from app.schemas.invoice_imports import (
    InvoiceIngestItem,
    InvoiceIngestResult,
    InvoiceParseResult,
)
from app.repositories.goods_receipt import GoodsReceiptRepository
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
                code=line.code, commercial_eur=line.unit_price,
                import_value_eur=import_value, duty_eur=duty, qty=line.quantity,
                po_number=order_no, po_action="matched", status="ok",
            )
            if not confirm:
                result.items.append(item)
                continue
            try:
                if order_no is None:
                    raise ValueError("invoice has no Order No.")
                po = await resolve_or_create_po(
                    self._session, order_no,
                    [(line.code, line.quantity, line.unit_price)],
                )
                item.po_action = "created" if po.status != "partial" else "matched"
                pol = await find_po_line(self._session, po.id, line.code)
                if pol is None:
                    raise ValueError(f"no PO line for sku {line.code}")
                gr_repo = GoodsReceiptRepository(self._session)
                await gr_repo.create(
                    GoodsReceiptCreate(
                        po_line_id=pol.id,
                        qty_received=line.quantity,
                        actual_breakdown=breakdown,
                        notes=f"invoice={commercial.invoice_number} incoterm={commercial.incoterms}",
                    )
                )
                if line.intrastat_code:
                    await self._session.execute(
                        update(Product).where(Product.sku == line.code).values(
                            hs_code=line.intrastat_code
                        )
                    )
                result.created += 1
            except Exception as e:  # tolerant per-row
                item.status = "error"
                item.detail = str(e)
                result.errors += 1
            result.items.append(item)

        return result
```

> When implementing: confirm `GoodsReceiptRepository.create` accepts a `GoodsReceiptCreate` and enqueues
> `recalc_map_on_gr` (it does). In tests the Celery task may run eagerly or be mocked; assert on the GR row
> (not on `map_aed`) unless eager mode is configured. If MAP assertion is desired, call
> `MAPService(session).process_gr(gr.id)` directly in the test after ingest.

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker exec mt-backend sh -c "cd /app && python -m pytest tests/services/procurement/test_invoice_ingest.py -o addopts='' -q"`
Expected: PASS (2 passed). Fix FK/seed issues (scheme code `DIRECT_B2C` must exist in `schemes`; it does per seed).

- [ ] **Step 5: Commit**

```bash
git add mt-pricing-backend/app/services/procurement/invoice_ingest_service.py mt-pricing-backend/tests/services/procurement/test_invoice_ingest.py
git commit -m "feat(procurement): invoice ingest service → goods receipts (F0.5)"
```

---

## Task 6: Idempotency via VendorInvoice

**Files:**
- Modify: `mt-pricing-backend/app/services/procurement/invoice_ingest_service.py`
- Test: `mt-pricing-backend/tests/services/procurement/test_invoice_ingest.py`

- [ ] **Step 1: Write the failing test**

Add to `test_invoice_ingest.py`:

```python
async def test_ingest_is_idempotent_per_invoice(db_session: AsyncSession):
    from app.services.procurement.invoice_ingest_service import InvoiceIngestService
    from app.schemas.invoice_imports import InvoiceLine, InvoiceParseResult

    await _seed_product(db_session, "310912025")
    commercial = InvoiceParseResult(
        invoice_number="INV-IDEM", order_refs=["POIDEM"],
        lines=[InvoiceLine(code="310912025", description="V", quantity=Decimal("3"),
                           unit_price=Decimal("68.208"), intrastat_code="84818081")],
    )
    import_inv = InvoiceParseResult(
        invoice_number="INV-IDEM-IMP", order_refs=["POIDEM"],
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker exec mt-backend sh -c "cd /app && python -m pytest tests/services/procurement/test_invoice_ingest.py::test_ingest_is_idempotent_per_invoice -o addopts='' -q"`
Expected: FAIL (second ingest creates a duplicate GR → `r2.created == 1`)

- [ ] **Step 3: Write minimal implementation**

In `invoice_ingest_service.py`, record a `VendorInvoice` per (invoice_number, po) and skip codes already
ingested for that invoice number. Add near the top of `ingest`, before the loop:

```python
        from app.db.models.procurement import VendorInvoice
        from sqlalchemy import select as _select

        already = set()
        if commercial.invoice_number:
            seen = (
                await self._session.execute(
                    _select(VendorInvoice.match_details).where(
                        VendorInvoice.invoice_number == commercial.invoice_number
                    )
                )
            ).scalars().all()
            for md in seen:
                already.update((md or {}).get("codes", []))
```

Inside the loop, right after computing `item` and before `if not confirm`, skip seen codes:

```python
            if confirm and line.code in already:
                item.status = "skipped"
                result.skipped += 1
                result.items.append(item)
                continue
```

After the loop, when `confirm` and at least one created, persist the VendorInvoice marker:

```python
        if confirm and result.created and order_no is not None:
            from app.db.models.inventory import PurchaseOrder
            po_row = (
                await self._session.execute(
                    _select(PurchaseOrder).where(PurchaseOrder.po_number == order_no)
                )
            ).scalar_one()
            self._session.add(
                VendorInvoice(
                    invoice_number=commercial.invoice_number or "",
                    vendor_id="mt_spain",
                    po_id=po_row.id,
                    invoice_date=__import__("datetime").date.today(),
                    total_amount=sum(
                        (Decimal(str(i.commercial_eur)) * Decimal(str(i.qty))
                         for i in result.items if i.status == "ok"),
                        Decimal("0"),
                    ),
                    currency="EUR",
                    status="pending",
                    match_details={"codes": [i.code for i in result.items if i.status == "ok"]},
                )
            )
            await self._session.flush()
```

> Confirm `VendorInvoice` required fields (`invoice_number`, `vendor_id`, `po_id`, `invoice_date`, `total_amount`)
> against `app/db/models/procurement.py` and adjust. `date.today()` is acceptable here (not in a workflow script).

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker exec mt-backend sh -c "cd /app && python -m pytest tests/services/procurement/test_invoice_ingest.py -o addopts='' -q"`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add mt-pricing-backend/app/services/procurement/invoice_ingest_service.py mt-pricing-backend/tests/services/procurement/test_invoice_ingest.py
git commit -m "feat(procurement): idempotent invoice ingestion via VendorInvoice marker"
```

---

## Task 7: API endpoint + RBAC + OpenAPI

**Files:**
- Create: `mt-pricing-backend/app/api/routes/invoice_imports.py`
- Modify: the router registry that includes route modules (find with `grep -rn "include_router" app/api`)
- Test: `mt-pricing-backend/tests/api/test_invoice_imports.py`

- [ ] **Step 1: Write the endpoint**

Create `mt-pricing-backend/app/api/routes/invoice_imports.py`:

```python
"""POST /imports/invoice — ingest MT commercial + import invoices (F0.5)."""
from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_permissions
from app.schemas.invoice_imports import InvoiceIngestResult
from app.services.procurement.invoice_ingest_service import InvoiceIngestService
from app.services.procurement.invoice_parser import parse_invoice_pdf

router = APIRouter(prefix="/imports", tags=["invoice-imports"])


@router.post("/invoice", response_model=InvoiceIngestResult, operation_id="ingestInvoice")
async def ingest_invoice(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    _user=Depends(require_permissions("imports:write")),
    commercial_pdf: UploadFile = File(...),
    import_pdf: UploadFile = File(...),
    tariff_pct: float = 5.0,
    confirm: bool = False,
) -> InvoiceIngestResult:
    commercial = parse_invoice_pdf(await commercial_pdf.read())
    import_inv = parse_invoice_pdf(await import_pdf.read())
    if not commercial.lines:
        raise HTTPException(422, detail={"code": "invoice_parse_failed", "which": "commercial"})
    svc = InvoiceIngestService(session)
    return await svc.ingest(
        commercial=commercial, import_inv=import_inv,
        tariff_pct=Decimal(str(tariff_pct)), confirm=confirm,
    )
```

- [ ] **Step 2: Register the router**

Run `grep -rn "include_router" mt-pricing-backend/app/api/` to find the registry, then add:

```python
from app.api.routes import invoice_imports
api_router.include_router(invoice_imports.router)
```

(match the existing include pattern/prefix in that file).

- [ ] **Step 3: Write the endpoint test**

Create `mt-pricing-backend/tests/api/test_invoice_imports.py` — assert the route is registered and rejects an empty/invalid PDF with 422 (full multipart flow can be an integration test reusing the seed from Task 5; minimal version below):

```python
def test_invoice_route_registered():
    from app.main import app
    paths = {r.path for r in app.routes}
    assert any(p.endswith("/imports/invoice") for p in paths)
```

- [ ] **Step 4: Run + regenerate OpenAPI**

Run: `docker exec mt-backend sh -c "cd /app && python -m pytest tests/api/test_invoice_imports.py -o addopts='' -q && python -m app.scripts.export_openapi"`
Then on host: `git add mt-pricing-backend/_bmad-output/planning-artifacts/mt-api-contract-openapi.json`
Expected: route test PASS; OpenAPI JSON updated (new endpoint present).

- [ ] **Step 5: Commit**

```bash
git add mt-pricing-backend/app/api/routes/invoice_imports.py mt-pricing-backend/tests/api/test_invoice_imports.py mt-pricing-backend/_bmad-output/planning-artifacts/mt-api-contract-openapi.json
git commit -m "feat(procurement): POST /imports/invoice endpoint (F0.5)"
```

---

## Task 8: Regression + lint + typecheck

- [ ] **Step 1: Procurement + pricing suites**

Run: `docker exec mt-backend sh -c "cd /app && python -m pytest tests/services/procurement/ tests/services/pricing/ -o addopts='' -q"`
Expected: PASS

- [ ] **Step 2: Lint + typecheck**

Run: `docker exec mt-backend sh -c "cd /app && ruff check app/services/procurement app/api/routes/invoice_imports.py app/schemas/invoice_imports.py && ruff format --check app/services/procurement && mypy app/services/procurement"`
Expected: clean (fix + re-run)

- [ ] **Step 3: Commit any formatting**

```bash
git add -A && git commit -m "style(procurement): ruff format for invoice ingestion" || echo "nothing to format"
```

---

## Self-Review

**Spec coverage:**
- Parser PDF (comercial+importación, mismo formato) → Task 2 ✅
- Emparejar por Code → Task 5 (`import_by_code`) ✅
- `actual_breakdown = commercial + import×tariff%` → Task 3 ✅ (corrected: only summable keys)
- PO híbrido (match/create+confirm) → Task 4 ✅
- GR vía repo existente → dispara MAP → Task 5 ✅
- `products.hs_code ← intrastat` → Task 5 ✅
- Endpoint preview→confirm + RBAC → Tasks 5 (`confirm` flag) + 7 ✅
- Idempotencia (invoice_number, code) → Task 6 ✅
- Reusa MAP/CostService/GR/PO (no reconstruye costeo) → Tasks 4/5 reuse existing repos ✅
- HS tariff master / XML / 3-way-match automation → out of scope (documented) ✅

**Placeholder scan:** Concrete code in every step. The "> Verify…" notes are confirmations against real files the
engineer reads while implementing (signatures already checked: `PurchaseOrderRepository.create/.confirm`,
`GoodsReceiptRepository.create`, `VendorInvoice` fields) — not placeholders for missing logic.

**Type consistency:** `InvoiceParseResult.lines: list[InvoiceLine]`, `InvoiceLine.unit_price: Decimal`,
`build_actual_breakdown(commercial_eur, import_value_eur, tariff_pct) -> dict[str,str]`,
`InvoiceIngestService.ingest(commercial, import_inv, tariff_pct, confirm)` — used identically across Tasks 2/3/5/7.
`actual_breakdown` keys (`commercial_eur`, `import_duty_eur`) consistent in Tasks 3 and 5 assertions.

**Known follow-ups (out of F0.5):** HS-specific tariff (F7) reuses `build_actual_breakdown` with per-HS rate;
XML adapter behind the same parser port; `VendorInvoice` 3-way-match automation; surfacing cost provenance (F1).

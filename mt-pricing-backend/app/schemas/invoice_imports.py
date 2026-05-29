"""DTOs for supplier invoice ingestion (F0.5)."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel


class InvoiceLine(BaseModel):
    code: str  # SKU
    description: str
    quantity: Decimal
    unit_price: Decimal  # EUR (commercial: real cost; import: customs value)
    intrastat_code: str | None = None


class InvoiceParseResult(BaseModel):
    invoice_number: str | None
    incoterms: str | None
    currency: str = "EUR"
    order_refs: list[str] = []  # 'Order No.' values found
    lines: list[InvoiceLine] = []
    errors: list[dict] = []  # row-level parse errors


class InvoiceIngestItem(BaseModel):
    code: str
    commercial_eur: Decimal
    import_value_eur: Decimal
    duty_eur: Decimal
    qty: Decimal
    po_number: str | None
    po_action: str  # 'matched' | 'created'
    status: str  # 'ok' | 'skipped' | 'error'
    detail: str | None = None


class InvoiceIngestResult(BaseModel):
    created: int = 0
    skipped: int = 0
    errors: int = 0
    items: list[InvoiceIngestItem] = []

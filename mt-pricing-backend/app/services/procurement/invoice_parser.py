"""Supplier invoice PDF parser (F0.5). Pure text parsing + pdfplumber wrapper."""

from __future__ import annotations

import io
import re
from decimal import Decimal, InvalidOperation

from app.schemas.invoice_imports import InvoiceLine, InvoiceParseResult

_ITEM_RE = re.compile(
    r"^(?P<code>\d{5,})\s+(?P<desc>.+?)\s+(?P<qty>\d+)\s+"
    r"(?P<unit>[\d,]+\.\d+|\d+)\s+(?P<amount>[\d,]+\.\d+|\d+(?:\.\d+)?)$"
)
_INTRASTAT_RE = re.compile(r"Intrastat code\s*:\s*(\d+)")
_ORDER_RE = re.compile(r"Order No\.\s*:\s*(\S+)")
_INCOTERM_RE = re.compile(r"INCOTERMS\s*:\s*(\w+)")
_INVOICE_NO_RE = re.compile(r"^(\d{8,})\s+\d{2}/\d{2}/\d{4}")


def _num(raw: str) -> Decimal:
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

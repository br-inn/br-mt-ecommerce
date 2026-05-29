"""POST /imports/invoice — ingest MT commercial + import invoices (F0.5)."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_permissions
from app.db.models.user import User
from app.schemas.invoice_imports import InvoiceIngestResult
from app.services.procurement.invoice_ingest_service import InvoiceIngestService
from app.services.procurement.invoice_parser import parse_invoice_pdf

router = APIRouter(prefix="/imports", tags=["invoice-imports"])


@router.post("/invoice", response_model=InvoiceIngestResult, operation_id="ingestInvoice")
async def ingest_invoice(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    _user: Annotated[User, Depends(require_permissions("imports:write"))],
    commercial_pdf: UploadFile = File(...),
    import_pdf: UploadFile = File(...),
    tariff_pct: float = 5.0,
    confirm: bool = False,
) -> InvoiceIngestResult:
    """Ingest a commercial invoice + import invoice pair to cost records.

    - **commercial_pdf**: MT commercial invoice PDF (real cost per SKU).
    - **import_pdf**: customs import invoice PDF (intrastat values + duties).
    - **tariff_pct**: applicable tariff percentage (default 5 %).
    - **confirm**: dry-run when False (default); write to DB when True.
    """
    commercial = parse_invoice_pdf(await commercial_pdf.read())
    import_inv = parse_invoice_pdf(await import_pdf.read())
    if not commercial.lines:
        raise HTTPException(
            422,
            detail={"code": "invoice_parse_failed", "which": "commercial"},
        )
    svc = InvoiceIngestService(session)
    return await svc.ingest(
        commercial=commercial,
        import_inv=import_inv,
        tariff_pct=Decimal(str(tariff_pct)),
        confirm=confirm,
    )

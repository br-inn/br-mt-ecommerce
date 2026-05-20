"""Billing API v1 — EP-ERP-05 (US-ERP-05-01 … 06).

Endpoints US-ERP-05-01 — Document chain:
- POST   /billing/invoices                              — crear invoice
- GET    /billing/invoices                              — listar invoices
- GET    /billing/invoices/{id}                         — detalle invoice
- PATCH  /billing/invoices/{id}                         — actualizar invoice
- GET    /billing/invoices/{id}/chain                   — cadena invoice→SO→delivery
- POST   /billing/invoices/from-delivery/{delivery_id}  — crear desde delivery

Endpoints US-ERP-05-02 — Posting + FI:
- POST   /billing/invoices/{id}/post                    — postear invoice
- POST   /billing/invoices/{id}/cancel                  — cancelar
- POST   /billing/invoices/{id}/reverse                 — crear credit memo

Endpoints US-ERP-05-03 — Dunning:
- GET    /billing/dunning                               — invoices en mora
- POST   /billing/dunning/{invoice_id}/escalate         — subir nivel (gerente)

Endpoints US-ERP-05-04 — E-Invoice:
- POST   /billing/e-invoices/{invoice_id}/submit        — enviar a ZATCA/CFDI
- GET    /billing/e-invoices/{invoice_id}/submissions   — historial submissions
- POST   /billing/e-invoices/submissions/{id}/retry     — reintentar

Endpoints US-ERP-05-05 — AR Aging + Payment Promises:
- GET    /billing/ar-aging                              — aging report
- POST   /billing/payment-promises                      — crear promesa
- PATCH  /billing/payment-promises/{id}                 — actualizar promesa

Endpoints US-ERP-05-06 — KPIs:
- GET    /billing/kpis                                  — KPIs consolidados
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session, require_role
from app.db.models.billing import EInvoiceSubmission, Invoice, PaymentPromise
from app.db.models.user import User
from app.schemas.billing import (
    ARAgingReport,
    BillingKPIs,
    DunningEscalateRequest,
    DunningHistoryRead,
    EInvoiceSubmissionRead,
    EInvoiceSubmitRequest,
    InvoiceChain,
    InvoiceCreate,
    InvoicePatch,
    InvoiceRead,
    PaymentPromiseCreate,
    PaymentPromisePatch,
    PaymentPromiseRead,
)
from app.services import billing as svc

router = APIRouter(
    prefix="/api/v1/billing",
    tags=["billing"],
    dependencies=[Depends(require_role("admin", "gerente"))],
)

DbSession = Annotated[AsyncSession, Depends(get_db_session)]
CurrentUser = Annotated[User, Depends(get_current_user)]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_invoice_or_404(session: AsyncSession, invoice_id: UUID) -> Invoice:
    inv = await svc.get_invoice(session, invoice_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return inv


# ---------------------------------------------------------------------------
# US-ERP-05-01 — Invoices CRUD + Document chain
# ---------------------------------------------------------------------------

@router.post("/invoices", response_model=InvoiceRead, status_code=status.HTTP_201_CREATED)
async def create_invoice(
    data: InvoiceCreate,
    session: DbSession,
    current_user: CurrentUser,
) -> Any:
    """Crear nueva invoice."""
    inv = await svc.create_invoice(session, data)
    await session.commit()
    return inv


@router.get("/invoices", response_model=list[InvoiceRead])
async def list_invoices(
    session: DbSession,
    current_user: CurrentUser,
    customer_id: str | None = Query(default=None),
    inv_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
) -> Any:
    """Listar invoices con filtros opcionales."""
    return await svc.list_invoices(session, customer_id, inv_status, limit, offset)


@router.get("/invoices/{invoice_id}", response_model=InvoiceRead)
async def get_invoice(
    invoice_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
) -> Any:
    return await _get_invoice_or_404(session, invoice_id)


@router.patch("/invoices/{invoice_id}", response_model=InvoiceRead)
async def patch_invoice(
    invoice_id: UUID,
    data: InvoicePatch,
    session: DbSession,
    current_user: CurrentUser,
) -> Any:
    inv = await _get_invoice_or_404(session, invoice_id)
    updated = await svc.patch_invoice(session, inv, data)
    await session.commit()
    return updated


@router.get("/invoices/{invoice_id}/chain", response_model=InvoiceChain)
async def get_invoice_chain(
    invoice_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
) -> Any:
    """Retorna invoice + SO + delivery asociados."""
    inv = await _get_invoice_or_404(session, invoice_id)
    chain = await svc.get_invoice_chain(session, inv)
    return chain


@router.post("/invoices/from-delivery/{delivery_id}", response_model=InvoiceRead, status_code=status.HTTP_201_CREATED)
async def create_invoice_from_delivery(
    delivery_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
) -> Any:
    """Crear invoice copiando precios del SO/delivery."""
    try:
        inv = await svc.create_invoice_from_delivery(session, delivery_id, current_user.id)
        await session.commit()
        return inv
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# US-ERP-05-02 — Post / Cancel / Reverse
# ---------------------------------------------------------------------------

@router.post("/invoices/{invoice_id}/post", response_model=InvoiceRead)
async def post_invoice(
    invoice_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
) -> Any:
    """Postear invoice — status → posted, genera asientos FI y open_item."""
    inv = await _get_invoice_or_404(session, invoice_id)
    try:
        updated = await svc.post_invoice(session, inv)
        await session.commit()
        return updated
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/invoices/{invoice_id}/cancel", response_model=InvoiceRead)
async def cancel_invoice(
    invoice_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
) -> Any:
    """Cancelar invoice."""
    inv = await _get_invoice_or_404(session, invoice_id)
    try:
        updated = await svc.cancel_invoice(session, inv)
        await session.commit()
        return updated
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/invoices/{invoice_id}/reverse", response_model=InvoiceRead, status_code=status.HTTP_201_CREATED)
async def reverse_invoice(
    invoice_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
) -> Any:
    """Revertir invoice — crea Credit Memo."""
    inv = await _get_invoice_or_404(session, invoice_id)
    try:
        credit_memo = await svc.reverse_invoice(session, inv)
        await session.commit()
        return credit_memo
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# US-ERP-05-03 — Dunning
# ---------------------------------------------------------------------------

@router.get("/dunning", response_model=list[dict])
async def get_dunning(
    session: DbSession,
    current_user: CurrentUser,
    customer_id: str | None = Query(default=None),
    level: int | None = Query(default=None),
) -> Any:
    """Listar invoices en mora, opcionalmente filtradas por customer/nivel."""
    return await svc.get_dunning_invoices(session, customer_id, level)


@router.post("/dunning/{invoice_id}/escalate", response_model=DunningHistoryRead)
async def escalate_dunning(
    invoice_id: UUID,
    data: DunningEscalateRequest,
    session: DbSession,
    current_user: Annotated[User, Depends(require_role("gerente"))],
) -> Any:
    """Escalar dunning manualmente (rol gerente)."""
    inv = await _get_invoice_or_404(session, invoice_id)
    try:
        history = await svc.escalate_dunning(session, inv, data.notes)
        await session.commit()
        return history
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# US-ERP-05-04 — E-Invoice
# ---------------------------------------------------------------------------

@router.post("/e-invoices/{invoice_id}/submit", response_model=EInvoiceSubmissionRead, status_code=status.HTTP_201_CREATED)
async def submit_e_invoice(
    invoice_id: UUID,
    req: EInvoiceSubmitRequest,
    session: DbSession,
    current_user: CurrentUser,
) -> Any:
    """Enviar invoice a ZATCA/CFDI/UBL."""
    inv = await _get_invoice_or_404(session, invoice_id)
    sub = await svc.submit_e_invoice(session, inv, req)
    await session.commit()
    return sub


@router.get("/e-invoices/{invoice_id}/submissions", response_model=list[EInvoiceSubmissionRead])
async def list_e_invoice_submissions(
    invoice_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
) -> Any:
    """Historial de submissions para una invoice."""
    result = await session.execute(
        select(EInvoiceSubmission).where(EInvoiceSubmission.invoice_id == invoice_id)
    )
    return list(result.scalars().all())


@router.post("/e-invoices/submissions/{submission_id}/retry", response_model=EInvoiceSubmissionRead)
async def retry_e_invoice(
    submission_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
) -> Any:
    """Reintentar submission rechazada."""
    try:
        sub = await svc.retry_e_invoice(session, submission_id)
        await session.commit()
        return sub
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# US-ERP-05-05 — AR Aging + Payment Promises
# ---------------------------------------------------------------------------

@router.get("/ar-aging", response_model=ARAgingReport)
async def get_ar_aging(
    session: DbSession,
    current_user: CurrentUser,
    as_of_date: date | None = Query(default=None),
) -> Any:
    """AR Aging report por customer, segmentado en buckets estándar."""
    buckets = await svc.get_ar_aging(session, as_of_date)
    return ARAgingReport(as_of_date=as_of_date or date.today(), buckets=buckets)


@router.post("/payment-promises", response_model=PaymentPromiseRead, status_code=status.HTTP_201_CREATED)
async def create_payment_promise(
    data: PaymentPromiseCreate,
    session: DbSession,
    current_user: CurrentUser,
) -> Any:
    pp = await svc.create_payment_promise(session, data, current_user.id)
    await session.commit()
    return pp


@router.patch("/payment-promises/{promise_id}", response_model=PaymentPromiseRead)
async def patch_payment_promise(
    promise_id: UUID,
    data: PaymentPromisePatch,
    session: DbSession,
    current_user: CurrentUser,
) -> Any:
    try:
        pp = await svc.patch_payment_promise(session, promise_id, data)
        await session.commit()
        return pp
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# US-ERP-05-06 — KPIs
# ---------------------------------------------------------------------------

@router.get("/kpis", response_model=BillingKPIs)
async def get_billing_kpis(
    session: DbSession,
    current_user: CurrentUser,
) -> Any:
    """KPIs consolidados de billing — DSO, CEI, TTI, compliance, overdue."""
    return await svc.get_billing_kpis(session)

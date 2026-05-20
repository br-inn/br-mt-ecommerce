"""Procurement API v1 — EP-ERP-03 (US-ERP-03-01 … 06).

Endpoints US-ERP-03-01/02/03 (existentes):
- POST   /procurement/requisitions              — crear PR en draft
- GET    /procurement/requisitions              — listar PRs
- GET    /procurement/requisitions/{id}         — detalle PR
- PATCH  /procurement/requisitions/{id}/submit  — draft → pending_approval (o auto-approved)
- PATCH  /procurement/requisitions/{id}/approve — pending_approval → approved (gerente/ti)
- PATCH  /procurement/requisitions/{id}/reject  — pending_approval → rejected (gerente/ti)
- PATCH  /procurement/requisitions/{id}/cancel  — cualquier estado → cancelled (excepto converted_to_po)

- GET    /procurement/approval-rules             — listar reglas
- POST   /procurement/approval-rules             — crear regla
- PATCH  /procurement/approval-rules/{id}        — actualizar regla

- GET    /procurement/vendor-conditions          — PIRs vigentes (filtros vendor_id, product_sku)
- POST   /procurement/vendor-conditions          — crear PIR
- PUT    /procurement/vendor-conditions/{id}     — actualizar PIR

Endpoints US-ERP-03-04 — 3-way match:
- POST   /procurement/invoices                          — registrar factura
- GET    /procurement/invoices                          — listar facturas
- POST   /procurement/invoices/{id}/match               — ejecutar 3-way match
- POST   /procurement/invoices/{id}/release-block       — liberar bloqueo de pago (gerente)
- GET    /procurement/invoice-tolerances                — listar tolerancias
- POST   /procurement/invoice-tolerances                — crear tolerancia
- PATCH  /procurement/invoice-tolerances/{id}           — actualizar tolerancia

Endpoints US-ERP-03-05 — Source List + RFQ:
- GET    /procurement/source-list                       — listar (filtro product_sku)
- POST   /procurement/source-list                       — crear entrada
- PATCH  /procurement/source-list/{id}                  — actualizar entrada
- DELETE /procurement/source-list/{id}                  — eliminar entrada
- POST   /procurement/rfqs                              — crear RFQ
- GET    /procurement/rfqs                              — listar RFQs
- POST   /procurement/rfqs/{id}/responses               — registrar respuesta
- GET    /procurement/rfqs/{id}/comparison              — tabla comparativa

Endpoints US-ERP-03-06 — Dashboard KPIs:
- GET    /procurement/kpis                              — KPIs consolidados
- GET    /procurement/spend-analysis                    — análisis de spend
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, get_current_user, require_permissions, require_role
from app.db.models.inventory import GoodsReceipt, PurchaseOrder, PurchaseOrderLine
from app.db.models.procurement import (
    InvoiceTolerance,
    RfqHeader,
    RfqLine,
    RfqVendorResponse,
    SourceList,
    VendorInvoice,
)
from app.db.models.user import User
from app.repositories.procurement import ProcurementRepository
from app.schemas.common import ProblemDetails
from app.schemas.procurement import (
    ApprovalDecisionOut,
    ApprovalRuleCreate,
    ApprovalRuleOut,
    ApprovalRuleUpdate,
    InvoiceReleaseBlock,
    InvoiceToleranceCreate,
    InvoiceToleranceOut,
    InvoiceToleranceUpdate,
    PRCreate,
    PROut,
    PRReject,
    ProcurementKpiOut,
    RfqComparisonItem,
    RfqComparisonOut,
    RfqCreate,
    RfqOut,
    RfqResponseCreate,
    RfqResponseOut,
    SourceListCreate,
    SourceListOut,
    SourceListUpdate,
    SpendAnalysisOut,
    SpendByProduct,
    SpendByVendor,
    VendorConditionCreate,
    VendorConditionOut,
    VendorConditionUpdate,
    VendorInvoiceCreate,
    VendorInvoiceOut,
)
from app.services.procurement_match import perform_three_way_match

router = APIRouter(prefix="/procurement", tags=["procurement"])

_APPROVER_ROLES = ("gerente", "ti")


# ---------------------------------------------------------------------------
# Purchase Requisitions
# ---------------------------------------------------------------------------

@router.post(
    "/requisitions",
    response_model=PROut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear Purchase Requisition en estado draft",
    operation_id="procurementRequisitionsCreate",
    responses={422: {"model": ProblemDetails}},
)
async def create_pr(
    data: PRCreate,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PROut:
    repo = ProcurementRepository(session)
    pr = await repo.create_pr(data, requester_id=user.id)
    await session.commit()
    await session.refresh(pr)
    return PROut.model_validate(pr)


@router.post(
    "/requisitions/{pr_id}/convert-to-po",
    summary="Convertir PR aprobada a Purchase Order",
    operation_id="procurementConvertPrToPo",
    status_code=201,
)
async def convert_pr_to_po(
    pr_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    from app.repositories.procurement import ProcurementRepository
    repo = ProcurementRepository(db)
    po = await repo.convert_pr_to_po(pr_id, created_by=current_user.id)
    await db.commit()
    return {"po_id": str(po.id), "po_number": po.po_number, "status": po.status}


@router.get(
    "/requisitions",
    response_model=list[PROut],
    summary="Listar Purchase Requisitions",
    operation_id="procurementRequisitionsList",
)
async def list_prs(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    status_filter: str | None = Query(default=None, alias="status"),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[PROut]:
    repo = ProcurementRepository(session)

    # gerente y ti ven todas; el resto solo las suyas
    role_code = user.role.code if user.role else None
    viewer_id = None if role_code in _APPROVER_ROLES else user.id

    cursor_uuid: UUID | None = None
    if cursor:
        try:
            cursor_uuid = UUID(cursor)
        except ValueError:
            pass

    rows, _ = await repo.list_prs(
        requester_id=viewer_id,
        status=status_filter,
        limit=limit,
        cursor=cursor_uuid,
    )
    return [PROut.model_validate(pr) for pr in rows]


@router.get(
    "/requisitions/{pr_id}",
    response_model=PROut,
    summary="Detalle de Purchase Requisition",
    operation_id="procurementRequisitionsGet",
    responses={404: {"model": ProblemDetails}},
)
async def get_pr(
    pr_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PROut:
    repo = ProcurementRepository(session)
    pr = await repo._get_or_404(pr_id)
    role_code = user.role.code if user.role else None
    if role_code not in _APPROVER_ROLES and pr.requester_id != user.id:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "pr_forbidden", "title": "Solo puedes ver tus propias PRs"},
        )
    return PROut.model_validate(pr)


@router.patch(
    "/requisitions/{pr_id}/submit",
    response_model=PROut,
    summary="Enviar PR a aprobación (draft → pending_approval o auto-approved)",
    operation_id="procurementRequisitionsSubmit",
    responses={422: {"model": ProblemDetails}},
)
async def submit_pr(
    pr_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PROut:
    repo = ProcurementRepository(session)
    pr = await repo.submit_pr(pr_id)
    await session.commit()
    await session.refresh(pr)
    return PROut.model_validate(pr)


@router.patch(
    "/requisitions/{pr_id}/approve",
    response_model=PROut,
    summary="Aprobar PR (pending_approval → approved)",
    operation_id="procurementRequisitionsApprove",
    responses={403: {"model": ProblemDetails}, 422: {"model": ProblemDetails}},
)
async def approve_pr(
    pr_id: UUID,
    user: Annotated[User, Depends(require_role(*_APPROVER_ROLES))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PROut:
    repo = ProcurementRepository(session)
    pr = await repo.approve_pr(pr_id, approver_id=user.id)
    await session.commit()
    await session.refresh(pr)
    return PROut.model_validate(pr)


@router.patch(
    "/requisitions/{pr_id}/reject",
    response_model=PROut,
    summary="Rechazar PR (requiere motivo)",
    operation_id="procurementRequisitionsReject",
    responses={403: {"model": ProblemDetails}, 422: {"model": ProblemDetails}},
)
async def reject_pr(
    pr_id: UUID,
    body: PRReject,
    user: Annotated[User, Depends(require_role(*_APPROVER_ROLES))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PROut:
    repo = ProcurementRepository(session)
    pr = await repo.reject_pr(pr_id, approver_id=user.id, reason=body.reason)
    await session.commit()
    await session.refresh(pr)
    return PROut.model_validate(pr)


@router.patch(
    "/requisitions/{pr_id}/cancel",
    response_model=PROut,
    summary="Cancelar PR",
    operation_id="procurementRequisitionsCancel",
    responses={422: {"model": ProblemDetails}},
)
async def cancel_pr(
    pr_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PROut:
    repo = ProcurementRepository(session)
    pr = await repo.cancel_pr(pr_id)
    await session.commit()
    await session.refresh(pr)
    return PROut.model_validate(pr)


# ---------------------------------------------------------------------------
# Approval Rules (admin)
# ---------------------------------------------------------------------------

@router.get(
    "/approval-rules",
    response_model=list[ApprovalRuleOut],
    summary="Listar reglas de aprobación",
    operation_id="procurementApprovalRulesList",
)
async def list_approval_rules(
    _user: Annotated[User, Depends(require_role(*_APPROVER_ROLES))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[ApprovalRuleOut]:
    repo = ProcurementRepository(session)
    rules = await repo.list_approval_rules()
    return [ApprovalRuleOut.model_validate(r) for r in rules]


@router.post(
    "/approval-rules",
    response_model=ApprovalRuleOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear regla de aprobación",
    operation_id="procurementApprovalRulesCreate",
)
async def create_approval_rule(
    data: ApprovalRuleCreate,
    _user: Annotated[User, Depends(require_role("ti"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ApprovalRuleOut:
    repo = ProcurementRepository(session)
    rule = await repo.create_approval_rule(data.model_dump())
    await session.commit()
    await session.refresh(rule)
    return ApprovalRuleOut.model_validate(rule)


@router.patch(
    "/approval-rules/{rule_id}",
    response_model=ApprovalRuleOut,
    summary="Actualizar regla de aprobación",
    operation_id="procurementApprovalRulesUpdate",
    responses={404: {"model": ProblemDetails}},
)
async def update_approval_rule(
    rule_id: UUID,
    data: ApprovalRuleUpdate,
    _user: Annotated[User, Depends(require_role("ti"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ApprovalRuleOut:
    repo = ProcurementRepository(session)
    rule = await repo.update_approval_rule(
        rule_id, data.model_dump(exclude_unset=True)
    )
    await session.commit()
    await session.refresh(rule)
    return ApprovalRuleOut.model_validate(rule)


@router.delete(
    "/approval-rules/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Eliminar regla de aprobación",
    operation_id="procurementApprovalRulesDelete",
    responses={404: {"model": ProblemDetails}},
)
async def delete_approval_rule(
    rule_id: UUID,
    _user: Annotated[User, Depends(require_role("ti"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    repo = ProcurementRepository(session)
    await repo.delete_approval_rule(rule_id)
    await session.commit()


@router.get(
    "/requisitions/{pr_id}/decisions",
    response_model=list[ApprovalDecisionOut],
    summary="Historial de decisiones de aprobación para una PR",
    operation_id="procurementRequisitionsDecisions",
    responses={404: {"model": ProblemDetails}},
)
async def get_pr_decisions(
    pr_id: UUID,
    _user: Annotated[User, Depends(require_role(*_APPROVER_ROLES))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[ApprovalDecisionOut]:
    repo = ProcurementRepository(session)
    await repo._get_or_404(pr_id)
    decisions = await repo.get_pr_decisions(pr_id)
    return [ApprovalDecisionOut.model_validate(d) for d in decisions]


# ---------------------------------------------------------------------------
# Vendor Product Conditions / PIR
# ---------------------------------------------------------------------------

@router.get(
    "/vendor-conditions",
    response_model=list[VendorConditionOut],
    summary="Listar PIRs vigentes",
    operation_id="procurementVendorConditionsList",
)
async def list_vendor_conditions(
    _user: Annotated[User, Depends(require_permissions("purchases:write"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    vendor_id: str | None = Query(default=None),
    product_sku: str | None = Query(default=None),
    active_only: bool = Query(default=True),
) -> list[VendorConditionOut]:
    repo = ProcurementRepository(session)
    vcs = await repo.list_vendor_conditions(
        vendor_id=vendor_id,
        product_sku=product_sku,
        active_only=active_only,
    )
    return [VendorConditionOut.model_validate(vc) for vc in vcs]


@router.post(
    "/vendor-conditions",
    response_model=VendorConditionOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear PIR (condición proveedor-producto)",
    operation_id="procurementVendorConditionsCreate",
)
async def create_vendor_condition(
    data: VendorConditionCreate,
    _user: Annotated[User, Depends(require_role("ti", "gerente"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> VendorConditionOut:
    repo = ProcurementRepository(session)
    vc = await repo.create_vendor_condition(data)
    await session.commit()
    await session.refresh(vc)
    return VendorConditionOut.model_validate(vc)


@router.put(
    "/vendor-conditions/{vc_id}",
    response_model=VendorConditionOut,
    summary="Actualizar PIR",
    operation_id="procurementVendorConditionsUpdate",
    responses={404: {"model": ProblemDetails}},
)
async def update_vendor_condition(
    vc_id: UUID,
    data: VendorConditionUpdate,
    _user: Annotated[User, Depends(require_role("ti", "gerente"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> VendorConditionOut:
    repo = ProcurementRepository(session)
    vc = await repo.update_vendor_condition(vc_id, data.model_dump(exclude_unset=True))
    await session.commit()
    await session.refresh(vc)
    return VendorConditionOut.model_validate(vc)


# ---------------------------------------------------------------------------
# US-ERP-03-04 — Vendor Invoices + 3-way match
# ---------------------------------------------------------------------------

def _next_invoice_number() -> str:
    """Genera número de factura interno provisional (INVYYYYMMDD-XXXX)."""
    from datetime import date as _date
    import random
    return f"INV{_date.today().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"


@router.post(
    "/invoices",
    response_model=VendorInvoiceOut,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar factura de proveedor",
    operation_id="procurementInvoicesCreate",
    responses={422: {"model": ProblemDetails}},
)
async def create_invoice(
    data: VendorInvoiceCreate,
    _user: Annotated[User, Depends(require_permissions("purchases:write"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> VendorInvoiceOut:
    invoice = VendorInvoice(
        id=uuid4(),
        invoice_number=data.invoice_number,
        vendor_id=data.vendor_id,
        po_id=data.po_id,
        gr_id=data.gr_id,
        invoice_date=data.invoice_date,
        total_amount=data.total_amount,
        currency=data.currency,
        status="pending",
        payment_block=False,
        match_details=None,
    )
    session.add(invoice)
    await session.commit()
    await session.refresh(invoice)
    return VendorInvoiceOut.model_validate(invoice)


@router.get(
    "/invoices",
    response_model=list[VendorInvoiceOut],
    summary="Listar facturas de proveedor",
    operation_id="procurementInvoicesList",
)
async def list_invoices(
    _user: Annotated[User, Depends(require_permissions("purchases:write"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    vendor_id: str | None = Query(default=None),
    invoice_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[VendorInvoiceOut]:
    stmt = select(VendorInvoice)
    if vendor_id:
        stmt = stmt.where(VendorInvoice.vendor_id == vendor_id)
    if invoice_status:
        stmt = stmt.where(VendorInvoice.status == invoice_status)
    stmt = stmt.order_by(VendorInvoice.created_at.desc()).limit(limit)
    result = await session.execute(stmt)
    invoices = result.scalars().all()
    return [VendorInvoiceOut.model_validate(i) for i in invoices]


@router.post(
    "/invoices/{invoice_id}/match",
    response_model=VendorInvoiceOut,
    summary="Ejecutar 3-way match en factura",
    operation_id="procurementInvoicesMatch",
    responses={404: {"model": ProblemDetails}, 422: {"model": ProblemDetails}},
)
async def match_invoice(
    invoice_id: UUID,
    _user: Annotated[User, Depends(require_permissions("purchases:write"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> VendorInvoiceOut:
    try:
        await perform_three_way_match(invoice_id, session)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    await session.commit()
    invoice = await session.get(VendorInvoice, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Factura no encontrada")
    return VendorInvoiceOut.model_validate(invoice)


@router.post(
    "/invoices/{invoice_id}/release-block",
    response_model=VendorInvoiceOut,
    summary="Liberar bloqueo de pago de factura (requiere gerente)",
    operation_id="procurementInvoicesReleaseBlock",
    responses={403: {"model": ProblemDetails}, 404: {"model": ProblemDetails}},
)
async def release_invoice_block(
    invoice_id: UUID,
    body: InvoiceReleaseBlock,
    _user: Annotated[User, Depends(require_role("gerente"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> VendorInvoiceOut:
    invoice = await session.get(VendorInvoice, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Factura no encontrada")
    if not invoice.payment_block:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La factura no está bloqueada",
        )
    invoice.payment_block = False
    invoice.status = "approved"
    details: dict[str, Any] = dict(invoice.match_details or {})
    details["release_reason"] = body.reason
    invoice.match_details = details
    session.add(invoice)
    await session.commit()
    await session.refresh(invoice)
    return VendorInvoiceOut.model_validate(invoice)


# ---------------------------------------------------------------------------
# Invoice Tolerances CRUD
# ---------------------------------------------------------------------------

@router.get(
    "/invoice-tolerances",
    response_model=list[InvoiceToleranceOut],
    summary="Listar claves de tolerancia",
    operation_id="procurementInvoiceTolerancesList",
)
async def list_invoice_tolerances(
    _user: Annotated[User, Depends(require_role("ti", "gerente"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    active_only: bool = Query(default=True),
) -> list[InvoiceToleranceOut]:
    stmt = select(InvoiceTolerance)
    if active_only:
        stmt = stmt.where(InvoiceTolerance.is_active.is_(True))
    result = await session.execute(stmt)
    return [InvoiceToleranceOut.model_validate(t) for t in result.scalars().all()]


@router.post(
    "/invoice-tolerances",
    response_model=InvoiceToleranceOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear clave de tolerancia",
    operation_id="procurementInvoiceTolerancesCreate",
)
async def create_invoice_tolerance(
    data: InvoiceToleranceCreate,
    _user: Annotated[User, Depends(require_role("ti"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> InvoiceToleranceOut:
    tol = InvoiceTolerance(id=uuid4(), **data.model_dump())
    session.add(tol)
    await session.commit()
    await session.refresh(tol)
    return InvoiceToleranceOut.model_validate(tol)


@router.patch(
    "/invoice-tolerances/{tol_id}",
    response_model=InvoiceToleranceOut,
    summary="Actualizar clave de tolerancia",
    operation_id="procurementInvoiceTolerancesUpdate",
    responses={404: {"model": ProblemDetails}},
)
async def update_invoice_tolerance(
    tol_id: UUID,
    data: InvoiceToleranceUpdate,
    _user: Annotated[User, Depends(require_role("ti"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> InvoiceToleranceOut:
    tol = await session.get(InvoiceTolerance, tol_id)
    if tol is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tolerancia no encontrada")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(tol, field, value)
    session.add(tol)
    await session.commit()
    await session.refresh(tol)
    return InvoiceToleranceOut.model_validate(tol)


# ---------------------------------------------------------------------------
# US-ERP-03-05 — Source List
# ---------------------------------------------------------------------------

@router.get(
    "/source-list",
    response_model=list[SourceListOut],
    summary="Listar proveedores aprobados (Source List)",
    operation_id="procurementSourceListList",
)
async def list_source_list(
    _user: Annotated[User, Depends(require_permissions("purchases:write"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    product_sku: str | None = Query(default=None),
    include_blocked: bool = Query(default=False),
) -> list[SourceListOut]:
    stmt = select(SourceList)
    if product_sku:
        stmt = stmt.where(SourceList.product_sku == product_sku)
    if not include_blocked:
        stmt = stmt.where(SourceList.is_blocked.is_(False))
    stmt = stmt.order_by(SourceList.is_preferred.desc(), SourceList.vendor_id)
    result = await session.execute(stmt)
    return [SourceListOut.model_validate(s) for s in result.scalars().all()]


@router.post(
    "/source-list",
    response_model=SourceListOut,
    status_code=status.HTTP_201_CREATED,
    summary="Agregar proveedor a Source List",
    operation_id="procurementSourceListCreate",
)
async def create_source_list(
    data: SourceListCreate,
    _user: Annotated[User, Depends(require_role("ti", "gerente"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SourceListOut:
    payload = data.model_dump()
    if payload.get("valid_from") is None:
        from datetime import date as _date
        payload["valid_from"] = _date.today()
    sl = SourceList(id=uuid4(), **payload)
    session.add(sl)
    await session.commit()
    await session.refresh(sl)
    return SourceListOut.model_validate(sl)


@router.patch(
    "/source-list/{sl_id}",
    response_model=SourceListOut,
    summary="Actualizar entrada de Source List",
    operation_id="procurementSourceListUpdate",
    responses={404: {"model": ProblemDetails}},
)
async def update_source_list(
    sl_id: UUID,
    data: SourceListUpdate,
    _user: Annotated[User, Depends(require_role("ti", "gerente"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SourceListOut:
    sl = await session.get(SourceList, sl_id)
    if sl is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entrada no encontrada")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(sl, field, value)
    session.add(sl)
    await session.commit()
    await session.refresh(sl)
    return SourceListOut.model_validate(sl)


@router.delete(
    "/source-list/{sl_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Eliminar entrada de Source List",
    operation_id="procurementSourceListDelete",
)
async def delete_source_list(
    sl_id: UUID,
    _user: Annotated[User, Depends(require_role("ti", "gerente"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    sl = await session.get(SourceList, sl_id)
    if sl is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entrada no encontrada")
    await session.delete(sl)
    await session.commit()


# ---------------------------------------------------------------------------
# RFQ
# ---------------------------------------------------------------------------

def _next_rfq_number() -> str:
    from datetime import date as _date
    import random
    return f"RFQ{_date.today().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"


@router.post(
    "/rfqs",
    response_model=RfqOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear RFQ",
    operation_id="procurementRfqsCreate",
    responses={422: {"model": ProblemDetails}},
)
async def create_rfq(
    data: RfqCreate,
    user: Annotated[User, Depends(require_permissions("purchases:write"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> RfqOut:
    rfq_id = uuid4()
    rfq = RfqHeader(
        id=rfq_id,
        rfq_number=_next_rfq_number(),
        pr_id=data.pr_id,
        status="draft",
        deadline=data.deadline,
        notes=data.notes,
        created_by=user.id,
    )
    session.add(rfq)
    for line_data in data.lines:
        line = RfqLine(
            id=uuid4(),
            rfq_id=rfq_id,
            product_sku=line_data.product_sku,
            qty=line_data.qty,
            uom=line_data.uom,
        )
        session.add(line)
    await session.commit()
    await session.refresh(rfq)
    return RfqOut.model_validate(rfq)


@router.get(
    "/rfqs",
    response_model=list[RfqOut],
    summary="Listar RFQs",
    operation_id="procurementRfqsList",
)
async def list_rfqs(
    _user: Annotated[User, Depends(require_permissions("purchases:write"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    rfq_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[RfqOut]:
    stmt = select(RfqHeader)
    if rfq_status:
        stmt = stmt.where(RfqHeader.status == rfq_status)
    stmt = stmt.order_by(RfqHeader.created_at.desc()).limit(limit)
    result = await session.execute(stmt)
    return [RfqOut.model_validate(r) for r in result.scalars().all()]


@router.post(
    "/rfqs/{rfq_id}/responses",
    response_model=RfqResponseOut,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar respuesta de proveedor a RFQ",
    operation_id="procurementRfqsResponseCreate",
    responses={404: {"model": ProblemDetails}},
)
async def create_rfq_response(
    rfq_id: UUID,
    data: RfqResponseCreate,
    _user: Annotated[User, Depends(require_permissions("purchases:write"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> RfqResponseOut:
    rfq = await session.get(RfqHeader, rfq_id)
    if rfq is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RFQ no encontrado")

    # Upsert — si ya existe respuesta del mismo vendor, actualizar
    existing_result = await session.execute(
        select(RfqVendorResponse).where(
            RfqVendorResponse.rfq_id == rfq_id,
            RfqVendorResponse.vendor_id == data.vendor_id,
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(existing, field, value)
        existing.responded_at = datetime.now(tz=timezone.utc)
        session.add(existing)
        await session.commit()
        await session.refresh(existing)
        return RfqResponseOut.model_validate(existing)

    resp = RfqVendorResponse(
        id=uuid4(),
        rfq_id=rfq_id,
        vendor_id=data.vendor_id,
        unit_price=data.unit_price,
        currency=data.currency,
        lead_time_days=data.lead_time_days,
        valid_until=data.valid_until,
        notes=data.notes,
        responded_at=datetime.now(tz=timezone.utc),
    )
    session.add(resp)
    # Actualizar status de RFQ
    if rfq.status == "sent":
        rfq.status = "responses_received"
        session.add(rfq)
    await session.commit()
    await session.refresh(resp)
    return RfqResponseOut.model_validate(resp)


@router.get(
    "/rfqs/{rfq_id}/comparison",
    response_model=RfqComparisonOut,
    summary="Tabla comparativa de respuestas de RFQ",
    operation_id="procurementRfqsComparison",
    responses={404: {"model": ProblemDetails}},
)
async def rfq_comparison(
    rfq_id: UUID,
    _user: Annotated[User, Depends(require_permissions("purchases:write"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> RfqComparisonOut:
    rfq = await session.get(RfqHeader, rfq_id)
    if rfq is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RFQ no encontrado")

    resp_result = await session.execute(
        select(RfqVendorResponse).where(RfqVendorResponse.rfq_id == rfq_id)
    )
    responses = list(resp_result.scalars().all())

    # Calcular scores: score = 0.6*(1/precio_norm) + 0.4*(1/lead_time_norm)
    prices = [r.unit_price for r in responses if r.unit_price is not None and r.unit_price > 0]
    leads = [r.lead_time_days for r in responses if r.lead_time_days is not None and r.lead_time_days > 0]

    min_price = min(prices) if prices else None
    min_lead = min(leads) if leads else None

    items: list[RfqComparisonItem] = []
    for r in responses:
        score: float | None = None
        if min_price and r.unit_price and r.unit_price > 0 and min_lead and r.lead_time_days and r.lead_time_days > 0:
            price_norm = float(r.unit_price) / float(min_price)
            lead_norm = float(r.lead_time_days) / float(min_lead)
            score = round(0.6 * (1 / price_norm) + 0.4 * (1 / lead_norm), 4)
        items.append(
            RfqComparisonItem(
                vendor_id=r.vendor_id,
                unit_price=r.unit_price,
                currency=r.currency,
                lead_time_days=r.lead_time_days,
                score=score,
            )
        )

    # Ordenar por score desc (None al final)
    items.sort(key=lambda x: (x.score is None, -(x.score or 0)))

    return RfqComparisonOut(rfq_id=rfq_id, rfq_number=rfq.rfq_number, items=items)


# ---------------------------------------------------------------------------
# US-ERP-03-06 — Dashboard KPIs + Spend Analysis
# ---------------------------------------------------------------------------

@router.get(
    "/kpis",
    response_model=ProcurementKpiOut,
    summary="KPIs consolidados del módulo de compras",
    operation_id="procurementKpis",
)
async def procurement_kpis(
    _user: Annotated[User, Depends(require_permissions("purchases:write"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProcurementKpiOut:
    from app.db.models.procurement import PurchaseRequisition

    # open_pr_count — PRs en pending_approval o approved
    pr_count_result = await session.execute(
        select(func.count()).select_from(PurchaseRequisition).where(
            PurchaseRequisition.status.in_(("pending_approval", "approved"))
        )
    )
    open_pr_count: int = pr_count_result.scalar_one() or 0

    # open_po_count — POs en approved/sent/partially_received (equivalente a confirmed/partial)
    po_count_result = await session.execute(
        select(func.count()).select_from(PurchaseOrder).where(
            PurchaseOrder.status.in_(("confirmed", "partial"))
        )
    )
    open_po_count: int = po_count_result.scalar_one() or 0

    # pending_invoice_count y blocked_invoice_amount
    inv_pending_result = await session.execute(
        select(func.count()).select_from(VendorInvoice).where(
            VendorInvoice.status.in_(("pending", "blocked"))
        )
    )
    pending_invoice_count: int = inv_pending_result.scalar_one() or 0

    blocked_amount_result = await session.execute(
        select(func.coalesce(func.sum(VendorInvoice.total_amount), Decimal("0"))).where(
            VendorInvoice.status == "blocked"
        )
    )
    blocked_invoice_amount: Decimal = blocked_amount_result.scalar_one() or Decimal("0")

    # maverick_spend_pct — aproximación: GRs sin PO / total GRs (simplificado → 0 porque toda GR tiene po_line_id)
    # En este modelo todas las GRs están asociadas a PO, así que maverick = 0
    maverick_spend_pct = Decimal("0")

    # avg_po_lead_time_days — promedio días entre created_at de PO y received_at de GR
    lead_time_result = await session.execute(
        select(
            func.avg(
                func.extract("epoch", GoodsReceipt.received_at - PurchaseOrder.confirmed_at) / 86400
            )
        )
        .select_from(GoodsReceipt)
        .join(PurchaseOrderLine, GoodsReceipt.po_line_id == PurchaseOrderLine.id)
        .join(PurchaseOrder, PurchaseOrderLine.po_id == PurchaseOrder.id)
        .where(PurchaseOrder.confirmed_at.isnot(None))
    )
    avg_lead_raw = lead_time_result.scalar_one()
    avg_po_lead_time_days: Decimal | None = (
        Decimal(str(round(float(avg_lead_raw), 2))) if avg_lead_raw is not None else None
    )

    # on_time_delivery_pct — GRs recibidas antes o en deadline de PO (no hay campo deadline en PO existente)
    # Sin campo deadline en PO, retornamos None
    on_time_delivery_pct: Decimal | None = None

    return ProcurementKpiOut(
        open_pr_count=open_pr_count,
        open_po_count=open_po_count,
        pending_invoice_count=pending_invoice_count,
        blocked_invoice_amount=blocked_invoice_amount,
        maverick_spend_pct=maverick_spend_pct,
        avg_po_lead_time_days=avg_po_lead_time_days,
        on_time_delivery_pct=on_time_delivery_pct,
    )


@router.get(
    "/spend-analysis",
    response_model=SpendAnalysisOut,
    summary="Análisis de spend por vendor y producto (top 10)",
    operation_id="procurementSpendAnalysis",
)
async def spend_analysis(
    _user: Annotated[User, Depends(require_permissions("purchases:write"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    period: str = Query(default="30d", pattern="^(30d|90d|365d)$"),
) -> SpendAnalysisOut:
    period_days_map = {"30d": 30, "90d": 90, "365d": 365}
    days = period_days_map[period]
    since = datetime.now(tz=timezone.utc) - timedelta(days=days)

    # Spend by vendor — desde VendorInvoices aprobadas/pagadas en el período
    vendor_result = await session.execute(
        select(VendorInvoice.vendor_id, func.sum(VendorInvoice.total_amount).label("total"))
        .where(
            VendorInvoice.status.in_(("matched", "tolerance_ok", "approved", "paid")),
            VendorInvoice.created_at >= since,
        )
        .group_by(VendorInvoice.vendor_id)
        .order_by(func.sum(VendorInvoice.total_amount).desc())
        .limit(10)
    )
    by_vendor = [
        SpendByVendor(vendor_id=row.vendor_id, total_amount=row.total or Decimal("0"))
        for row in vendor_result
    ]

    # Spend by product — desde PO lines en POs confirmadas en el período
    product_result = await session.execute(
        select(
            PurchaseOrderLine.sku.label("product_sku"),
            func.sum(PurchaseOrderLine.qty_ordered * PurchaseOrderLine.unit_price).label("total"),
        )
        .join(PurchaseOrder, PurchaseOrderLine.po_id == PurchaseOrder.id)
        .where(
            PurchaseOrder.status.in_(("confirmed", "partial", "received")),
            PurchaseOrder.confirmed_at >= since,
        )
        .group_by(PurchaseOrderLine.sku)
        .order_by(func.sum(PurchaseOrderLine.qty_ordered * PurchaseOrderLine.unit_price).desc())
        .limit(10)
    )
    by_product = [
        SpendByProduct(product_sku=row.product_sku, total_amount=row.total or Decimal("0"))
        for row in product_result
    ]

    return SpendAnalysisOut(period_days=days, by_vendor=by_vendor, by_product=by_product)

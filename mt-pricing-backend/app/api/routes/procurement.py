"""Procurement API v1 — EP-ERP-03 (US-ERP-03-01/02/03).

Endpoints:
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

- GET    /procurement/vendor-conditions          — PIRs vigentes (filtros vendor_id, product_id)
- POST   /procurement/vendor-conditions          — crear PIR
- PUT    /procurement/vendor-conditions/{id}     — actualizar PIR
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, get_current_user, require_permissions, require_role
from app.db.models.user import User
from app.repositories.procurement import ProcurementRepository
from app.schemas.common import ProblemDetails
from app.schemas.procurement import (
    ApprovalDecisionOut,
    ApprovalRuleCreate,
    ApprovalRuleOut,
    ApprovalRuleUpdate,
    PRCreate,
    PROut,
    PRReject,
    VendorConditionCreate,
    VendorConditionOut,
    VendorConditionUpdate,
)

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
    product_id: UUID | None = Query(default=None),
    active_only: bool = Query(default=True),
) -> list[VendorConditionOut]:
    repo = ProcurementRepository(session)
    vcs = await repo.list_vendor_conditions(
        vendor_id=vendor_id,
        product_id=product_id,
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

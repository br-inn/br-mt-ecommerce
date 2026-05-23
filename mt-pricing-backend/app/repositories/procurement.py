"""ProcurementRepository — EP-ERP-03 (US-ERP-03-01/02/03)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.procurement import (
    ApprovalDecision,
    ApprovalRule,
    PurchaseRequisition,
    VendorProductCondition,
)
from app.schemas.procurement import (
    PRCreate,
    VendorConditionCreate,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _next_pr_number(session: AsyncSession) -> str:
    """Genera PR-YYYYMMDD-NNNN incremental por día."""
    from datetime import date

    today = date.today().strftime("%Y%m%d")
    prefix = f"PR-{today}-"
    stmt = select(func.count()).where(PurchaseRequisition.pr_number.like(f"{prefix}%"))
    count = int((await session.execute(stmt)).scalar_one() or 0)
    return f"{prefix}{count + 1:04d}"


def _active_pir_clause(vendor_id: str, product_sku: str) -> Any:
    from datetime import date

    today = date.today()
    return and_(
        VendorProductCondition.vendor_id == vendor_id,
        VendorProductCondition.product_sku == product_sku,
        VendorProductCondition.is_active.is_(True),
        VendorProductCondition.valid_from <= today,
        or_(
            VendorProductCondition.valid_to.is_(None),
            VendorProductCondition.valid_to >= today,
        ),
    )


# ---------------------------------------------------------------------------
# PurchaseRequisition
# ---------------------------------------------------------------------------


class ProcurementRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # --- PR CRUD ------------------------------------------------------------

    async def create_pr(self, data: PRCreate, *, requester_id: UUID) -> PurchaseRequisition:
        pr_number = await _next_pr_number(self.session)
        pr = PurchaseRequisition(
            pr_number=pr_number,
            requester_id=requester_id,
            product_sku=data.product_sku,
            qty=data.qty,
            uom=data.uom,
            required_date=data.required_date,
            cost_center_id=data.cost_center_id,
            suggested_vendor_id=data.suggested_vendor_id,
            estimated_amount=data.estimated_amount,
            notes=data.notes,
            status="draft",
        )
        self.session.add(pr)
        await self.session.flush()
        return pr

    async def get_pr(self, pr_id: UUID) -> PurchaseRequisition | None:
        stmt = select(PurchaseRequisition).where(PurchaseRequisition.id == pr_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_prs(
        self,
        *,
        requester_id: UUID | None = None,
        status: str | None = None,
        limit: int = 50,
        cursor: UUID | None = None,
    ) -> tuple[list[PurchaseRequisition], UUID | None]:
        stmt = select(PurchaseRequisition)

        clauses: list[Any] = []
        if requester_id:
            clauses.append(PurchaseRequisition.requester_id == requester_id)
        if status:
            clauses.append(PurchaseRequisition.status == status)
        if clauses:
            stmt = stmt.where(and_(*clauses))
        if cursor:
            stmt = stmt.where(PurchaseRequisition.id > cursor)

        stmt = stmt.order_by(PurchaseRequisition.id.asc()).limit(limit + 1)
        rows = list((await self.session.execute(stmt)).scalars().all())

        next_cursor: UUID | None = None
        if len(rows) > limit:
            next_cursor = rows[limit - 1].id
            rows = rows[:limit]

        return rows, next_cursor

    # --- Lifecycle ----------------------------------------------------------

    async def submit_pr(self, pr_id: UUID) -> PurchaseRequisition:
        pr = await self._get_or_404(pr_id)
        if pr.status != "draft":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "pr_not_draft",
                    "title": f"Solo se pueden enviar PRs en estado 'draft' (actual: {pr.status})",
                },
            )
        rule = await self._match_approval_rule(pr)
        if rule is None or rule.timeout_hours == 0:
            pr.status = "approved"
            decision = ApprovalDecision(
                document_id=pr.id,
                document_type="purchase_requisition",
                approver_id=pr.requester_id,
                action="APPROVE",
                reason="Auto-aprobado por regla (importe <= umbral mínimo o sin regla)",
            )
            self.session.add(decision)
        else:
            pr.status = "pending_approval"
            role_info = rule.approver_role or f"usuario:{rule.approver_user_id}"
            pr.notes = (
                f"{pr.notes or ''}\n[Regla activada: prioridad {rule.priority}, "
                f"aprobador: {role_info}, timeout: {rule.timeout_hours}h]"
            ).strip()

        pr.updated_at = datetime.now(tz=UTC)
        await self.session.flush()
        return pr

    async def approve_pr(self, pr_id: UUID, *, approver_id: UUID) -> PurchaseRequisition:
        pr = await self._get_or_404(pr_id)
        if pr.status != "pending_approval":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "pr_not_pending",
                    "title": f"Solo se pueden aprobar PRs en 'pending_approval' (actual: {pr.status})",
                },
            )
        decision = ApprovalDecision(
            document_id=pr.id,
            document_type="purchase_requisition",
            approver_id=approver_id,
            action="APPROVE",
        )
        self.session.add(decision)
        pr.status = "approved"
        pr.updated_at = datetime.now(tz=UTC)
        await self.session.flush()
        return pr

    async def reject_pr(
        self, pr_id: UUID, *, approver_id: UUID, reason: str
    ) -> PurchaseRequisition:
        pr = await self._get_or_404(pr_id)
        if pr.status not in ("pending_approval",):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "pr_not_rejectable",
                    "title": f"No se puede rechazar PR en estado '{pr.status}'",
                },
            )
        decision = ApprovalDecision(
            document_id=pr.id,
            document_type="purchase_requisition",
            approver_id=approver_id,
            action="REJECT",
            reason=reason,
        )
        self.session.add(decision)
        pr.status = "rejected"
        pr.updated_at = datetime.now(tz=UTC)
        await self.session.flush()
        return pr

    async def cancel_pr(self, pr_id: UUID) -> PurchaseRequisition:
        pr = await self._get_or_404(pr_id)
        if pr.status == "converted_to_po":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "pr_already_converted",
                    "title": "No se puede cancelar una PR ya convertida a PO",
                },
            )
        pr.status = "cancelled"
        pr.updated_at = datetime.now(tz=UTC)
        await self.session.flush()
        return pr

    # --- Approval rules -----------------------------------------------------

    async def _match_approval_rule(self, pr: PurchaseRequisition) -> ApprovalRule | None:
        amount = pr.estimated_amount or Decimal("0")
        stmt = (
            select(ApprovalRule)
            .where(
                ApprovalRule.document_type == "purchase_requisition",
                ApprovalRule.is_active.is_(True),
                ApprovalRule.min_amount <= amount,
                or_(
                    ApprovalRule.max_amount.is_(None),
                    ApprovalRule.max_amount > amount,
                ),
            )
            .order_by(ApprovalRule.priority.asc())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_approval_rules(self) -> list[ApprovalRule]:
        stmt = select(ApprovalRule).order_by(ApprovalRule.priority.asc())
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_approval_rule(self, rule_id: UUID) -> ApprovalRule | None:
        stmt = select(ApprovalRule).where(ApprovalRule.id == rule_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def create_approval_rule(self, data: dict[str, Any]) -> ApprovalRule:
        rule = ApprovalRule(**data)
        self.session.add(rule)
        await self.session.flush()
        return rule

    async def update_approval_rule(self, rule_id: UUID, payload: dict[str, Any]) -> ApprovalRule:
        rule = await self.get_approval_rule(rule_id)
        if rule is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "rule_not_found", "title": "Regla de aprobación no existe"},
            )
        for k, v in payload.items():
            setattr(rule, k, v)
        await self.session.flush()
        return rule

    async def delete_approval_rule(self, rule_id: UUID) -> None:
        rule = await self.get_approval_rule(rule_id)
        if rule is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "rule_not_found", "title": "Regla de aprobación no existe"},
            )
        await self.session.delete(rule)
        await self.session.flush()

    async def get_pr_decisions(self, pr_id: UUID) -> list[ApprovalDecision]:
        stmt = (
            select(ApprovalDecision)
            .where(
                ApprovalDecision.document_id == pr_id,
                ApprovalDecision.document_type == "purchase_requisition",
            )
            .order_by(ApprovalDecision.decided_at.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    # --- Vendor conditions (PIR) --------------------------------------------

    async def list_vendor_conditions(
        self,
        *,
        vendor_id: str | None = None,
        product_sku: str | None = None,
        active_only: bool = True,
    ) -> list[VendorProductCondition]:
        stmt = select(VendorProductCondition)
        clauses: list[Any] = []
        if vendor_id:
            clauses.append(VendorProductCondition.vendor_id == vendor_id)
        if product_sku:
            clauses.append(VendorProductCondition.product_sku == product_sku)
        if active_only:
            from datetime import date as _date

            today = _date.today()
            clauses.append(VendorProductCondition.is_active.is_(True))
            clauses.append(VendorProductCondition.valid_from <= today)
            clauses.append(
                or_(
                    VendorProductCondition.valid_to.is_(None),
                    VendorProductCondition.valid_to >= today,
                )
            )
        if clauses:
            stmt = stmt.where(and_(*clauses))
        stmt = stmt.order_by(VendorProductCondition.valid_from.desc())
        return list((await self.session.execute(stmt)).scalars().all())

    async def create_vendor_condition(self, data: VendorConditionCreate) -> VendorProductCondition:
        from datetime import date as _date

        vc = VendorProductCondition(
            vendor_id=data.vendor_id,
            product_sku=data.product_sku,
            price=data.price,
            uom=data.uom,
            moq=data.moq,
            lead_time_days=data.lead_time_days,
            valid_from=data.valid_from or _date.today(),
            valid_to=data.valid_to,
            currency=data.currency,
            is_active=data.is_active,
        )
        self.session.add(vc)
        await self.session.flush()
        return vc

    async def update_vendor_condition(
        self, vc_id: UUID, payload: dict[str, Any]
    ) -> VendorProductCondition:
        stmt = select(VendorProductCondition).where(VendorProductCondition.id == vc_id)
        vc = (await self.session.execute(stmt)).scalar_one_or_none()
        if vc is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "vc_not_found", "title": "Condición de proveedor no existe"},
            )
        for k, v in payload.items():
            setattr(vc, k, v)
        await self.session.flush()
        return vc

    async def get_active_pir(
        self, vendor_id: str, product_sku: str
    ) -> VendorProductCondition | None:
        """Devuelve el PIR vigente más reciente para vendor+product."""
        stmt = (
            select(VendorProductCondition)
            .where(_active_pir_clause(vendor_id, product_sku))
            .order_by(VendorProductCondition.valid_from.desc())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    # --- Internal helpers ---------------------------------------------------

    async def _get_or_404(self, pr_id: UUID) -> PurchaseRequisition:
        pr = await self.get_pr(pr_id)
        if pr is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "pr_not_found", "title": "Purchase Requisition no existe"},
            )
        return pr

    async def convert_pr_to_po(
        self, pr_id: UUID, created_by: UUID | None = None
    ) -> PurchaseOrder:
        import datetime as _dt

        from app.db.models.inventory import PurchaseOrder

        pr = await self._get_or_404(pr_id)
        if pr.status != "approved":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "pr_not_approved",
                    "title": f"Solo se pueden convertir PR aprobadas (actual: {pr.status})",
                },
            )

        po_number = f"PO-{_dt.date.today().strftime('%Y%m%d')}-{pr_id.hex[:6].upper()}"
        notes = f"Generado desde PR {pr.pr_number}"
        if pr.product_sku:
            notes += f" — SKU: {pr.product_sku}, Qty: {pr.qty} {pr.uom}"
        po = PurchaseOrder(
            po_number=po_number,
            status="draft",
            currency="AED",
            created_by=created_by,
            notes=notes,
        )
        self.session.add(po)
        await self.session.flush()

        pr.status = "converted_to_po"
        pr.updated_at = datetime.now(tz=_dt.UTC)
        await self.session.flush()
        await self.session.refresh(po)
        return po

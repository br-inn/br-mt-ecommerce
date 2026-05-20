"""EP-ERP-06 — Finanzas: API routes.

Prefix: /api/v1/finance

Endpoints por story:
  US-ERP-06-01: GET/POST /accounts, PATCH /accounts/{id}
                GET/POST /posting-periods, POST /posting-periods/{id}/close
  US-ERP-06-02: GET/POST /cost-centers, GET/POST /profit-centers
  US-ERP-06-03: POST /entries, GET /entries, POST /entries/{id}/reverse
  US-ERP-06-04: GET /ap-aging, POST /payment-runs,
                POST /payment-runs/{id}/approve, POST /payment-runs/{id}/execute
  US-ERP-06-05: GET/POST /standard-costs, GET /price-variances
  US-ERP-06-06: GET /pl, GET /balance-sheet, GET /trial-balance
  US-ERP-06-07: POST /period-close/{fy}/{period},
                PATCH /period-close/{id}/item, POST /period-close/{id}/close
                POST /cit-provision/{fiscal_year}
  US-ERP-06-08: POST /fx-revaluation/{fy}/{period}
                POST /entries/{id}/review, POST /entries/{id}/approve
  US-ERP-06-09: GET /copa, GET/POST /budgets, GET /budget-vs-actual, GET /cash-flow
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, text, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    _user_permission_codes,
    get_current_user,
    get_db_session,
    require_permissions,
    require_role,
)
from app.db.models.finance import (
    Budget,
    CostCenter,
    FinancialEntry,
    GlAccount,
    JournalEntryControl,
    PaymentRun,
    PaymentRunItem,
    PeriodCloseChecklist,
    PostingPeriod,
    PriceVariance,
    ProfitCenter,
    StandardCost,
    TaxProvision,
    VendorOpenItem,
)
from app.db.models.pricing import FXRate
from app.db.models.user import User
from app.schemas.finance import (
    ApAgingOut,
    ApAgingBucket,
    BalanceSheetLineOut,
    BalanceSheetOut,
    BudgetCreate,
    BudgetOut,
    BudgetVsActualLine,
    BudgetVsActualOut,
    CashFlowOut,
    ChecklistItemUpdate,
    CitProvisionResult,
    CopaLineOut,
    CopaOut,
    CostCenterCreate,
    CostCenterOut,
    EntryReviewApproveOut,
    FinancialEntryCreate,
    FinancialEntryOut,
    FxRevalResult,
    GlAccountCreate,
    GlAccountOut,
    GlAccountUpdate,
    JournalEntryControlOut,
    PaymentRunCreate,
    PaymentRunOut,
    PeriodCloseChecklistOut,
    PlLineOut,
    PlSummaryOut,
    PostingPeriodCreate,
    PostingPeriodOut,
    PriceVarianceOut,
    ProfitCenterCreate,
    ProfitCenterOut,
    StandardCostCreate,
    StandardCostOut,
    TaxProvisionOut,
    TrialBalanceLineOut,
    TrialBalanceOut,
)

log = logging.getLogger(__name__)

router = APIRouter(
    prefix="/finance",
    tags=["finance"],
    dependencies=[Depends(require_role("admin", "gerente"))],
)

DbSession = Annotated[AsyncSession, Depends(get_db_session)]
CurrentUser = Annotated[User, Depends(get_current_user)]


# ===========================================================================
# US-ERP-06-01 — Chart of Accounts
# ===========================================================================

@router.get("/accounts", response_model=list[GlAccountOut])
async def list_accounts(
    db: DbSession,
    current_user: CurrentUser,
    account_type: str | None = Query(None),
    blocked: bool | None = Query(None),
) -> list[GlAccountOut]:
    """GET /finance/accounts — listado de cuentas contables."""
    q = select(GlAccount)
    if account_type:
        q = q.where(GlAccount.account_type == account_type)
    if blocked is not None:
        q = q.where(GlAccount.is_blocked == blocked)
    q = q.order_by(GlAccount.account_code)
    result = await db.execute(q)
    return [GlAccountOut.model_validate(r) for r in result.scalars().all()]


@router.post("/accounts", response_model=GlAccountOut, status_code=status.HTTP_201_CREATED)
async def create_account(
    body: GlAccountCreate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_role("ti", "gerente"))],
) -> GlAccountOut:
    """POST /finance/accounts — crear cuenta contable."""
    existing = await db.execute(
        select(GlAccount).where(GlAccount.account_code == body.account_code)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"account_code {body.account_code!r} ya existe")
    account = GlAccount(**body.model_dump())
    db.add(account)
    await db.flush()
    await db.refresh(account)
    return GlAccountOut.model_validate(account)


@router.patch("/accounts/{account_id}", response_model=GlAccountOut)
async def update_account(
    account_id: UUID,
    body: GlAccountUpdate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_role("ti", "gerente"))],
) -> GlAccountOut:
    """PATCH /finance/accounts/{id} — actualizar cuenta."""
    result = await db.execute(select(GlAccount).where(GlAccount.id == account_id))
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(account, field, value)
    await db.flush()
    await db.refresh(account)
    return GlAccountOut.model_validate(account)


# ---------------------------------------------------------------------------
# US-ERP-06-01 — Posting Periods
# ---------------------------------------------------------------------------

@router.get("/posting-periods", response_model=list[PostingPeriodOut])
async def list_posting_periods(
    db: DbSession,
    current_user: CurrentUser,
    fiscal_year: int | None = Query(None),
    status: str | None = Query(None),
) -> list[PostingPeriodOut]:
    q = select(PostingPeriod)
    if fiscal_year:
        q = q.where(PostingPeriod.fiscal_year == fiscal_year)
    if status:
        q = q.where(PostingPeriod.status == status)
    q = q.order_by(PostingPeriod.fiscal_year, PostingPeriod.period_num)
    result = await db.execute(q)
    return [PostingPeriodOut.model_validate(r) for r in result.scalars().all()]


@router.post("/posting-periods", response_model=PostingPeriodOut, status_code=status.HTTP_201_CREATED)
async def create_posting_period(
    body: PostingPeriodCreate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_role("ti", "gerente"))],
) -> PostingPeriodOut:
    period = PostingPeriod(**body.model_dump())
    db.add(period)
    await db.flush()
    await db.refresh(period)
    return PostingPeriodOut.model_validate(period)


@router.post("/posting-periods/{period_id}/close", response_model=PostingPeriodOut)
async def close_posting_period(
    period_id: UUID,
    db: DbSession,
    current_user: Annotated[User, Depends(require_role("gerente"))],
) -> PostingPeriodOut:
    result = await db.execute(select(PostingPeriod).where(PostingPeriod.id == period_id))
    period = result.scalar_one_or_none()
    if not period:
        raise HTTPException(status_code=404, detail="Período no encontrado")
    if period.status == "locked":
        raise HTTPException(status_code=409, detail="El período ya está bloqueado")
    period.status = "closed"
    period.closed_at = datetime.now(timezone.utc)
    period.closed_by = current_user.id
    await db.flush()
    await db.refresh(period)
    return PostingPeriodOut.model_validate(period)


# ===========================================================================
# US-ERP-06-02 — Cost Centers + Profit Centers
# ===========================================================================

@router.get("/cost-centers", response_model=list[CostCenterOut])
async def list_cost_centers(db: DbSession, current_user: CurrentUser) -> list[CostCenterOut]:
    result = await db.execute(select(CostCenter).order_by(CostCenter.cc_code))
    return [CostCenterOut.model_validate(r) for r in result.scalars().all()]


@router.post("/cost-centers", response_model=CostCenterOut, status_code=status.HTTP_201_CREATED)
async def create_cost_center(
    body: CostCenterCreate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_role("ti", "gerente"))],
) -> CostCenterOut:
    cc = CostCenter(**body.model_dump())
    db.add(cc)
    await db.flush()
    await db.refresh(cc)
    return CostCenterOut.model_validate(cc)


@router.get("/profit-centers", response_model=list[ProfitCenterOut])
async def list_profit_centers(db: DbSession, current_user: CurrentUser) -> list[ProfitCenterOut]:
    result = await db.execute(select(ProfitCenter).order_by(ProfitCenter.pc_code))
    return [ProfitCenterOut.model_validate(r) for r in result.scalars().all()]


@router.post("/profit-centers", response_model=ProfitCenterOut, status_code=status.HTTP_201_CREATED)
async def create_profit_center(
    body: ProfitCenterCreate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_role("ti", "gerente"))],
) -> ProfitCenterOut:
    pc = ProfitCenter(**body.model_dump())
    db.add(pc)
    await db.flush()
    await db.refresh(pc)
    return ProfitCenterOut.model_validate(pc)


# ===========================================================================
# US-ERP-06-03 — Universal Journal
# ===========================================================================

@router.post("/entries", response_model=FinancialEntryOut, status_code=status.HTTP_201_CREATED)
async def create_financial_entry(
    body: FinancialEntryCreate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_role("gerente"))],
) -> FinancialEntryOut:
    """POST /finance/entries — crear asiento manual (requiere rol gerente).

    Validaciones previas al INSERT:
    - Si el período está CLOSED o LOCKED → 422.
    - Si el período está SOFT_CLOSED → solo usuarios con permiso `finance:admin`.
    """
    # Bug 1 fix: validate posting period status before creating entry
    period_result = await db.execute(
        select(PostingPeriod).where(
            PostingPeriod.fiscal_year == body.fiscal_year,
            PostingPeriod.period_num == body.posting_period,
        )
    )
    posting_period = period_result.scalar_one_or_none()
    if posting_period is not None:
        if posting_period.status in ("closed", "locked"):
            raise HTTPException(
                status_code=422,
                detail="Posting period is closed — entry rejected",
            )
        if posting_period.status == "soft_closed":
            # Only finance:admin users can post to a soft-closed period
            if "finance:admin" not in _user_permission_codes(current_user):
                raise HTTPException(
                    status_code=422,
                    detail="Posting period is soft-closed — requires finance:admin permission",
                )

    entry = FinancialEntry(**body.model_dump(), preparer_id=current_user.id)
    db.add(entry)
    await db.flush()
    await db.refresh(entry)
    return FinancialEntryOut.model_validate(entry)


@router.get("/entries", response_model=list[FinancialEntryOut])
async def list_financial_entries(
    db: DbSession,
    current_user: CurrentUser,
    gl_account: UUID | None = Query(None),
    period: int | None = Query(None),
    fiscal_year: int | None = Query(None),
    source_module: str | None = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
) -> list[FinancialEntryOut]:
    """GET /finance/entries — query con filtros."""
    q = select(FinancialEntry)
    if gl_account:
        q = q.where(FinancialEntry.gl_account_id == gl_account)
    if period:
        q = q.where(FinancialEntry.posting_period == period)
    if fiscal_year:
        q = q.where(FinancialEntry.fiscal_year == fiscal_year)
    if source_module:
        q = q.where(FinancialEntry.source_module == source_module)
    q = q.order_by(FinancialEntry.journal_date.desc()).limit(limit).offset(offset)
    result = await db.execute(q)
    return [FinancialEntryOut.model_validate(r) for r in result.scalars().all()]


@router.post("/entries/{entry_id}/reverse", response_model=FinancialEntryOut)
async def reverse_financial_entry(
    entry_id: UUID,
    db: DbSession,
    current_user: Annotated[User, Depends(require_role("gerente"))],
) -> FinancialEntryOut:
    """POST /finance/entries/{id}/reverse — crear asiento de reversión."""
    result = await db.execute(select(FinancialEntry).where(FinancialEntry.id == entry_id))
    original = result.scalar_one_or_none()
    if not original:
        raise HTTPException(status_code=404, detail="Asiento no encontrado")
    if original.is_reversed:
        raise HTTPException(status_code=409, detail="El asiento ya fue revertido")

    today = date.today()
    rev_number = f"REV-{original.entry_number}"
    reversal = FinancialEntry(
        entry_number=rev_number,
        journal_date=today,
        posting_period=original.posting_period,
        fiscal_year=original.fiscal_year,
        entry_type="REVERSAL",
        source_module=original.source_module,
        source_document=original.source_document,
        source_document_id=original.source_document_id,
        gl_account_id=original.gl_account_id,
        cost_center_id=original.cost_center_id,
        profit_center_id=original.profit_center_id,
        # debit/credit intercambiados
        debit_amount=original.credit_amount,
        credit_amount=original.debit_amount,
        currency_code=original.currency_code,
        amount_local=original.amount_local,
        fx_rate=original.fx_rate,
        description=f"Reversión de {original.entry_number}",
        reference=original.reference,
        preparer_id=current_user.id,
        reversal_entry_id=original.id,
    )
    original.is_reversed = True
    db.add(reversal)
    await db.flush()
    await db.refresh(reversal)
    return FinancialEntryOut.model_validate(reversal)


# ---------------------------------------------------------------------------
# US-ERP-06-08 — Review + Approve (SoD)
# ---------------------------------------------------------------------------

@router.post("/entries/{entry_id}/review", response_model=EntryReviewApproveOut)
async def review_financial_entry(
    entry_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> EntryReviewApproveOut:
    """POST /finance/entries/{id}/review — marcar como revisado (reviewer != preparer)."""
    result = await db.execute(select(FinancialEntry).where(FinancialEntry.id == entry_id))
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Asiento no encontrado")
    if entry.preparer_id == current_user.id:
        raise HTTPException(status_code=409, detail="SoD: reviewer no puede ser el mismo que preparer")
    entry.reviewer_id = current_user.id
    await db.flush()
    return EntryReviewApproveOut(
        entry_id=entry_id,
        action="reviewed",
        by_user=current_user.id,
        at=datetime.now(timezone.utc),
    )


@router.post("/entries/{entry_id}/approve", response_model=EntryReviewApproveOut)
async def approve_financial_entry(
    entry_id: UUID,
    db: DbSession,
    current_user: Annotated[User, Depends(require_role("gerente"))],
) -> EntryReviewApproveOut:
    """POST /finance/entries/{id}/approve — aprobar (approver != preparer, != reviewer)."""
    result = await db.execute(select(FinancialEntry).where(FinancialEntry.id == entry_id))
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Asiento no encontrado")
    if entry.preparer_id == current_user.id:
        raise HTTPException(status_code=409, detail="SoD: approver no puede ser el mismo que preparer")
    if entry.reviewer_id == current_user.id:
        raise HTTPException(status_code=409, detail="SoD: approver no puede ser el mismo que reviewer")
    entry.approver_id = current_user.id
    await db.flush()
    return EntryReviewApproveOut(
        entry_id=entry_id,
        action="approved",
        by_user=current_user.id,
        at=datetime.now(timezone.utc),
    )


# ===========================================================================
# US-ERP-06-04 — AP Aging + Payment Run
# ===========================================================================

@router.get("/ap-aging", response_model=ApAgingOut)
async def ap_aging(
    db: DbSession,
    current_user: CurrentUser,
    as_of_date: date = Query(default=None),
    vendor_id: str | None = Query(None),
) -> ApAgingOut:
    """GET /finance/ap-aging — AP aging por buckets current/1-30/31-60/61-90/90+."""
    ref_date = as_of_date or date.today()

    q = select(VendorOpenItem).where(
        VendorOpenItem.status.in_(["open", "partially_paid"])
    )
    if vendor_id:
        q = q.where(VendorOpenItem.vendor_id == vendor_id)
    result = await db.execute(q)
    items = result.scalars().all()

    buckets: dict[str, ApAgingBucket] = {}
    for item in items:
        vid = item.vendor_id
        if vid not in buckets:
            buckets[vid] = ApAgingBucket(vendor_id=vid)
        b = buckets[vid]
        if not item.due_date:
            b.current += item.amount
        else:
            days_overdue = (ref_date - item.due_date).days
            if days_overdue <= 0:
                b.current += item.amount
            elif days_overdue <= 30:
                b.days_1_30 += item.amount
            elif days_overdue <= 60:
                b.days_31_60 += item.amount
            elif days_overdue <= 90:
                b.days_61_90 += item.amount
            else:
                b.days_90_plus += item.amount
        b.total += item.amount

    return ApAgingOut(as_of_date=ref_date, buckets=list(buckets.values()))


@router.post("/payment-runs", response_model=PaymentRunOut, status_code=status.HTTP_201_CREATED)
async def create_payment_run(
    body: PaymentRunCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> PaymentRunOut:
    """POST /finance/payment-runs — proponer payment run con items vencidos."""
    cutoff = body.cutoff_date or body.run_date

    q = select(VendorOpenItem).where(
        VendorOpenItem.status == "open",
        VendorOpenItem.payment_block.is_(False),
        or_(VendorOpenItem.due_date.is_(None), VendorOpenItem.due_date <= cutoff),
    )
    if body.vendor_ids:
        q = q.where(VendorOpenItem.vendor_id.in_(body.vendor_ids))

    result = await db.execute(q)
    open_items = result.scalars().all()

    # Generar run_number
    run_number = f"PR-{body.run_date.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    total = sum(i.amount for i in open_items)

    run = PaymentRun(
        run_number=run_number,
        run_date=body.run_date,
        payment_method=body.payment_method,
        total_amount=total,
        currency=body.currency,
        status="proposed",
        created_by=current_user.id,
    )
    db.add(run)
    await db.flush()

    today = body.run_date
    for item in open_items:
        # Early payment discount: 2% if paying ≥10 days before due date
        discount = Decimal("0")
        if item.due_date and (item.due_date - today).days >= 10:
            discount = (item.amount * Decimal("0.02")).quantize(Decimal("0.01"))
        pri = PaymentRunItem(
            run_id=run.id,
            open_item_id=item.id,
            payment_amount=item.amount - discount,
            discount_taken=discount,
        )
        db.add(pri)

    await db.flush()
    await db.refresh(run)
    return PaymentRunOut.model_validate(run)


@router.post("/payment-runs/{run_id}/approve", response_model=PaymentRunOut)
async def approve_payment_run(
    run_id: UUID,
    db: DbSession,
    current_user: Annotated[User, Depends(require_role("gerente"))],
) -> PaymentRunOut:
    result = await db.execute(select(PaymentRun).where(PaymentRun.id == run_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Payment run no encontrado")
    if run.status != "proposed":
        raise HTTPException(status_code=409, detail=f"No se puede aprobar desde estado {run.status!r}")
    run.status = "approved"
    run.approved_by = current_user.id
    await db.flush()
    await db.refresh(run)
    return PaymentRunOut.model_validate(run)


@router.post("/payment-runs/{run_id}/execute", response_model=PaymentRunOut)
async def execute_payment_run(
    run_id: UUID,
    db: DbSession,
    current_user: Annotated[User, Depends(require_role("gerente"))],
) -> PaymentRunOut:
    """POST /finance/payment-runs/{id}/execute — ejecutar: marca items como paid + crea financial_entries."""
    result = await db.execute(
        select(PaymentRun).where(PaymentRun.id == run_id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Payment run no encontrado")
    if run.status != "approved":
        raise HTTPException(status_code=409, detail=f"Debe estar aprobado. Estado actual: {run.status!r}")

    # Cargar items
    items_result = await db.execute(
        select(PaymentRunItem).where(PaymentRunItem.run_id == run_id)
    )
    run_items = items_result.scalars().all()

    today = date.today()
    entry_seq = 1

    for pri in run_items:
        # Marcar open_item como paid
        oi_result = await db.execute(
            select(VendorOpenItem).where(VendorOpenItem.id == pri.open_item_id)
        )
        oi = oi_result.scalar_one_or_none()
        if oi:
            oi.status = "paid"

        # Obtener cuenta AP (2100)
        ap_acct_result = await db.execute(
            select(GlAccount).where(GlAccount.account_code == "2100")
        )
        ap_acct = ap_acct_result.scalar_one_or_none()
        if ap_acct:
            entry_number = f"PAY-{run.run_number}-{entry_seq:04d}"
            fe = FinancialEntry(
                entry_number=entry_number,
                journal_date=today,
                posting_period=today.month,
                fiscal_year=today.year,
                entry_type="SYSTEM",
                source_module="finance",
                source_document=run.run_number,
                source_document_id=run.id,
                gl_account_id=ap_acct.id,
                debit_amount=pri.payment_amount or Decimal("0"),
                credit_amount=Decimal("0"),
                currency_code=run.currency,
                description=f"Pago run {run.run_number}",
                preparer_id=current_user.id,
            )
            db.add(fe)
            entry_seq += 1

    run.status = "executed"
    await db.flush()
    await db.refresh(run)
    return PaymentRunOut.model_validate(run)


# ===========================================================================
# US-ERP-06-05 — Standard Cost + Variances
# ===========================================================================

@router.get("/standard-costs", response_model=list[StandardCostOut])
async def list_standard_costs(
    db: DbSession,
    current_user: CurrentUser,
    sku: str | None = Query(None),
    fiscal_year: int | None = Query(None),
) -> list[StandardCostOut]:
    q = select(StandardCost)
    if sku:
        q = q.where(StandardCost.product_sku == sku)
    if fiscal_year:
        q = q.where(StandardCost.fiscal_year == fiscal_year)
    q = q.order_by(StandardCost.product_sku, StandardCost.fiscal_year)
    result = await db.execute(q)
    return [StandardCostOut.model_validate(r) for r in result.scalars().all()]


@router.post("/standard-costs", response_model=StandardCostOut, status_code=status.HTTP_201_CREATED)
async def create_standard_cost(
    body: StandardCostCreate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_role("ti", "gerente"))],
) -> StandardCostOut:
    sc = StandardCost(**body.model_dump(), created_by=current_user.id)
    db.add(sc)
    await db.flush()
    await db.refresh(sc)
    return StandardCostOut.model_validate(sc)


@router.get("/price-variances", response_model=list[PriceVarianceOut])
async def list_price_variances(
    db: DbSession,
    current_user: CurrentUser,
    sku: str | None = Query(None),
    period: int | None = Query(None),
    fiscal_year: int | None = Query(None),
) -> list[PriceVarianceOut]:
    q = select(PriceVariance)
    if sku:
        q = q.where(PriceVariance.product_sku == sku)
    if period:
        q = q.where(PriceVariance.period == period)
    if fiscal_year:
        q = q.where(PriceVariance.fiscal_year == fiscal_year)
    q = q.order_by(PriceVariance.created_at.desc())
    result = await db.execute(q)
    return [PriceVarianceOut.model_validate(r) for r in result.scalars().all()]


# ===========================================================================
# US-ERP-06-06 — P&L + Balance Sheet + Trial Balance
# ===========================================================================

@router.get("/pl", response_model=PlSummaryOut)
async def get_pl(
    db: DbSession,
    current_user: CurrentUser,
    fiscal_year: int = Query(...),
    period_from: int = Query(1),
    period_to: int = Query(12),
) -> PlSummaryOut:
    """GET /finance/pl — P&L desde mv_pl_summary o query directa."""
    # Intentar desde vista materializada; fallback a query directa
    try:
        rows = await db.execute(text("""
            SELECT fiscal_year, posting_period, account_code, account_name,
                   account_type, total_debit, total_credit, net_amount
            FROM mv_pl_summary
            WHERE fiscal_year = :fy
              AND posting_period BETWEEN :p_from AND :p_to
              AND account_type IN ('REVENUE', 'EXPENSE')
            ORDER BY account_code
        """), {"fy": fiscal_year, "p_from": period_from, "p_to": period_to})
        data = rows.mappings().all()
    except Exception:
        # fallback directo
        rows = await db.execute(text("""
            SELECT fe.fiscal_year, fe.posting_period,
                   a.account_code, a.account_name, a.account_type,
                   SUM(fe.debit_amount) AS total_debit,
                   SUM(fe.credit_amount) AS total_credit,
                   SUM(fe.credit_amount - fe.debit_amount) AS net_amount
            FROM financial_entries fe
            JOIN gl_accounts a ON fe.gl_account_id = a.id
            WHERE fe.fiscal_year = :fy
              AND fe.posting_period BETWEEN :p_from AND :p_to
              AND a.account_type IN ('REVENUE', 'EXPENSE')
            GROUP BY fe.fiscal_year, fe.posting_period,
                     a.account_code, a.account_name, a.account_type
            ORDER BY a.account_code
        """), {"fy": fiscal_year, "p_from": period_from, "p_to": period_to})
        data = rows.mappings().all()

    lines = [
        PlLineOut(
            fiscal_year=r["fiscal_year"],
            posting_period=r["posting_period"],
            account_code=r["account_code"],
            account_name=r["account_name"],
            account_type=r["account_type"],
            total_debit=r["total_debit"] or Decimal("0"),
            total_credit=r["total_credit"] or Decimal("0"),
            net_amount=r["net_amount"] or Decimal("0"),
        )
        for r in data
    ]
    revenue_total = sum(l.net_amount for l in lines if l.account_type == "REVENUE")
    expense_total = sum(l.net_amount for l in lines if l.account_type == "EXPENSE")
    return PlSummaryOut(
        fiscal_year=fiscal_year,
        period_from=period_from,
        period_to=period_to,
        revenue_total=revenue_total,
        expense_total=expense_total,
        net_income=revenue_total - expense_total,
        lines=lines,
    )


@router.get("/balance-sheet", response_model=BalanceSheetOut)
async def get_balance_sheet(
    db: DbSession,
    current_user: CurrentUser,
    fiscal_year: int = Query(...),
    as_of_period: int = Query(12),
) -> BalanceSheetOut:
    """GET /finance/balance-sheet — ASSET/LIABILITY/EQUITY con saldo acumulado."""
    rows = await db.execute(text("""
        SELECT a.account_code, a.account_name, a.account_type,
               SUM(fe.debit_amount - fe.credit_amount) AS balance
        FROM financial_entries fe
        JOIN gl_accounts a ON fe.gl_account_id = a.id
        WHERE fe.fiscal_year = :fy
          AND fe.posting_period <= :period
          AND a.account_type IN ('ASSET', 'LIABILITY', 'EQUITY')
        GROUP BY a.account_code, a.account_name, a.account_type
        ORDER BY a.account_code
    """), {"fy": fiscal_year, "period": as_of_period})
    data = rows.mappings().all()

    lines = [
        BalanceSheetLineOut(
            account_code=r["account_code"],
            account_name=r["account_name"],
            account_type=r["account_type"],
            balance=r["balance"] or Decimal("0"),
        )
        for r in data
    ]
    total_assets = sum(l.balance for l in lines if l.account_type == "ASSET")
    total_liabilities = sum(l.balance for l in lines if l.account_type == "LIABILITY")
    total_equity = sum(l.balance for l in lines if l.account_type == "EQUITY")

    return BalanceSheetOut(
        as_of_period=as_of_period,
        fiscal_year=fiscal_year,
        total_assets=total_assets,
        total_liabilities=total_liabilities,
        total_equity=total_equity,
        lines=lines,
    )


@router.get("/trial-balance", response_model=TrialBalanceOut)
async def get_trial_balance(
    db: DbSession,
    current_user: CurrentUser,
    fiscal_year: int = Query(...),
    period: int = Query(...),
) -> TrialBalanceOut:
    """GET /finance/trial-balance — todos los saldos para reconciliación."""
    rows = await db.execute(text("""
        SELECT a.account_code, a.account_name, a.account_type,
               SUM(fe.debit_amount) AS total_debit,
               SUM(fe.credit_amount) AS total_credit,
               SUM(fe.debit_amount - fe.credit_amount) AS balance
        FROM financial_entries fe
        JOIN gl_accounts a ON fe.gl_account_id = a.id
        WHERE fe.fiscal_year = :fy AND fe.posting_period = :period
        GROUP BY a.account_code, a.account_name, a.account_type
        ORDER BY a.account_code
    """), {"fy": fiscal_year, "period": period})
    data = rows.mappings().all()

    lines = [
        TrialBalanceLineOut(
            account_code=r["account_code"],
            account_name=r["account_name"],
            account_type=r["account_type"],
            total_debit=r["total_debit"] or Decimal("0"),
            total_credit=r["total_credit"] or Decimal("0"),
            balance=r["balance"] or Decimal("0"),
        )
        for r in data
    ]
    total_d = sum(l.total_debit for l in lines)
    total_c = sum(l.total_credit for l in lines)
    return TrialBalanceOut(
        fiscal_year=fiscal_year,
        period=period,
        lines=lines,
        total_debit=total_d,
        total_credit=total_c,
    )


# ===========================================================================
# US-ERP-06-07 — Period Close + UAE CIT
# ===========================================================================

@router.post("/period-close/{fiscal_year}/{period_num}", response_model=PeriodCloseChecklistOut)
async def start_period_close(
    fiscal_year: int,
    period_num: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_role("gerente"))],
) -> PeriodCloseChecklistOut:
    """POST /finance/period-close/{fy}/{period} — iniciar cierre, crear checklist."""
    existing = await db.execute(
        select(PeriodCloseChecklist).where(
            PeriodCloseChecklist.fiscal_year == fiscal_year,
            PeriodCloseChecklist.period_num == period_num,
        )
    )
    checklist = existing.scalar_one_or_none()
    if checklist:
        raise HTTPException(status_code=409, detail="Checklist ya existe para este período")

    checklist = PeriodCloseChecklist(
        fiscal_year=fiscal_year,
        period_num=period_num,
        status="in_progress",
        started_at=datetime.now(timezone.utc),
    )
    db.add(checklist)
    await db.flush()
    await db.refresh(checklist)
    return PeriodCloseChecklistOut.model_validate(checklist)


@router.patch("/period-close/{checklist_id}/item", response_model=PeriodCloseChecklistOut)
async def update_checklist_item(
    checklist_id: UUID,
    body: ChecklistItemUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> PeriodCloseChecklistOut:
    """PATCH /finance/period-close/{id}/item — marcar ítem completado."""
    result = await db.execute(
        select(PeriodCloseChecklist).where(PeriodCloseChecklist.id == checklist_id)
    )
    checklist = result.scalar_one_or_none()
    if not checklist:
        raise HTTPException(status_code=404, detail="Checklist no encontrado")

    items: list = list(checklist.checklist_items) if checklist.checklist_items else []

    # Soporte para marcar por índice o por nombre
    if body.item_name:
        # Buscar por nombre (string) o actualizar objeto dict
        for i, item in enumerate(items):
            if (isinstance(item, str) and item == body.item_name) or \
               (isinstance(item, dict) and item.get("name") == body.item_name):
                if isinstance(item, str):
                    items[i] = {"name": item, "completed": body.completed}
                else:
                    items[i]["completed"] = body.completed
                break
    elif 0 <= body.item_index < len(items):
        item = items[body.item_index]
        if isinstance(item, str):
            items[body.item_index] = {"name": item, "completed": body.completed}
        elif isinstance(item, dict):
            items[body.item_index]["completed"] = body.completed

    checklist.checklist_items = items
    await db.flush()
    await db.refresh(checklist)
    return PeriodCloseChecklistOut.model_validate(checklist)


@router.post("/period-close/{checklist_id}/close", response_model=PeriodCloseChecklistOut)
async def close_period_checklist(
    checklist_id: UUID,
    db: DbSession,
    current_user: Annotated[User, Depends(require_role("gerente"))],
) -> PeriodCloseChecklistOut:
    """POST /finance/period-close/{id}/close — cerrar período (todos ítems OK + gerente)."""
    result = await db.execute(
        select(PeriodCloseChecklist).where(PeriodCloseChecklist.id == checklist_id)
    )
    checklist = result.scalar_one_or_none()
    if not checklist:
        raise HTTPException(status_code=404, detail="Checklist no encontrado")

    # Verificar todos los ítems completados
    items = checklist.checklist_items or []
    pending = []
    for item in items:
        if isinstance(item, str):
            pending.append(item)
        elif isinstance(item, dict) and not item.get("completed", False):
            pending.append(item.get("name", "?"))

    if pending:
        raise HTTPException(
            status_code=409,
            detail=f"Ítems pendientes: {', '.join(pending)}",
        )

    checklist.status = "closed"
    checklist.completed_at = datetime.now(timezone.utc)
    checklist.completed_by = current_user.id

    # Cerrar también el posting_period correspondiente
    pp_result = await db.execute(
        select(PostingPeriod).where(
            PostingPeriod.fiscal_year == checklist.fiscal_year,
            PostingPeriod.period_num == checklist.period_num,
        )
    )
    pp = pp_result.scalar_one_or_none()
    if pp and pp.status == "open":
        pp.status = "closed"
        pp.closed_at = datetime.now(timezone.utc)
        pp.closed_by = current_user.id

    await db.flush()
    await db.refresh(checklist)
    return PeriodCloseChecklistOut.model_validate(checklist)


@router.post("/cit-provision/{fiscal_year}", response_model=CitProvisionResult)
async def calculate_cit_provision(
    fiscal_year: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_role("gerente"))],
) -> CitProvisionResult:
    """POST /finance/cit-provision/{fy} — calcular CIT UAE 9% sobre utilidades > AED 375,000."""
    # Calcular utilidad neta desde financial_entries
    rows = await db.execute(text("""
        SELECT
            COALESCE(SUM(CASE WHEN a.account_type = 'REVENUE'
                         THEN fe.credit_amount - fe.debit_amount ELSE 0 END), 0) AS revenue,
            COALESCE(SUM(CASE WHEN a.account_type = 'EXPENSE'
                         THEN fe.debit_amount - fe.credit_amount ELSE 0 END), 0) AS expenses
        FROM financial_entries fe
        JOIN gl_accounts a ON fe.gl_account_id = a.id
        WHERE fe.fiscal_year = :fy
    """), {"fy": fiscal_year})
    row = rows.mappings().one_or_none()

    revenue = Decimal(str(row["revenue"])) if row else Decimal("0")
    expenses = Decimal(str(row["expenses"])) if row else Decimal("0")
    net_profit = revenue - expenses

    cit_exempt = Decimal("375000")
    cit_rate = Decimal("0.09")
    taxable_base = max(net_profit - cit_exempt, Decimal("0"))
    provision_amount = (taxable_base * cit_rate).quantize(Decimal("0.0001"))

    provision_id = None
    if provision_amount > 0:
        provision = TaxProvision(
            provision_type="CIT",
            fiscal_year=fiscal_year,
            period_num=12,
            taxable_base=taxable_base,
            tax_rate=cit_rate,
            provision_amount=provision_amount,
            status="draft",
        )
        db.add(provision)
        await db.flush()
        provision_id = provision.id

    return CitProvisionResult(
        fiscal_year=fiscal_year,
        taxable_base=taxable_base,
        tax_rate=cit_rate,
        cit_exempt_threshold=cit_exempt,
        provision_amount=provision_amount,
        provision_id=provision_id,
        message=f"CIT UAE FY{fiscal_year}: base={taxable_base} × 9% = {provision_amount} AED",
    )


# ===========================================================================
# US-ERP-06-08 — FX Revaluation
# ===========================================================================

@router.post("/fx-revaluation/{fiscal_year}/{period}", response_model=FxRevalResult)
async def run_fx_revaluation(
    fiscal_year: int,
    period: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_role("gerente"))],
) -> FxRevalResult:
    """POST /finance/fx-revaluation/{fy}/{period} — revaluar saldos en moneda extranjera."""
    # Obtener cuentas con currency != AED
    accts_result = await db.execute(
        select(GlAccount).where(GlAccount.currency != "AED", GlAccount.is_blocked.is_(False))
    )
    foreign_accounts = accts_result.scalars().all()

    # Obtener cuenta FX gain/loss (7100)
    fx_acct_result = await db.execute(
        select(GlAccount).where(GlAccount.account_code == "7100")
    )
    fx_acct = fx_acct_result.scalar_one_or_none()
    if not fx_acct:
        raise HTTPException(status_code=422, detail="Cuenta 7100 (FX gain/loss) no encontrada")

    today = date.today()
    entries_created = 0
    total_gain = Decimal("0")
    total_loss = Decimal("0")

    for acct in foreign_accounts:
        # Obtener saldo neto en moneda extranjera
        bal_result = await db.execute(text("""
            SELECT
                COALESCE(SUM(debit_amount - credit_amount), 0) AS balance_local,
                currency_code,
                COALESCE(AVG(fx_rate), 1) AS avg_rate
            FROM financial_entries
            WHERE gl_account_id = :acct_id
              AND fiscal_year = :fy
              AND posting_period <= :period
            GROUP BY currency_code
        """), {"acct_id": str(acct.id), "fy": fiscal_year, "period": period})
        bal = bal_result.mappings().one_or_none()

        if not bal or bal["balance_local"] == 0:
            continue

        currency = bal["currency_code"]
        if currency == "AED":
            continue

        # Obtener tasa de cierre del período
        rate_result = await db.execute(
            select(FXRate)
            .where(FXRate.from_currency == currency, FXRate.to_currency == "AED")
            .order_by(FXRate.effective_date.desc())
            .limit(1)
        )
        fx_rate_obj = rate_result.scalar_one_or_none()
        if not fx_rate_obj:
            continue

        rate_closing = Decimal(str(fx_rate_obj.rate))
        rate_original = Decimal(str(bal["avg_rate"]))
        balance_foreign = Decimal(str(bal["balance_local"])) / rate_original if rate_original else Decimal("0")
        fx_diff = balance_foreign * (rate_closing - rate_original)

        if fx_diff == 0:
            continue

        entry_number = f"FXREV-{fiscal_year}-P{period:02d}-{acct.account_code}-{uuid.uuid4().hex[:6].upper()}"
        if fx_diff > 0:
            # FX gain: credit en cuenta 7100
            fe = FinancialEntry(
                entry_number=entry_number,
                journal_date=today,
                posting_period=period,
                fiscal_year=fiscal_year,
                entry_type="FX_REVAL",
                source_module="fx",
                gl_account_id=fx_acct.id,
                debit_amount=Decimal("0"),
                credit_amount=abs(fx_diff),
                currency_code="AED",
                fx_rate=rate_closing,
                description=f"FX Reval {acct.account_code} {currency} → AED",
                preparer_id=current_user.id,
            )
            total_gain += abs(fx_diff)
        else:
            # FX loss: debit en cuenta 7100
            fe = FinancialEntry(
                entry_number=entry_number,
                journal_date=today,
                posting_period=period,
                fiscal_year=fiscal_year,
                entry_type="FX_REVAL",
                source_module="fx",
                gl_account_id=fx_acct.id,
                debit_amount=abs(fx_diff),
                credit_amount=Decimal("0"),
                currency_code="AED",
                fx_rate=rate_closing,
                description=f"FX Reval {acct.account_code} {currency} → AED",
                preparer_id=current_user.id,
            )
            total_loss += abs(fx_diff)

        db.add(fe)
        entries_created += 1

    await db.flush()
    return FxRevalResult(
        fiscal_year=fiscal_year,
        period=period,
        accounts_revalued=len(foreign_accounts),
        total_fx_gain=total_gain,
        total_fx_loss=total_loss,
        entries_created=entries_created,
    )


# ===========================================================================
# US-ERP-06-09 — CO-PA + Budgets + Cash Flow
# ===========================================================================

@router.get("/copa", response_model=CopaOut)
async def get_copa(
    db: DbSession,
    current_user: CurrentUser,
    fiscal_year: int = Query(...),
    profit_center: str | None = Query(None),
) -> CopaOut:
    """GET /finance/copa — Contribution Margin por profit center.

    Bug 4 fix (PERFORMANCE): Query now reads from the materialized view
    ``mv_copa_summary`` instead of running a live aggregation on every request.

    TODO (migration required — out of scope here): Create the materialized view:

        CREATE MATERIALIZED VIEW mv_copa_summary AS
        SELECT
            pc.pc_code,
            pc.pc_name,
            fe.fiscal_year,
            COALESCE(SUM(CASE WHEN LEFT(a.account_code, 1) = '4'
                         THEN fe.credit_amount - fe.debit_amount ELSE 0 END), 0) AS revenue,
            COALESCE(SUM(CASE WHEN a.account_code = '5100'
                         THEN fe.debit_amount - fe.credit_amount ELSE 0 END), 0) AS cogs,
            COALESCE(SUM(CASE WHEN LEFT(a.account_code, 1) = '6'
                         THEN fe.debit_amount - fe.credit_amount ELSE 0 END), 0) AS opex
        FROM financial_entries fe
        JOIN gl_accounts a ON fe.gl_account_id = a.id
        JOIN profit_centers pc ON fe.profit_center_id = pc.id
        GROUP BY pc.pc_code, pc.pc_name, fe.fiscal_year;

        CREATE UNIQUE INDEX mv_copa_summary_pk
            ON mv_copa_summary (fiscal_year, pc_code);

    The view is refreshed by the ``mt.finance.refresh_copa_mv`` Celery task
    (see workers/tasks/finance.py) which should be registered in job_definitions
    with a nightly schedule (same pattern as ``mt.finance.refresh_pl_mv``).
    """
    # Bug 4 fix: read from materialized view — O(1) lookup instead of full scan
    rows = await db.execute(
        text("""
            SELECT
                pc_code,
                pc_name,
                revenue,
                cogs,
                opex
            FROM mv_copa_summary
            WHERE fiscal_year = :fy
              AND (:pc IS NULL OR pc_code = :pc)
            ORDER BY pc_code
        """),
        {"fy": fiscal_year, "pc": profit_center},
    )
    data = rows.mappings().all()

    lines = []
    for r in data:
        rev = Decimal(str(r["revenue"]))
        cogs = Decimal(str(r["cogs"]))
        opex = Decimal(str(r["opex"]))
        gm = rev - cogs
        ebit = gm - opex
        gm_pct = (gm / rev * 100).quantize(Decimal("0.01")) if rev else None
        lines.append(CopaLineOut(
            profit_center_code=r["pc_code"],
            profit_center_name=r["pc_name"],
            revenue=rev,
            cogs=cogs,
            gross_margin=gm,
            gross_margin_pct=gm_pct,
            opex=opex,
            ebit=ebit,
        ))

    return CopaOut(fiscal_year=fiscal_year, profit_center=profit_center, lines=lines)


@router.get("/budgets", response_model=list[BudgetOut])
async def list_budgets(
    db: DbSession,
    current_user: CurrentUser,
    fiscal_year: int | None = Query(None),
    period_num: int | None = Query(None),
) -> list[BudgetOut]:
    q = select(Budget)
    if fiscal_year:
        q = q.where(Budget.fiscal_year == fiscal_year)
    if period_num:
        q = q.where(Budget.period_num == period_num)
    q = q.order_by(Budget.fiscal_year, Budget.period_num)
    result = await db.execute(q)
    return [BudgetOut.model_validate(r) for r in result.scalars().all()]


@router.post("/budgets", response_model=BudgetOut, status_code=status.HTTP_201_CREATED)
async def create_budget(
    body: BudgetCreate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_role("ti", "gerente"))],
) -> BudgetOut:
    budget = Budget(**body.model_dump())
    db.add(budget)
    await db.flush()
    await db.refresh(budget)
    return BudgetOut.model_validate(budget)


@router.get("/budget-vs-actual", response_model=BudgetVsActualOut)
async def get_budget_vs_actual(
    db: DbSession,
    current_user: CurrentUser,
    fiscal_year: int = Query(...),
    period: int = Query(...),
) -> BudgetVsActualOut:
    """GET /finance/budget-vs-actual — comparar budgets vs financial_entries."""
    rows = await db.execute(text("""
        SELECT
            a.account_code, a.account_name, a.account_type,
            pc.pc_code AS profit_center_code,
            COALESCE(b.budget_amount, 0) AS budget,
            COALESCE(
                SUM(CASE WHEN a.account_type IN ('EXPENSE','ASSET')
                    THEN fe.debit_amount - fe.credit_amount
                    ELSE fe.credit_amount - fe.debit_amount END
                ), 0
            ) AS actual
        FROM budgets b
        JOIN gl_accounts a ON b.gl_account_id = a.id
        LEFT JOIN profit_centers pc ON b.profit_center_id = pc.id
        LEFT JOIN financial_entries fe ON fe.gl_account_id = b.gl_account_id
            AND fe.fiscal_year = b.fiscal_year
            AND fe.posting_period = b.period_num
        WHERE b.fiscal_year = :fy AND b.period_num = :period
        GROUP BY a.account_code, a.account_name, a.account_type,
                 pc.pc_code, b.budget_amount
        ORDER BY a.account_code
    """), {"fy": fiscal_year, "period": period})
    data = rows.mappings().all()

    lines = []
    for r in data:
        budget = Decimal(str(r["budget"]))
        actual = Decimal(str(r["actual"]))
        variance = actual - budget
        variance_pct = (variance / budget * 100).quantize(Decimal("0.01")) if budget else None
        lines.append(BudgetVsActualLine(
            account_code=r["account_code"],
            account_name=r["account_name"],
            account_type=r["account_type"],
            profit_center_code=r["profit_center_code"],
            budget=budget,
            actual=actual,
            variance=variance,
            variance_pct=variance_pct,
        ))

    total_budget = sum(l.budget for l in lines)
    total_actual = sum(l.actual for l in lines)
    return BudgetVsActualOut(
        fiscal_year=fiscal_year,
        period=period,
        lines=lines,
        total_budget=total_budget,
        total_actual=total_actual,
        total_variance=total_actual - total_budget,
    )


@router.get("/cash-flow", response_model=CashFlowOut)
async def get_cash_flow(
    db: DbSession,
    current_user: CurrentUser,
    fiscal_year: int = Query(...),
    period_from: int = Query(1),
    period_to: int = Query(12),
) -> CashFlowOut:
    """GET /finance/cash-flow — flujo de caja Operating/Investing/Financing."""
    # Operating: cobros clientes (cuenta 1100 — AR) y pagos proveedores (cuenta 2100 — AP)
    rows = await db.execute(text("""
        SELECT
            COALESCE(SUM(CASE WHEN a.account_code = '1100'
                         THEN fe.credit_amount - fe.debit_amount ELSE 0 END), 0) AS ar_collections,
            COALESCE(SUM(CASE WHEN a.account_code = '2100'
                         THEN fe.debit_amount - fe.credit_amount ELSE 0 END), 0) AS ap_payments
        FROM financial_entries fe
        JOIN gl_accounts a ON fe.gl_account_id = a.id
        WHERE fe.fiscal_year = :fy
          AND fe.posting_period BETWEEN :p_from AND :p_to
    """), {"fy": fiscal_year, "p_from": period_from, "p_to": period_to})
    row = rows.mappings().one_or_none()

    inflows = Decimal(str(row["ar_collections"])) if row else Decimal("0")
    outflows = Decimal(str(row["ap_payments"])) if row else Decimal("0")
    net_operating = inflows - outflows
    net_change = net_operating  # investing + financing = 0 (stub)

    return CashFlowOut(
        fiscal_year=fiscal_year,
        period_from=period_from,
        period_to=period_to,
        operating_inflows=inflows,
        operating_outflows=outflows,
        net_operating=net_operating,
        net_change=net_change,
        closing_cash=net_change,  # opening_cash = 0 (stub)
    )

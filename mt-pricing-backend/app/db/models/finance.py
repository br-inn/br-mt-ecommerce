"""EP-ERP-06 — Finanzas: Chart of Accounts, Universal Journal, AP, Costing, Budgets.

Modelos ORM para las 9 stories de EP-ERP-06:
- US-ERP-06-01: GlAccount, PostingPeriod
- US-ERP-06-02: CostCenter, ProfitCenter
- US-ERP-06-03: FinancialEntry   (≠ JournalEntry que es inventario)
- US-ERP-06-04: VendorOpenItem, PaymentRun, PaymentRunItem
- US-ERP-06-05: StandardCost, PriceVariance
- US-ERP-06-06: (vista mv_pl_summary — sin ORM directo, queries crudas)
- US-ERP-06-07: PeriodCloseChecklist, TaxProvision
- US-ERP-06-08: JournalEntryControl
- US-ERP-06-09: Budget

CRÍTICO: products usa sku TEXT como PK. Nunca product_id UUID con ForeignKey("products.id").
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CHAR,
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as UUID_PG
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import UuidPkMixin


# ---------------------------------------------------------------------------
# US-ERP-06-01 — Chart of Accounts
# ---------------------------------------------------------------------------


class GlAccount(UuidPkMixin, Base):
    """General Ledger Account — Chart of Accounts."""

    __tablename__ = "gl_accounts"

    account_code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    account_name: Mapped[str] = mapped_column(Text, nullable=False)
    account_type: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # ASSET|LIABILITY|EQUITY|REVENUE|EXPENSE|CONTRA
    parent_id: Mapped[UUID | None] = mapped_column(
        UUID_PG(as_uuid=True),
        ForeignKey("gl_accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_reconciling: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )
    is_blocked: Mapped[bool] = mapped_column(Boolean, server_default=text("false"), nullable=False)
    # normal_balance — DEBIT para activos/gastos; CREDIT para pasivos/equity/revenue (mig 141)
    normal_balance: Mapped[str] = mapped_column(
        Text, server_default=text("'DEBIT'"), nullable=False
    )
    # is_active — columna explícita (no GENERATED ALWAYS); inicio true (mig 141)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), nullable=False)
    currency: Mapped[str] = mapped_column(CHAR(3), server_default="AED", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "account_type IN ('ASSET','LIABILITY','EQUITY','REVENUE','EXPENSE','CONTRA')",
            name="ck_gl_accounts_account_type",
        ),
        CheckConstraint(
            "normal_balance IN ('DEBIT', 'CREDIT')",
            name="ck_gl_accounts_normal_balance",
        ),
    )

    # relationships
    parent: Mapped[GlAccount | None] = relationship(
        "GlAccount", remote_side="GlAccount.id", foreign_keys=[parent_id]
    )
    children: Mapped[list[GlAccount]] = relationship(
        "GlAccount", back_populates="parent", foreign_keys=[parent_id]
    )
    financial_entries: Mapped[list[FinancialEntry]] = relationship(
        "FinancialEntry", back_populates="gl_account"
    )
    budgets: Mapped[list[Budget]] = relationship("Budget", back_populates="gl_account")

    def __repr__(self) -> str:
        return f"<GlAccount {self.account_code} {self.account_name}>"


# ---------------------------------------------------------------------------
# US-ERP-06-01 — Posting Periods
# ---------------------------------------------------------------------------


class PostingPeriod(UuidPkMixin, Base):
    """Fiscal posting period — controla apertura/cierre contable."""

    __tablename__ = "posting_periods"

    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_num: Mapped[int] = mapped_column(Integer, nullable=False)
    period_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    date_from: Mapped[date] = mapped_column(Date, nullable=False)
    date_to: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        Text, server_default="open", nullable=False
    )  # open|soft_closed|closed|locked
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_by: Mapped[UUID | None] = mapped_column(
        UUID_PG(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint("period_num BETWEEN 1 AND 16", name="ck_posting_periods_period_num"),
        CheckConstraint(
            "status IN ('open','soft_closed','closed','locked')", name="ck_posting_periods_status"
        ),
        UniqueConstraint("fiscal_year", "period_num", name="uq_posting_periods_fy_period"),
    )

    def __repr__(self) -> str:
        return f"<PostingPeriod {self.fiscal_year}/{self.period_num} {self.status}>"


# ---------------------------------------------------------------------------
# US-ERP-06-02 — Cost Centers
# ---------------------------------------------------------------------------


class CostCenter(UuidPkMixin, Base):
    """Cost Center — centro de costo para imputación contable."""

    __tablename__ = "cost_centers"

    cc_code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    cc_name: Mapped[str] = mapped_column(Text, nullable=False)
    parent_id: Mapped[UUID | None] = mapped_column(
        UUID_PG(as_uuid=True),
        ForeignKey("cost_centers.id", ondelete="SET NULL"),
        nullable=True,
    )
    cc_type: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # PRODUCTION|SERVICE|ADMIN|SALES|IT
    responsible_id: Mapped[UUID | None] = mapped_column(
        UUID_PG(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    valid_from: Mapped[date] = mapped_column(
        Date, server_default=text("CURRENT_DATE"), nullable=False
    )
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "cc_type IN ('PRODUCTION','SERVICE','ADMIN','SALES','IT')",
            name="ck_cost_centers_cc_type",
        ),
    )

    parent: Mapped[CostCenter | None] = relationship(
        "CostCenter", remote_side="CostCenter.id", foreign_keys=[parent_id]
    )
    children: Mapped[list[CostCenter]] = relationship(
        "CostCenter", back_populates="parent", foreign_keys=[parent_id]
    )
    financial_entries: Mapped[list[FinancialEntry]] = relationship(
        "FinancialEntry", back_populates="cost_center"
    )

    def __repr__(self) -> str:
        return f"<CostCenter {self.cc_code} {self.cc_name}>"


# ---------------------------------------------------------------------------
# US-ERP-06-02 — Profit Centers
# ---------------------------------------------------------------------------


class ProfitCenter(UuidPkMixin, Base):
    """Profit Center — unidad de negocio para análisis de rentabilidad."""

    __tablename__ = "profit_centers"

    pc_code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    pc_name: Mapped[str] = mapped_column(Text, nullable=False)
    business_area: Mapped[str] = mapped_column(Text, nullable=False)  # B2C|B2B|INTERNAL
    responsible_id: Mapped[UUID | None] = mapped_column(
        UUID_PG(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "business_area IN ('B2C','B2B','INTERNAL')",
            name="ck_profit_centers_business_area",
        ),
    )

    financial_entries: Mapped[list[FinancialEntry]] = relationship(
        "FinancialEntry", back_populates="profit_center"
    )
    budgets: Mapped[list[Budget]] = relationship("Budget", back_populates="profit_center")

    def __repr__(self) -> str:
        return f"<ProfitCenter {self.pc_code} {self.business_area}>"


# ---------------------------------------------------------------------------
# US-ERP-06-03 — Universal Journal (financial_entries)
# DIFERENTE de journal_entries (inventario/stock movements)
# ---------------------------------------------------------------------------


class FinancialEntry(UuidPkMixin, Base):
    """Universal Journal Entry — asiento contable del módulo finanzas.

    NOTA: Esta tabla es DIFERENTE de `journal_entries` (tabla de inventario
    creada en EP-ERP-02 para stock movements). No confundir.
    """

    __tablename__ = "financial_entries"

    entry_number: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    journal_date: Mapped[date] = mapped_column(Date, nullable=False)
    posting_period: Mapped[int] = mapped_column(Integer, nullable=False)
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    entry_type: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # MANUAL|SYSTEM|REVERSAL|ACCRUAL|FX_REVAL
    source_module: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_document: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_document_id: Mapped[UUID | None] = mapped_column(UUID_PG(as_uuid=True), nullable=True)
    gl_account_id: Mapped[UUID] = mapped_column(
        UUID_PG(as_uuid=True),
        ForeignKey("gl_accounts.id"),
        nullable=False,
    )
    cost_center_id: Mapped[UUID | None] = mapped_column(
        UUID_PG(as_uuid=True),
        ForeignKey("cost_centers.id", ondelete="SET NULL"),
        nullable=True,
    )
    profit_center_id: Mapped[UUID | None] = mapped_column(
        UUID_PG(as_uuid=True),
        ForeignKey("profit_centers.id", ondelete="SET NULL"),
        nullable=True,
    )
    debit_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), server_default="0", nullable=False
    )
    credit_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), server_default="0", nullable=False
    )
    currency_code: Mapped[str] = mapped_column(CHAR(3), server_default="AED", nullable=False)
    amount_local: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    fx_rate: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 6), server_default="1", nullable=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    preparer_id: Mapped[UUID | None] = mapped_column(
        UUID_PG(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewer_id: Mapped[UUID | None] = mapped_column(
        UUID_PG(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approver_id: Mapped[UUID | None] = mapped_column(
        UUID_PG(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    is_reversed: Mapped[bool] = mapped_column(Boolean, server_default=text("false"), nullable=False)
    reversal_entry_id: Mapped[UUID | None] = mapped_column(
        UUID_PG(as_uuid=True),
        ForeignKey("financial_entries.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "entry_type IN ('MANUAL','SYSTEM','REVERSAL','ACCRUAL','FX_REVAL')",
            name="ck_financial_entries_entry_type",
        ),
        CheckConstraint(
            "source_module IN ('billing','procurement','inventory','sales','finance','fx') OR source_module IS NULL",
            name="ck_financial_entries_source_module",
        ),
        CheckConstraint("debit_amount >= 0", name="ck_financial_entries_debit_pos"),
        CheckConstraint("credit_amount >= 0", name="ck_financial_entries_credit_pos"),
        CheckConstraint(
            "debit_amount > 0 OR credit_amount > 0", name="ck_financial_entries_nonzero"
        ),
        Index("ix_fe_period_fy", "posting_period", "fiscal_year"),
        Index("ix_fe_account_date", "gl_account_id", "journal_date"),
        Index("ix_fe_source", "source_module", "source_document_id"),
        Index("ix_fe_journal_date", "journal_date"),
    )

    gl_account: Mapped[GlAccount] = relationship("GlAccount", back_populates="financial_entries")
    cost_center: Mapped[CostCenter | None] = relationship(
        "CostCenter", back_populates="financial_entries"
    )
    profit_center: Mapped[ProfitCenter | None] = relationship(
        "ProfitCenter", back_populates="financial_entries"
    )

    def __repr__(self) -> str:
        return f"<FinancialEntry {self.entry_number} {self.entry_type}>"


# ---------------------------------------------------------------------------
# US-ERP-06-04 — AP Aging + Payment Run
# ---------------------------------------------------------------------------


class VendorOpenItem(UuidPkMixin, Base):
    """Open item de proveedor — AP subledger."""

    __tablename__ = "vendor_open_items"

    vendor_id: Mapped[str] = mapped_column(Text, nullable=False)
    po_id: Mapped[UUID | None] = mapped_column(
        UUID_PG(as_uuid=True),
        ForeignKey("purchase_orders.id", ondelete="SET NULL"),
        nullable=True,
    )
    invoice_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    document_type: Mapped[str] = mapped_column(
        Text, server_default="vendor_invoice", nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    currency: Mapped[str] = mapped_column(CHAR(3), server_default="AED", nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(Text, server_default="open", nullable=False)
    payment_block: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "document_type IN ('vendor_invoice','debit_memo','credit_note')",
            name="ck_vendor_open_items_doc_type",
        ),
        CheckConstraint(
            "status IN ('open','partially_paid','paid','blocked')",
            name="ck_vendor_open_items_status",
        ),
    )

    payment_run_items: Mapped[list[PaymentRunItem]] = relationship(
        "PaymentRunItem", back_populates="open_item"
    )

    def __repr__(self) -> str:
        return f"<VendorOpenItem {self.vendor_id} {self.amount} {self.status}>"


class PaymentRun(UuidPkMixin, Base):
    """Payment run — propuesta de pago a proveedores."""

    __tablename__ = "payment_runs"

    run_number: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    run_date: Mapped[date] = mapped_column(Date, nullable=False)
    payment_method: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    currency: Mapped[str] = mapped_column(CHAR(3), server_default="AED", nullable=False)
    status: Mapped[str] = mapped_column(Text, server_default="proposed", nullable=False)
    created_by: Mapped[UUID | None] = mapped_column(
        UUID_PG(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_by: Mapped[UUID | None] = mapped_column(
        UUID_PG(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "payment_method IN ('bank_transfer','check','wire') OR payment_method IS NULL",
            name="ck_payment_runs_method",
        ),
        CheckConstraint(
            "status IN ('proposed','approved','executed','cancelled')",
            name="ck_payment_runs_status",
        ),
    )

    items: Mapped[list[PaymentRunItem]] = relationship(
        "PaymentRunItem", back_populates="payment_run"
    )

    def __repr__(self) -> str:
        return f"<PaymentRun {self.run_number} {self.status}>"


class PaymentRunItem(UuidPkMixin, Base):
    """Línea de un payment run."""

    __tablename__ = "payment_run_items"

    run_id: Mapped[UUID] = mapped_column(
        UUID_PG(as_uuid=True),
        ForeignKey("payment_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    open_item_id: Mapped[UUID] = mapped_column(
        UUID_PG(as_uuid=True),
        ForeignKey("vendor_open_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    payment_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    discount_taken: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), server_default="0", nullable=False
    )

    payment_run: Mapped[PaymentRun] = relationship("PaymentRun", back_populates="items")
    open_item: Mapped[VendorOpenItem] = relationship(
        "VendorOpenItem", back_populates="payment_run_items"
    )


# ---------------------------------------------------------------------------
# US-ERP-06-05 — Standard Cost + Price Purchase Variance
# ---------------------------------------------------------------------------


class StandardCost(UuidPkMixin, Base):
    """Costo estándar por SKU y año fiscal."""

    __tablename__ = "standard_costs"

    product_sku: Mapped[str] = mapped_column(
        Text,
        ForeignKey("products.sku", ondelete="CASCADE"),
        nullable=False,
    )
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    standard_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    currency: Mapped[str] = mapped_column(CHAR(3), server_default="AED", nullable=False)
    cost_type: Mapped[str] = mapped_column(Text, server_default="standard", nullable=False)
    valid_from: Mapped[date] = mapped_column(
        Date, server_default=text("CURRENT_DATE"), nullable=False
    )
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_by: Mapped[UUID | None] = mapped_column(
        UUID_PG(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "cost_type IN ('standard','planned','actual')",
            name="ck_standard_costs_cost_type",
        ),
        UniqueConstraint(
            "product_sku", "fiscal_year", "cost_type", name="uq_standard_costs_sku_fy_type"
        ),
    )

    def __repr__(self) -> str:
        return f"<StandardCost {self.product_sku} FY{self.fiscal_year} {self.standard_cost}>"


class PriceVariance(UuidPkMixin, Base):
    """Varianza de precio de compra vs costo estándar."""

    __tablename__ = "price_variances"

    po_line_id: Mapped[UUID | None] = mapped_column(
        UUID_PG(as_uuid=True),
        ForeignKey("purchase_order_lines.id", ondelete="SET NULL"),
        nullable=True,
    )
    product_sku: Mapped[str] = mapped_column(
        Text,
        ForeignKey("products.sku", ondelete="CASCADE"),
        nullable=False,
    )
    standard_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    actual_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    variance_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        Computed("actual_cost - standard_cost", persisted=True),
    )
    variance_pct: Mapped[Decimal | None] = mapped_column(Numeric(7, 4), nullable=True)
    period: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fiscal_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )

    def __repr__(self) -> str:
        return f"<PriceVariance {self.product_sku} var={self.variance_amount}>"


# ---------------------------------------------------------------------------
# US-ERP-06-07 — Period Close Checklist + Tax Provisions
# ---------------------------------------------------------------------------


class PeriodCloseChecklist(UuidPkMixin, Base):
    """Checklist de cierre de período contable."""

    __tablename__ = "period_close_checklists"

    fiscal_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    period_num: Mapped[int | None] = mapped_column(Integer, nullable=True)
    checklist_items: Mapped[list[Any]] = mapped_column(
        JSONB,
        server_default=text(
            """'["Reconcile AR", "Reconcile AP", "Post accruals", "Run depreciation", """
            """"FX revaluation", "Close subledgers", "Review variances", "CIT provision", "Lock period"]'::jsonb"""
        ),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(Text, server_default="open", nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_by: Mapped[UUID | None] = mapped_column(
        UUID_PG(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('open','in_progress','closed')",
            name="ck_period_close_checklists_status",
        ),
        UniqueConstraint("fiscal_year", "period_num", name="uq_period_close_fy_period"),
    )

    def __repr__(self) -> str:
        return f"<PeriodCloseChecklist FY{self.fiscal_year}/P{self.period_num} {self.status}>"


class TaxProvision(UuidPkMixin, Base):
    """Provisión fiscal — VAT, CIT, WHT."""

    __tablename__ = "tax_provisions"

    provision_type: Mapped[str | None] = mapped_column(Text, nullable=True)  # VAT|CIT|WHT
    fiscal_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    period_num: Mapped[int | None] = mapped_column(Integer, nullable=True)
    taxable_base: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    tax_rate: Mapped[Decimal | None] = mapped_column(Numeric(7, 4), nullable=True)
    provision_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    status: Mapped[str] = mapped_column(Text, server_default="draft", nullable=False)
    gl_entry_id: Mapped[UUID | None] = mapped_column(UUID_PG(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "provision_type IN ('VAT','CIT','WHT') OR provision_type IS NULL",
            name="ck_tax_provisions_type",
        ),
        CheckConstraint(
            "status IN ('draft','posted','filed')",
            name="ck_tax_provisions_status",
        ),
    )

    def __repr__(self) -> str:
        return f"<TaxProvision {self.provision_type} FY{self.fiscal_year} {self.status}>"


# ---------------------------------------------------------------------------
# US-ERP-06-08 — Journal Entry SoD Controls
# ---------------------------------------------------------------------------


class JournalEntryControl(UuidPkMixin, Base):
    """Segregation of Duties control para asientos contables.

    Un usuario no puede ser PREPARER y APPROVER del mismo asiento.
    """

    __tablename__ = "journal_entry_controls"

    user_id: Mapped[UUID] = mapped_column(
        UUID_PG(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    control_type: Mapped[str] = mapped_column(Text, nullable=False)  # PREPARER|REVIEWER|APPROVER
    gl_account_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    effective_from: Mapped[date] = mapped_column(
        Date, server_default=text("CURRENT_DATE"), nullable=False
    )
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "control_type IN ('PREPARER','REVIEWER','APPROVER')",
            name="ck_je_controls_type",
        ),
    )

    def __repr__(self) -> str:
        return f"<JournalEntryControl {self.control_type} user={self.user_id}>"


# ---------------------------------------------------------------------------
# US-ERP-06-09 — Budgets
# ---------------------------------------------------------------------------


class Budget(UuidPkMixin, Base):
    """Presupuesto por período, cuenta contable y profit center."""

    __tablename__ = "budgets"

    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_num: Mapped[int] = mapped_column(Integer, nullable=False)
    gl_account_id: Mapped[UUID] = mapped_column(
        UUID_PG(as_uuid=True),
        ForeignKey("gl_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    profit_center_id: Mapped[UUID | None] = mapped_column(
        UUID_PG(as_uuid=True),
        ForeignKey("profit_centers.id", ondelete="SET NULL"),
        nullable=True,
    )
    budget_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    currency: Mapped[str] = mapped_column(CHAR(3), server_default="AED", nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "fiscal_year",
            "period_num",
            "gl_account_id",
            "profit_center_id",
            name="uq_budgets_fy_period_account_pc",
        ),
        Index("ix_budgets_fy_period", "fiscal_year", "period_num"),
    )

    gl_account: Mapped[GlAccount] = relationship("GlAccount", back_populates="budgets")
    profit_center: Mapped[ProfitCenter | None] = relationship(
        "ProfitCenter", back_populates="budgets"
    )

    def __repr__(self) -> str:
        return f"<Budget FY{self.fiscal_year}/P{self.period_num} {self.budget_amount}>"

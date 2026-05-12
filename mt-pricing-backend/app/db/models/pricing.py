"""Pricing domain models — fx_rates, costs, prices, exception_rules,
price_approval_events (Wave 2 — motor v5.1 ported).

Refs:
- ADR-006 (workflow excepción)
- ADR-010 (no aprobado no integra)
- ADR-045 (persistencia híbrida)
- ADR-046 (DatabaseScheduler)
- `_bmad-output/planning-artifacts/sprint0-v51-rules-extraction.md` (18 reglas + golden numbers)

NOTAS arquitectura:
- `Channel` se movió a `app.db.models.channels` (US-1B-03-01, mig 079).
  Se re-exporta aquí para backward-compat.
- `Scheme` (cost scheme) ya existía (`schemes` table, PK = code STRING).
  El modelo `Price.scheme_code` se referencia por `code` (no UUID) para coherencia
  con `costs.scheme_code` y la tabla previa.
- `Cost` y `Price` arrastran `breakdown` JSONB con todos los componentes (costes
  desglosados / margen breakdown) — clave para auditoría Juan Carlos.
- `PriceApprovalEvent` registra cada transición FSM con actor + razón.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.enums import PriceState, Scheme, values_csv
from app.db.mixins import AuditMixin, TimestampMixin, UuidPkMixin
from app.db.types import UUID_PG

# ---------------------------------------------------------------------------
# Channel — moved to app.db.models.channels (US-1B-03-01). Re-export here
# for backward-compat with any code that does `from app.db.models.pricing import Channel`.
# ---------------------------------------------------------------------------
from app.db.models.channels import Channel  # noqa: F401,E402


# ---------------------------------------------------------------------------
# FXRate — tabla as-of efectiva
# ---------------------------------------------------------------------------
class FXRate(UuidPkMixin, TimestampMixin, Base):
    """Tipo de cambio par-a-par con vigencia temporal.

    Lookup canónico: `WHERE from_currency = X AND to_currency = Y AND
    effective_from <= now AND (effective_to IS NULL OR effective_to > now)
    ORDER BY effective_from DESC LIMIT 1`.
    """

    __tablename__ = "fx_rates"

    from_currency: Mapped[str] = mapped_column(
        String(3), ForeignKey("currencies.code", ondelete="RESTRICT"), nullable=False
    )
    to_currency: Mapped[str] = mapped_column(
        String(3), ForeignKey("currencies.code", ondelete="RESTRICT"), nullable=False
    )
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # 'manual','cbuae','ecb','imported','identity' — CHECK enforced by mig 017.
    source: Mapped[str | None] = mapped_column(String(32))
    # `created_by` añadido en migración 20260507_017 (US-1A-05-03) — nullable
    # porque las filas seed (mig 010, identity row mig 017) no tienen actor.
    created_by: Mapped[UUID | None] = mapped_column(
        UUID_PG, ForeignKey("users.id", ondelete="SET NULL")
    )

    __table_args__ = (
        CheckConstraint("rate > 0", name="ck_fx_rate_positive"),
        Index("idx_fx_lookup", "from_currency", "to_currency", "effective_from"),
        Index(
            "idx_fx_active",
            "from_currency",
            "to_currency",
            postgresql_where=text("effective_to IS NULL"),
        ),
    )


# ---------------------------------------------------------------------------
# Cost — moved to `app.db.models.cost` (US-1A-04-02). Importer can `from
# app.db.models.pricing import Cost` if needed.
# ---------------------------------------------------------------------------
from app.db.models.cost import Cost  # noqa: F401,E402  # back-compat re-export


# ---------------------------------------------------------------------------
# Price — propuesta + state machine
# ---------------------------------------------------------------------------
class Price(UuidPkMixin, TimestampMixin, AuditMixin, Base):
    """Propuesta de precio para SKU × Channel × Scheme.

    Estados (state machine — ver `app.services.pricing.state_machine`):
        draft → auto_approved | pending_review | rejected
        auto_approved → approved | exported
        pending_review → approved | rejected | revised
        approved → exported | revised
        rejected → draft
        revised → pending_review | rejected
        exported (terminal)
    """

    __tablename__ = "prices"

    product_sku: Mapped[str] = mapped_column(
        Text, ForeignKey("products.sku", ondelete="CASCADE"), nullable=False, index=True
    )
    channel_id: Mapped[UUID] = mapped_column(
        UUID_PG, ForeignKey("channels.id", ondelete="RESTRICT"), nullable=False
    )
    scheme_code: Mapped[str] = mapped_column(
        String(32), ForeignKey("schemes.code", ondelete="RESTRICT"), nullable=False
    )

    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    pvp_min: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    margin_pct: Mapped[Decimal] = mapped_column(
        Numeric(7, 4), nullable=False, server_default=text("0")
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        ForeignKey("currencies.code", ondelete="RESTRICT"),
        nullable=False,
        server_default=text("'AED'"),
    )

    rule_applied: Mapped[str | None] = mapped_column(String(64))
    formula: Mapped[str | None] = mapped_column(Text)
    breakdown: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    alerts: Mapped[list[dict]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    fx_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'draft'"), index=True
    )
    proposed_by: Mapped[UUID | None] = mapped_column(
        UUID_PG, ForeignKey("users.id", ondelete="SET NULL")
    )
    approved_by: Mapped[UUID | None] = mapped_column(
        UUID_PG, ForeignKey("users.id", ondelete="SET NULL")
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejection_reason: Mapped[str | None] = mapped_column(Text)

    escalated: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    escalated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    valid_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("amount >= 0", name="ck_prices_amount_nonneg"),
        CheckConstraint(
            f"status IN {values_csv(PriceState)}",
            name="ck_prices_status",
        ),
        Index("idx_prices_lookup", "product_sku", "channel_id", "scheme_code"),
        Index(
            "idx_prices_pending",
            "status",
            postgresql_where=text("status IN ('pending_review','draft')"),
        ),
        Index(
            "idx_prices_active",
            "product_sku",
            "channel_id",
            "scheme_code",
            postgresql_where=text("valid_to IS NULL"),
        ),
    )


# ---------------------------------------------------------------------------
# ExceptionRule — thresholds para auto_approve vs pending_review
# ---------------------------------------------------------------------------
class ExceptionRule(UuidPkMixin, TimestampMixin, Base):
    """Regla de excepción evaluada por `ExceptionEvaluator`.

    Si hay channel_id/scheme_code, aplica solo a esa combinación; si NULL,
    aplica como default global.
    """

    __tablename__ = "exception_rules"

    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    channel_id: Mapped[UUID | None] = mapped_column(
        UUID_PG, ForeignKey("channels.id", ondelete="CASCADE")
    )
    scheme_code: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("schemes.code", ondelete="CASCADE")
    )
    margin_threshold_pct: Mapped[Decimal | None] = mapped_column(Numeric(7, 4))
    fx_swing_threshold_pct: Mapped[Decimal | None] = mapped_column(Numeric(7, 4))
    min_margin_pct: Mapped[Decimal | None] = mapped_column(Numeric(7, 4))
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    version: Mapped[int] = mapped_column(
        nullable=False, server_default=text("1")
    )
    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    effective_to: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by: Mapped[UUID | None] = mapped_column(
        UUID_PG, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "scheme_code IS NULL OR scheme_code IN "
            f"{values_csv(Scheme)}",
            name="ck_exception_rules_scheme_code",
        ),
        Index("idx_exception_rules_active", "active", postgresql_where=text("active = true")),
    )


# ---------------------------------------------------------------------------
# PriceApprovalEvent — historial FSM del Price
# ---------------------------------------------------------------------------
class PriceApprovalEvent(UuidPkMixin, TimestampMixin, Base):
    """Cada transición de estado del Price genera 1 evento."""

    __tablename__ = "price_approval_events"

    price_id: Mapped[UUID] = mapped_column(
        UUID_PG, ForeignKey("prices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    actor_id: Mapped[UUID] = mapped_column(
        UUID_PG, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    from_status: Mapped[str] = mapped_column(String(32), nullable=False)
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    metadata_jsonb: Mapped[dict] = mapped_column(
        "metadata",  # nombre real de columna; `metadata` está reservado en Base
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )

    __table_args__ = (
        CheckConstraint(
            f"from_status IN {values_csv(PriceState)}",
            name="ck_price_approval_events_from_status",
        ),
        CheckConstraint(
            f"to_status IN {values_csv(PriceState)}",
            name="ck_price_approval_events_to_status",
        ),
        Index("idx_price_approval_events_lookup", "price_id", "created_at"),
    )


__all__ = [
    "Channel",
    "FXRate",
    "Cost",
    "Price",
    "ExceptionRule",
    "PriceApprovalEvent",
]

"""PriceAlert — alerta de variación de precio detectada por price_monitor_task (US-SCR-04-05).

INSERT en esta tabla dispara pg_notify en canal ``price_alert`` via trigger DB.
El worker ``send_price_alert_emails`` consulta filas con ``notified_at IS NULL``
y envía emails via SendGrid.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import UUID_PG


class PriceAlert(Base):
    """Una fila = una alerta de precio disparada para (sku, marketplace)."""

    __tablename__ = "price_alerts"

    __table_args__ = (
        Index("ix_price_alerts_triggered_at", "triggered_at"),
        Index("ix_price_alerts_match_id", "match_id"),
    )

    id: Mapped[UUID] = mapped_column(
        UUID_PG,
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    match_id: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("match_candidates.id", ondelete="SET NULL"),
        nullable=True,
    )
    sku: Mapped[str | None] = mapped_column(Text, nullable=True)
    marketplace: Mapped[str] = mapped_column(String(32), nullable=False)
    alert_type: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'price_variation'")
    )
    threshold_pct: Mapped[Decimal | None] = mapped_column(Numeric(7, 4), nullable=True)
    prev_price_aed: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    current_price_aed: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    variation_pct: Mapped[Decimal | None] = mapped_column(Numeric(7, 4), nullable=True)
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    channel: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'email'"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


__all__ = ["PriceAlert"]

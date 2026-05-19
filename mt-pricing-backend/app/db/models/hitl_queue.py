"""HitlQueue — cola HITL priorizada por uncertainty × value (US-SCR-04-08b).

priority_score = uncertainty_score × product_value_aed.
Matches con alta incertidumbre (confidence < 0.6) en productos caros (> 1000 AED)
se encolan automáticamente desde price_monitor_task y match_service.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
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

HITL_STATUSES: tuple[str, ...] = ("pending", "approved", "rejected", "skipped")

# Umbral de confianza y valor para auto-enqueue
HITL_CONFIDENCE_THRESHOLD = 0.6
HITL_VALUE_THRESHOLD_AED = 1000.0


class HitlQueue(Base):
    """Una fila = un match candidato en cola HITL para revisión humana.

    Unique constraint: solo puede haber un item ``pending`` por ``match_id``
    (índice parcial en migración).
    """

    __tablename__ = "hitl_queue"

    __table_args__ = (
        Index("ix_hitl_queue_priority", "priority_score"),
        Index("ix_hitl_queue_status_priority", "status", "priority_score"),
        Index("ix_hitl_queue_match_id", "match_id"),
    )

    id: Mapped[UUID] = mapped_column(
        UUID_PG,
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    match_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("match_candidates.id", ondelete="CASCADE"),
        nullable=False,
    )
    # uncertainty_score: 1 - calibrated_confidence (o 1.0 si calibrated_confidence es NULL)
    uncertainty_score: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    # product_value_aed: último precio AED del SKU (de price_history_raw o match_candidate)
    product_value_aed: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    # priority_score = uncertainty_score × product_value_aed
    priority_score: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'pending'")
    )
    assigned_to: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    # true cuando VLM grade es A o B Y price_aed > 1000 AED (mig 142)
    high_value_review: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )
    # true cuando el SKU nunca había aparecido antes en match_candidates (mig 142)
    is_first_appearance: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


__all__ = ["HitlQueue"]

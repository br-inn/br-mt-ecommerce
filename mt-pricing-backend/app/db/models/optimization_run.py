"""Modelo de registro/alerta de drift de optimización (F8).

Migración: 20260603_151_optimization_runs.py
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, text
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UuidPkMixin
from app.db.types import UUID_PG


class PricingOptimizationRun(UuidPkMixin, TimestampMixin, Base):
    """Registro de una detección de drift de optimización + su diff (no aplica)."""

    __tablename__ = "pricing_optimization_runs"

    channel_id: Mapped[UUID] = mapped_column(
        UUID_PG, ForeignKey("channels.id", name="fk_opt_runs_channel"), nullable=False
    )
    selling_model: Mapped[str] = mapped_column(
        PG_ENUM("b2c", "b2b", name="selling_model", create_type=False), nullable=False
    )
    baseline_snapshot_id: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("pricing_scenarios.id", name="fk_opt_runs_baseline", ondelete="SET NULL"),
        nullable=True,
    )
    revert_snapshot_id: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("pricing_scenarios.id", name="fk_opt_runs_revert", ondelete="SET NULL"),
        nullable=True,
    )
    skus_scheme_changed: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    skus_signal_changed: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    drift_reasons: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    diff_detail: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_by: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("users.id", name="fk_opt_runs_ack_by", ondelete="SET NULL"),
        nullable=True,
    )

    __table_args__ = (
        Index("idx_opt_runs_lookup", "channel_id", "selling_model", text("detected_at DESC")),
        Index("idx_opt_runs_unack", "channel_id", postgresql_where=text("acknowledged_at IS NULL")),
    )


__all__ = ["PricingOptimizationRun"]

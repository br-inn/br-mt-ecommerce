"""SQLAlchemy model para la tabla dr_drills — registro de ejercicios DR."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UuidPkMixin
from app.db.types import UUID_PG


class DrDrill(UuidPkMixin, TimestampMixin, Base):
    """Ejercicio de Disaster Recovery registrado y su resultado."""

    __tablename__ = "dr_drills"

    drill_type: Mapped[str] = mapped_column(String(50), nullable=False)
    scheduled_date: Mapped[date] = mapped_column(Date(), nullable=False)
    executed_date: Mapped[date | None] = mapped_column(Date(), nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(20), nullable=True)
    duration_minutes: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    findings: Mapped[str | None] = mapped_column(Text(), nullable=True)
    runbook_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)
    conducted_by_user_id: Mapped[UUID | None] = mapped_column(
        UUID_PG, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text(), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "outcome IN ('pass', 'fail', 'partial')",
            name="ck_dr_drills_outcome",
        ),
        Index("idx_dr_drills_scheduled_date", "scheduled_date"),
        Index("idx_dr_drills_outcome", "outcome"),
    )


__all__ = ["DrDrill"]

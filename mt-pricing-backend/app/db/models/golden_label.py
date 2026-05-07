"""GoldenLabel + CalibratorVersion — feedback loop humano para calibrator.

US-1A-09-07 (Sprint 5).

GoldenLabel:
- (sku, candidate_id) ground truth label = 0/1.
- ``score`` = score crudo del comparador en el momento de la judgment.
- ``judged_by`` + ``judged_at`` para audit trail (sólo MT internal users).
- Único por ``(sku, candidate_id)`` — el último judgment gana via UPSERT.

CalibratorVersion:
- Storage versionado de modelos isotonic (JSON, sin pickle).
- ``is_active`` único — sólo un calibrator activo a la vez.
- ``trained_on_count`` para métricas de health (mín 50 labels para train).
- ``brier_score`` + ``ece`` para evaluar mejora antes de promover.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import UuidPkMixin
from app.db.types import UUID_PG


class GoldenLabel(UuidPkMixin, Base):
    """Ground truth label humano para entrenar el calibrator."""

    __tablename__ = "golden_labels"

    sku: Mapped[str] = mapped_column(
        Text,
        ForeignKey("products.sku", ondelete="CASCADE"),
        nullable=False,
    )
    candidate_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("match_candidates.id", ondelete="CASCADE"),
        nullable=False,
    )
    label: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[Any] = mapped_column(Numeric(5, 4), nullable=False)
    judged_by: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    judged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint("label IN (0, 1)", name="ck_golden_labels_label_binary"),
        CheckConstraint(
            "score >= 0 AND score <= 1",
            name="ck_golden_labels_score_range",
        ),
        UniqueConstraint("sku", "candidate_id", name="uq_golden_labels_sku_candidate"),
        Index("idx_golden_labels_sku", "sku"),
        Index("idx_golden_labels_judged_at", "judged_at"),
    )


class CalibratorVersion(UuidPkMixin, Base):
    """Storage versionado del IsotonicCalibrator (JSON serialization)."""

    __tablename__ = "calibrator_versions"

    version: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    model_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    trained_on_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    brier_score: Mapped[Any | None] = mapped_column(
        Numeric(7, 6),
        nullable=True,
    )
    ece: Mapped[Any | None] = mapped_column(
        Numeric(7, 6),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )
    trained_by: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    trained_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    promoted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "trained_on_count >= 0",
            name="ck_calibrator_versions_count_nonneg",
        ),
        Index(
            "idx_calibrator_versions_active",
            "is_active",
            postgresql_where=text("is_active = true"),
            unique=True,
        ),
    )


__all__ = ["CalibratorVersion", "GoldenLabel"]

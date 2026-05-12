"""MatchCandidate — candidatos de comparador (Sprint 3 foundation).

Persistencia mínima del pipeline de matching descrito en
``mt-product-matching-pipeline-detail.md``. Sprint 3 se queda en el subset
``pending|validated|discarded`` para el flujo humano básico; el pipeline
completo (``match_decisions`` + ``judge_rationale`` + RIS, etc.) se enchufa
en sprints siguientes.

FSM ``status``:
    pending → validated
    pending → discarded

Channels: ``amazon_uae`` | ``noon_uae`` (Sprint 3).

Kind: ``peer`` (mismo producto / sustituto cercano), ``drop`` (desplaza al
SKU MT — habilita G1) o ``unknown`` (sin clasificar).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UuidPkMixin
from app.db.types import UUID_PG

MATCH_CANDIDATE_CHANNELS: tuple[str, ...] = ("amazon_uae", "noon_uae")
MATCH_CANDIDATE_KINDS: tuple[str, ...] = ("peer", "drop", "unknown")
MATCH_CANDIDATE_STATUSES: tuple[str, ...] = ("pending", "validated", "discarded")
MATCH_CANDIDATE_LABELS: tuple[str, ...] = ("accept", "reject", "skip")


class MatchCandidate(UuidPkMixin, TimestampMixin, Base):
    __tablename__ = "match_candidates"

    product_sku: Mapped[str] = mapped_column(
        Text,
        ForeignKey("products.sku", ondelete="CASCADE"),
        nullable=False,
    )
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    external_id: Mapped[str] = mapped_column(Text, nullable=False)

    brand: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    price_aed: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    delivery_text: Mapped[str | None] = mapped_column(Text)

    specs_jsonb: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    kind: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'unknown'")
    )
    score: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'pending'")
    )

    validated_by: Mapped[UUID | None] = mapped_column(
        UUID_PG, ForeignKey("users.id", ondelete="SET NULL")
    )
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    discarded_reason: Mapped[str | None] = mapped_column(Text)

    # --- Human Queue (US-RND-01-10) ---
    # calibrated_confidence: confianza calibrada por el Isotonic Calibrator (Sprint 5).
    # Valor en [0, 1]. NULL mientras no corra el calibrador.
    calibrated_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))

    # label: veredicto del revisor humano (accept / reject / skip).
    label: Mapped[str | None] = mapped_column(String(16))
    # reviewer_user_id: FK al revisor (SET NULL si se borra el usuario).
    reviewer_user_id: Mapped[UUID | None] = mapped_column(
        UUID_PG, ForeignKey("users.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "channel IN ('amazon_uae','noon_uae')",
            name="ck_match_candidates_channel",
        ),
        CheckConstraint(
            "kind IN ('peer','drop','unknown')",
            name="ck_match_candidates_kind",
        ),
        CheckConstraint(
            "status IN ('pending','validated','discarded')",
            name="ck_match_candidates_status",
        ),
        CheckConstraint("score >= 0 AND score <= 100", name="ck_match_candidates_score"),
        CheckConstraint(
            "label IS NULL OR label IN ('accept','reject','skip')",
            name="ck_match_candidates_label",
        ),
        CheckConstraint(
            "calibrated_confidence IS NULL OR (calibrated_confidence >= 0 AND calibrated_confidence <= 1)",
            name="ck_match_candidates_calibrated_confidence",
        ),
        Index("idx_match_candidates_sku_status", "product_sku", "status"),
        Index(
            "idx_match_candidates_confidence",
            "calibrated_confidence",
        ),
        Index(
            "idx_match_candidates_unique_external",
            "product_sku",
            "channel",
            "external_id",
            unique=True,
        ),
    )

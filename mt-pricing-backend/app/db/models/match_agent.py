"""MatchAgentConfig + MatchAgentDecision — agente de validación de matches.

MatchAgentConfig: fila singleton (id=1) con la configuración editable del
agente (modo sombra/activo, alpha conformal, gate de labels mínimos).

MatchAgentDecision: serie temporal — un registro por cada veredicto del agente
(sombra o activo). human_outcome se rellena al validar/descartar para medir la
precisión de sombra.
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
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import UuidPkMixin
from app.db.types import UUID_PG

AGENT_MODES: tuple[str, ...] = ("shadow", "active")
AGENT_VERDICTS: tuple[str, ...] = ("auto_validate", "auto_discard", "human")
AGENT_SIGNALS: tuple[str, ...] = ("conformal", "bootstrap")


class MatchAgentConfig(Base):
    """Configuración singleton del agente (siempre id=1)."""

    __tablename__ = "match_agent_config"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    mode: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'shadow'"))
    alpha: Mapped[Decimal] = mapped_column(
        Numeric(4, 3), nullable=False, server_default=text("0.02")
    )
    min_labels_gate: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("200")
    )
    updated_by: Mapped[UUID | None] = mapped_column(
        UUID_PG, ForeignKey("users.id", ondelete="SET NULL")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint("id = 1", name="ck_match_agent_config_singleton"),
        CheckConstraint("mode IN ('shadow','active')", name="ck_match_agent_config_mode"),
        CheckConstraint("alpha > 0 AND alpha < 1", name="ck_match_agent_config_alpha"),
        CheckConstraint("min_labels_gate >= 1", name="ck_match_agent_config_gate"),
    )


class MatchAgentDecision(UuidPkMixin, Base):
    """Registro de un veredicto del agente sobre un candidato."""

    __tablename__ = "match_agent_decisions"

    candidate_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("match_candidates.id", ondelete="CASCADE"),
        nullable=False,
    )
    product_sku: Mapped[str] = mapped_column(Text, nullable=False)
    verdict: Mapped[str] = mapped_column(String(16), nullable=False)
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    applied: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    signal: Mapped[str] = mapped_column(String(24), nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    calibrated_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    review_priority: Mapped[str | None] = mapped_column(String(16))
    calibrator_version: Mapped[str | None] = mapped_column(Text)
    human_outcome: Mapped[str | None] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint(
            "verdict IN ('auto_validate','auto_discard','human')",
            name="ck_match_agent_decisions_verdict",
        ),
        CheckConstraint("mode IN ('shadow','active')", name="ck_match_agent_decisions_mode"),
        CheckConstraint(
            "signal IN ('conformal','bootstrap')",
            name="ck_match_agent_decisions_signal",
        ),
        CheckConstraint(
            "human_outcome IS NULL OR human_outcome IN ('validated','discarded')",
            name="ck_match_agent_decisions_outcome",
        ),
        Index("idx_match_agent_decisions_sku", "product_sku"),
        Index("idx_match_agent_decisions_created", "created_at"),
        Index("idx_match_agent_decisions_verdict_mode", "verdict", "mode"),
        Index("idx_match_agent_decisions_candidate", "candidate_id"),
    )

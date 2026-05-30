"""ORM models for F1 provenance + audit tables.

Two tables: source_observations (raw ingestion log) and source_health
(one row per source_op, tracks freshness SLA).

Migration: 20260603_149_provenance_audit.py
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, Text, text
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import UuidPkMixin
from app.db.types import UUID_PG

_SOURCE_OP = PG_ENUM(name="source_op", create_type=False)


class SourceObservation(UuidPkMixin, Base):
    """Registro inmutable de una observación de datos de provenance.

    Cada fila captura un valor observado (numérico o texto) para un campo
    de una tabla de destino, originado por una operación `source_op`.
    """

    __tablename__ = "source_observations"

    source_op: Mapped[str] = mapped_column(_SOURCE_OP, nullable=False)
    target_table: Mapped[str] = mapped_column(Text, nullable=False)
    target_id: Mapped[UUID | None] = mapped_column(UUID_PG, nullable=True)
    target_field: Mapped[str] = mapped_column(Text, nullable=False)
    channel_id: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("channels.id", name="fk_source_observations_channel"),
        nullable=True,
    )
    sku: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("products.sku", name="fk_source_observations_sku"),
        nullable=True,
    )
    value_numeric: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    value_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )
    correlation_id: Mapped[UUID | None] = mapped_column(UUID_PG, nullable=True)

    __table_args__ = (
        Index(
            "idx_source_obs_lookup",
            "target_table",
            "target_field",
            "sku",
            text("observed_at DESC"),
        ),
        Index(
            "idx_source_obs_channel",
            "channel_id",
            "source_op",
            text("observed_at DESC"),
        ),
    )


class SourceHealth(Base):
    """Estado de salud de cada fuente de datos (una fila por source_op).

    Seeded en la migración 149 con un registro por cada valor del enum
    `source_op` y el SLA de frescura en minutos.
    """

    __tablename__ = "source_health"

    source_op: Mapped[str] = mapped_column(_SOURCE_OP, primary_key=True)
    last_sync_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_sync_success_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    freshness_sla_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1440")
    )
    rows_last_sync: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )


__all__ = ["SourceObservation", "SourceHealth"]

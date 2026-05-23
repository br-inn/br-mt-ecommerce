"""PriceHistoryRaw — historial de precios scrapeados (US-SCR-04-01).

Tabla particionada por RANGE(scraped_at) — la migración 20260601_134 crea
las particiones físicas. El modelo SQLAlchemy apunta a la tabla padre
``price_history_raw`` para lecturas/escrituras; PG enruta automáticamente
a la partición correcta al insertar.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import UuidPkMixin
from app.db.types import UUID_PG


class PriceHistoryRaw(Base):
    """Una fila = un precio scrapeado para (match_id, marketplace) en un instante.

    Particionada por ``scraped_at`` — no usar UuidPkMixin porque las tablas
    particionadas PG necesitan la PK incluyendo la clave de partición.
    """

    __tablename__ = "price_history_raw"
    # SQLAlchemy no gestiona las particiones — Alembic lo hace.
    __table_args__ = (
        Index(
            "ix_price_history_raw_match_marketplace",
            "match_id",
            "marketplace",
            "scraped_at",
        ),
        {"postgresql_partition_by": "RANGE (scraped_at)"},
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
    marketplace: Mapped[str] = mapped_column(String(32), nullable=False)
    price_aed: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default=text("'AED'"))
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        primary_key=True,  # composite PK con scraped_at para particionado
    )
    sku: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )


__all__ = ["PriceHistoryRaw"]

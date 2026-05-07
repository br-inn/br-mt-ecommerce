"""ChannelListing + ChannelSyncEvent — Sprint 3 Channel Mirror.

Dos tablas:

- ``channel_listings``: snapshot del listing en el canal externo (Amazon
  UAE, Noon UAE) emparejado con su SKU canonical MT. Incluye estado
  BuyBox, stock, rating, y los snapshots JSONB ``canonical_snapshot`` /
  ``live_snapshot`` para diff a posteriori.
- ``channel_sync_events``: log de operaciones (pull / push / diff) para
  el sync log del frontend (últimas N entradas).

Decisiones:
- ``channel_code`` (text) en lugar de FK a ``channels.id`` — el frontend
  habla en términos de ``amazon_uae`` / ``noon_uae``, y mantenemos el
  acoplamiento bajo (la tabla ``channels`` modela canales B2C/B2B también
  que no aplican aquí).
- UNIQUE (channel_code, external_id) — un ASIN/Noon-id solo puede mapear
  a un único listing en nuestro sistema.
- ``buybox_state`` String + CHECK (no PgEnum) — alineado con la convención
  del repo (ver ``app/db/enums.py``).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
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
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UuidPkMixin


# Valores permitidos para buybox_state — alineado con frontend Pill states.
BUYBOX_STATES: tuple[str, ...] = ("own", "competitor", "none")
SYNC_EVENT_TYPES: tuple[str, ...] = ("pull", "push", "diff")


def _values_csv(values: tuple[str, ...]) -> str:
    return "(" + ",".join(f"'{v}'" for v in values) + ")"


class ChannelListing(UuidPkMixin, TimestampMixin, Base):
    """Listing canonical ↔ canal externo.

    Una row por (channel_code, product_sku). El ``external_id`` (ASIN /
    Noon SKU) puede ser ``""`` mientras no se haya emparejado.
    """

    __tablename__ = "channel_listings"

    product_sku: Mapped[str] = mapped_column(
        Text,
        ForeignKey("products.sku", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    channel_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    external_id: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("''")
    )

    buybox_state: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'none'")
    )
    buybox_pct_7d: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    stock_qty: Mapped[int | None] = mapped_column(Integer)

    rating: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    reviews_count: Mapped[int | None] = mapped_column(Integer)

    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    canonical_snapshot_jsonb: Mapped[dict[str, Any]] = mapped_column(
        "canonical_snapshot_jsonb",
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    live_snapshot_jsonb: Mapped[dict[str, Any]] = mapped_column(
        "live_snapshot_jsonb",
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )

    diff_summary: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )

    __table_args__ = (
        UniqueConstraint(
            "channel_code", "external_id", name="uq_channel_listings_channel_external"
        ),
        UniqueConstraint(
            "channel_code", "product_sku", name="uq_channel_listings_channel_sku"
        ),
        CheckConstraint(
            f"buybox_state IN {_values_csv(BUYBOX_STATES)}",
            name="ck_channel_listings_buybox_state",
        ),
        Index("idx_channel_listings_lookup", "channel_code", "product_sku"),
        Index(
            "idx_channel_listings_last_sync",
            "channel_code",
            "last_sync_at",
        ),
    )


class ChannelSyncEvent(UuidPkMixin, TimestampMixin, Base):
    """Log de eventos sync — pull/push/diff por (channel, sku).

    El frontend lo lee con `GET /channels/{code}/sync-log?limit=N` y muestra
    en el Sync log card. Mantenemos el row completo (con payload_jsonb) para
    troubleshooting offline.
    """

    __tablename__ = "channel_sync_events"

    channel_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    product_sku: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("products.sku", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(16), nullable=False)
    ok: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    summary: Mapped[str | None] = mapped_column(Text)
    payload_jsonb: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (
        CheckConstraint(
            f"event_type IN {_values_csv(SYNC_EVENT_TYPES)}",
            name="ck_channel_sync_events_event_type",
        ),
        Index(
            "idx_channel_sync_events_recent",
            "channel_code",
            "created_at",
        ),
    )


__all__ = [
    "BUYBOX_STATES",
    "SYNC_EVENT_TYPES",
    "ChannelListing",
    "ChannelSyncEvent",
]

"""UnmatchedOffer — ofertas de marketplace sin match con ningun SKU MT.

Almacena candidatos scrapeados (Amazon UAE / Noon UAE) que no encontraron
match en el pipeline. Sirven para reutilizacion en futuras rondas de matching
sin necesidad de re-scraping.

El campo `embedding` se rellena en background por un job separado; hasta
entonces es NULL.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    DateTime,
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


class UnmatchedOffer(UuidPkMixin, TimestampMixin, Base):
    __tablename__ = "unmatched_offers"

    marketplace: Mapped[str] = mapped_column(String(32), nullable=False)
    external_id: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)

    brand: Mapped[str | None] = mapped_column(Text)
    price_aed: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    delivery_text: Mapped[str | None] = mapped_column(Text)

    specs_jsonb: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    image_url: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)

    fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    source_sku: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Populated by background embedding job; NULL until then.
    embedding: Mapped[list[float] | None] = mapped_column(Vector(384), nullable=True)

    match_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    matched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint(
            "marketplace IN ('amazon_uae','noon_uae')",
            name="ck_unmatched_offers_marketplace",
        ),
        UniqueConstraint("fingerprint", name="uq_unmatched_offers_fingerprint"),
        Index("idx_unmatched_offers_marketplace", "marketplace"),
        Index(
            "idx_unmatched_offers_pending",
            "scraped_at",
            postgresql_where=text("matched_at IS NULL"),
        ),
        Index("idx_unmatched_offers_source_sku", "source_sku"),
    )

"""Comparator (research workstream) — hooks Fase 1.

Modelos placeholder para el sistema de comparación de productos. Ver ADR-012
y architecture-mt-pricing-mdm-phase1.md §17.1.

Fase 1 deja las tablas creadas pero **vacías**. La lógica real (OCR, reverse
image search, VLM judge, embeddings) entra en Fase 1.5+ cuando el research
workstream entregue criterios go/no-go contra dataset etiquetado.

Tablas:
- ``competitor_listings`` — listings competidores normalizados (Amazon UAE,
  Noon UAE, supplier sites, etc.). Soporta embedding pgvector dim 1536
  (OpenAI text-embedding-3-small / similares). Match opcional vía
  ``matched_product_sku`` + ``match_confidence``.
- ``match_decisions`` — decisiones humanas (match / no_match / uncertain)
  con ``evidence_jsonb`` para trazabilidad de audit (judge rationale, deal
  breakers, etc.). Una fila por decisión — historial completo conservado.

⚠ Sprint 0 (Fase 1): tablas vacías + service stub :class:`NoopComparatorService`.
No insertar filas hasta que research workstream firme la decisión go.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UuidPkMixin
from app.db.types import HAS_PGVECTOR, UUID_PG

# Embedding dim 1536 (ADR-012 §17.1: OpenAI text-embedding-3-small / similares).
# Fase 1: nullable — research workstream decide modelo final en S5+.
if HAS_PGVECTOR:  # pragma: no cover
    from pgvector.sqlalchemy import Vector  # type: ignore[import-not-found]

    _EMBEDDING_TYPE: Any = Vector(1536)
else:  # pragma: no cover
    from sqlalchemy import Float

    _EMBEDDING_TYPE = ARRAY(Float)


MATCH_DECISIONS: tuple[str, ...] = ("match", "no_match", "uncertain")


class CompetitorListing(UuidPkMixin, TimestampMixin, Base):
    """Listing competidor normalizado — vacío Fase 1, poblado por research wave."""

    __tablename__ = "competitor_listings"

    # Sourcing
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)

    # Payload sin procesar + normalizado (ports producen el normalizado)
    raw_payload_jsonb: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    normalized_jsonb: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )

    # Imagen + dedup hash
    image_url: Mapped[str | None] = mapped_column(Text)
    image_sha256: Mapped[str | None] = mapped_column(String(64))

    # Embedding pgvector dim 1536 — nullable hasta que research workstream
    # entregue el modelo de embedding firmado.
    embedding: Mapped[list[float] | None] = mapped_column(
        _EMBEDDING_TYPE, nullable=True
    )

    # Match opcional contra catálogo MT
    matched_product_sku: Mapped[str | None] = mapped_column(
        Text, ForeignKey("products.sku", ondelete="SET NULL"), nullable=True
    )
    match_confidence: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4), nullable=True
    )

    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        # Uniqueness por (source, source_id) — un listing no duplicado dentro
        # de un mismo provider.
        Index(
            "ux_competitor_listings_source",
            "source",
            "source_id",
            unique=True,
        ),
        Index(
            "ix_competitor_listings_matched_sku",
            "matched_product_sku",
        ),
        CheckConstraint(
            "match_confidence IS NULL OR (match_confidence >= 0 AND match_confidence <= 1)",
            name="ck_competitor_listings_confidence_range",
        ),
    )


class MatchDecision(UuidPkMixin, TimestampMixin, Base):
    """Decisión humana sobre un candidato listing → SKU."""

    __tablename__ = "match_decisions"

    competitor_listing_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("competitor_listings.id", ondelete="CASCADE"),
        nullable=False,
    )
    product_sku: Mapped[str] = mapped_column(
        Text,
        ForeignKey("products.sku", ondelete="CASCADE"),
        nullable=False,
    )
    decision: Mapped[str] = mapped_column(String(16), nullable=False)
    confidence: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4), nullable=True
    )
    evidence_jsonb: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    decided_by: Mapped[UUID | None] = mapped_column(
        UUID_PG, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    __table_args__ = (
        CheckConstraint(
            "decision IN ('match','no_match','uncertain')",
            name="ck_match_decisions_decision",
        ),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_match_decisions_confidence_range",
        ),
        Index(
            "ix_match_decisions_listing",
            "competitor_listing_id",
        ),
        Index(
            "ix_match_decisions_sku",
            "product_sku",
        ),
    )


__all__ = [
    "MATCH_DECISIONS",
    "CompetitorListing",
    "MatchDecision",
]

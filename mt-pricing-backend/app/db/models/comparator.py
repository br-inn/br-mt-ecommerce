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

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    ARRAY,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB
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


class CompetitorBrand(UuidPkMixin, TimestampMixin, Base):
    """Marca competidora registrada para scraping periódico en Amazon UAE."""

    __tablename__ = "competitor_brands"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    amazon_search_term: Mapped[str | None] = mapped_column(String(200), nullable=True)
    amazon_dept: Mapped[str] = mapped_column(
        String(100), nullable=False, server_default=text("'industrial'")
    )
    amazon_category_node: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_scraped_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # US-SCR-04-03: monitoreo continuo de precios activo para esta marca
    monitoring_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )

    __table_args__ = (
        Index("ux_competitor_brands_name", func.lower(name), unique=True),
    )

    @property
    def effective_search_term(self) -> str:
        return self.amazon_search_term or self.name


class BrandExtractor(UuidPkMixin, TimestampMixin, Base):
    """Mapeo de atributos generado por LLM por marca x marketplace (US-SCR-05-01).

    Generado una vez en Bootstrap mode via Claude; reutilizado sin LLM en cada
    monitoring scrape. ``attribute_map`` traduce labels de Amazon al schema
    canónico de CandidateRaw.specs.
    """

    __tablename__ = "scraper_brand_extractors"

    brand_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("competitor_brands.id", ondelete="CASCADE"),
        nullable=False,
    )
    marketplace: Mapped[str] = mapped_column(String(32), nullable=False)
    # {"Amazon label": {"field": "canonical_field", "type": "str|float|int"}}
    attribute_map: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    sample_asins: Mapped[list[str]] = mapped_column(
        postgresql.ARRAY(Text),
        nullable=False,
        server_default=text("'{}'::text[]"),
    )
    generated_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    hit_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 4), nullable=False, server_default=text("0")
    )

    __table_args__ = (
        UniqueConstraint("brand_id", "marketplace", name="uq_brand_extractor"),
        CheckConstraint(
            "marketplace IN ('amazon_uae', 'noon_uae')",
            name="ck_brand_extractor_marketplace",
        ),
    )


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

    # Reverse Image Search — US-F15-02-03
    reverse_image_hits: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    reverse_image_searched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reverse_image_provider: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # Price Sanity Check — US-F15-02-04
    price_too_low: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    price_too_high: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    sanity_check_skipped: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    competitor_brand_id: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("competitor_brands.id", ondelete="SET NULL"),
        nullable=True,
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
        Index("ix_competitor_listings_brand_id", "competitor_brand_id"),
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

    # VLM judge columns (US-F15-02-02) — nullable: populated when VLM judge runs
    judge_verdict: Mapped[str | None] = mapped_column(String(16), nullable=True)
    judge_confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    judge_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    judge_image_regions: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    deal_breakers_triggered: Mapped[list[str] | None] = mapped_column(
        ARRAY(Text()), nullable=True
    )
    judge_model_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    judge_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "decision IN ('match','no_match','uncertain')",
            name="ck_match_decisions_decision",
        ),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_match_decisions_confidence_range",
        ),
        CheckConstraint(
            "judge_confidence IS NULL OR (judge_confidence >= 0 AND judge_confidence <= 1)",
            name="ck_match_decisions_judge_confidence_range",
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


class CompetitorFetchError(Base):
    """Errores de fetch de precios de competidores — US-F15-02-01.

    Poblada por AmazonSPApiFetcherAdapter._log_fetch_error (best-effort).
    Usada para diagnóstico y monitoreo de la integración SP-API.
    """

    __tablename__ = "competitor_fetch_errors"

    id: Mapped[UUID] = mapped_column(
        UUID_PG,
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    asin: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    error_type: Mapped[str] = mapped_column(String(100), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
        index=True,
    )


class ProductEquivalence(Base):
    """Par de productos equivalentes — US-F15-01-05.

    Extraído de fichas técnicas PDF o declarado manualmente. Sincronizado
    al Knowledge Graph como edges EQUIVALENT_TO via
    ``mt.graphrag.ingest_equivalences_from_pdf``.
    """

    __tablename__ = "product_equivalences"

    id: Mapped[UUID] = mapped_column(
        UUID_PG,
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    product_id_a: Mapped[str] = mapped_column(
        Text,
        ForeignKey("products.sku", ondelete="CASCADE"),
        nullable=False,
    )
    product_id_b: Mapped[str] = mapped_column(
        Text,
        ForeignKey("products.sku", ondelete="CASCADE"),
        nullable=False,
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.8)
    source: Mapped[str] = mapped_column(String(200), nullable=False, default="manual")
    extracted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )
    synced_to_kg: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        UniqueConstraint("product_id_a", "product_id_b", name="uq_product_equivalences_pair"),
        Index("ix_product_equivalences_product_id_a", "product_id_a"),
        Index("ix_product_equivalences_product_id_b", "product_id_b"),
        Index(
            "ix_product_equivalences_synced",
            "synced_to_kg",
            postgresql_where=text("synced_to_kg = false"),
        ),
    )


class ExtractorAlert(Base):
    """Alerta de degradación de hit_rate del Brand Extractor (US-SCR-05-04).

    Se crea/actualiza cuando el hit_rate de un BrandExtractor cae > 20pp
    respecto a la baseline de 7 días. ``resolved_at`` NULL = alerta activa.
    """

    __tablename__ = "scraper_extractor_alerts"

    id: Mapped[UUID] = mapped_column(
        UUID_PG,
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    brand_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("competitor_brands.id", ondelete="CASCADE"),
        nullable=False,
    )
    marketplace: Mapped[str] = mapped_column(String(32), nullable=False)
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    hit_rate_now: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    hit_rate_baseline: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    delta_pp: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_by: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    __table_args__ = (
        Index(
            "ix_extractor_alerts_brand_mkt_resolved",
            "brand_id",
            "marketplace",
            "resolved_at",
        ),
    )


class PriceCalibrationRange(Base):
    """Rango P10/P90 de calibración de precios por categoría+divisa (US-F15-02-04).

    Actualizado nocturnamente por la task ``price_sanity.recalibrate_price_ranges``.
    Usado por :class:`app.services.comparator.price_sanity.PriceSanityCheckService`
    para filtrar candidatos con precios anómalos antes del VLM judge.
    """

    __tablename__ = "price_calibration_ranges"

    id: Mapped[UUID] = mapped_column(
        UUID_PG,
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    category_id: Mapped[str] = mapped_column(String(64), nullable=False)
    expected_min_p10: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    expected_max_p90: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, server_default=text("'AED'")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    __table_args__ = (
        UniqueConstraint(
            "category_id",
            "currency",
            name="uq_price_calibration_ranges_category_currency",
        ),
    )


class ComparatorModelRegistry(Base):
    """Registro de modelos embedding fine-tuned — US-F15-03-02.

    Ciclo de vida: candidate → active (promote_model script) → retired.
    Solo un modelo puede tener status='active' en producción; el promote_model
    script se encarga de retirar el anterior al promover uno nuevo.
    """

    __tablename__ = "comparator_model_registry"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID_PG,
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    base_model: Mapped[str] = mapped_column(String(256), nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    eval_metrics_jsonb: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )
    trained_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="candidate",
        server_default="candidate",
    )

    __table_args__ = (
        Index("ix_comparator_model_registry_status", "status"),
    )


class ManufacturerWhitelist(Base):
    """Whitelist de fabricantes con dominios canónicos para RIS boost — US-F15-02-03.

    Cada fila representa un fabricante con su lista de dominios oficiales
    (canonical_domains) y aliases de marca (brand_aliases).
    ``get_canonical_domains()`` en ris_boost.py hace match por
    ``manufacturer_name ILIKE :brand`` o ``:brand = ANY(brand_aliases)``
    y retorna el union de canonical_domains de todos los matches activos.
    """

    __tablename__ = "manufacturers_whitelist"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID_PG,
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    manufacturer_name: Mapped[str] = mapped_column(
        String(128), nullable=False, unique=True
    )
    canonical_domains: Mapped[list[str]] = mapped_column(
        ARRAY(Text()),
        nullable=False,
        server_default=text("'{}'::text[]"),
    )
    brand_aliases: Mapped[list[str]] = mapped_column(
        ARRAY(Text()),
        nullable=False,
        server_default=text("'{}'::text[]"),
    )
    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        server_default=text("1.0"),
    )
    active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        Index("idx_manufacturers_whitelist_active", "active"),
    )


__all__ = [
    "MATCH_DECISIONS",
    "BrandExtractor",
    "ComparatorModelRegistry",
    "CompetitorBrand",
    "CompetitorFetchError",
    "CompetitorListing",
    "ExtractorAlert",
    "ManufacturerWhitelist",
    "MatchDecision",
    "PriceCalibrationRange",
    "ProductEquivalence",
]

"""Product + ProductTranslation + ProductAsset (formerly ProductImage).

Notas:
- PK del producto es `sku` TEXT (alineado con architecture §8.4); `internal_id`
  UUID adicional para joins sintéticos (FK desde tablas que prefieran UUID).
- `embedding` se modela placeholder ARRAY(Float) si pgvector no está disponible.
- `data_quality` es `String(16) + CHECK` (ver `enums.py` rationale).
- Wave 1: ProductImage → ProductAsset; ProductImage mantenida como alias deprecado.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
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
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.enums import DataQuality, ReleaseStatus, TranslationStatus, values_csv
from app.db.mixins import UuidPkMixin
from app.db.types import HAS_PGVECTOR, UUID_PG

# Vector real si la lib está; ARRAY(Float) si no.
if HAS_PGVECTOR:  # pragma: no cover
    from pgvector.sqlalchemy import Vector  # type: ignore[import-not-found]

    _EMBEDDING_TYPE: Any = Vector(1024)
else:
    from sqlalchemy import Float

    _EMBEDDING_TYPE = ARRAY(Float)


class Product(Base):
    __tablename__ = "products"

    sku: Mapped[str] = mapped_column(Text, primary_key=True)
    internal_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        nullable=False,
        unique=True,
        server_default=text("gen_random_uuid()"),
    )

    # Fase B drop (mig 065): name_en/description_en/marketing_copy_en se
    # eliminaron de la tabla; sustituidos por product_translations(lang='en').
    # Se exponen como hybrid_property read-only para preservar compat con
    # código existente que lee `product.name_en`. Para escritura usar
    # ProductService.upsert_translation con lang='en'.

    family: Mapped[str] = mapped_column(Text, nullable=False)
    subfamily: Mapped[str | None] = mapped_column(Text)
    type: Mapped[str | None] = mapped_column(Text)
    material: Mapped[str | None] = mapped_column(Text)
    dn: Mapped[str | None] = mapped_column(Text)
    pn: Mapped[str | None] = mapped_column(Text)
    connection: Mapped[str | None] = mapped_column(Text)
    brand: Mapped[str | None] = mapped_column(Text)

    specs: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    dimensions: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    packaging: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    weight: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    weight_unit: Mapped[str | None] = mapped_column(String(8), server_default=text("'kg'"))
    intrastat_code: Mapped[str | None] = mapped_column(Text)
    erp_name: Mapped[str | None] = mapped_column(Text)

    # M1-08 — GS1 global trade item number (EAN-8 / EAN-13 / GTIN-14)
    gtin: Mapped[str | None] = mapped_column(String(14), nullable=True)
    # Marketplace export fields (Task 1 migration)
    hs_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    country_of_origin: Mapped[str | None] = mapped_column(
        Text, nullable=True, server_default=text("'ES'")
    )
    # M1-04 — unidad de medida base del producto (SAP MM base UoM)
    base_uom: Mapped[str] = mapped_column(String(10), nullable=False, server_default=text("'UNIT'"))

    data_quality: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'partial'")
    )
    manual_locked_fields: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")
    )
    # Fase B drop (mig 066): products.active eliminado; se deriva de
    # lifecycle_status='active' vía hybrid_property (read-only).

    # ---- Wave 2 ----------------------------------------------------------
    # Lifecycle / identity
    # Usa PG_ENUM con create_type=False porque el tipo lifecycle_status ya
    # existe en BD (mig. 037). Declararlo como ENUM permite que asyncpg
    # haga el binding correcto del parámetro (evita ::VARCHAR mismatch).
    lifecycle_status: Mapped[str] = mapped_column(
        PG_ENUM(
            "draft",
            "in_review",
            "active",
            "deprecated",
            "replaced",
            "discontinued",
            name="lifecycle_status",
            create_type=False,
        ),
        nullable=False,
        server_default=text("'active'::lifecycle_status"),
    )
    revision: Mapped[str | None] = mapped_column(Text)
    series: Mapped[str | None] = mapped_column(Text)
    parent_sku: Mapped[str | None] = mapped_column(
        Text, ForeignKey("products.sku", ondelete="SET NULL", name="fk_products_parent_sku")
    )
    is_parent: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    is_variant: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))

    # Technical scalars (solo transversales — los específicos de válvula
    # viven en `specs` JSONB validados por JSON Schema; ver mig. 043).
    size: Mapped[str | None] = mapped_column(Text)
    temp_min_c: Mapped[int | None] = mapped_column(Integer)
    temp_max_c: Mapped[int | None] = mapped_column(Integer)
    pressure_max_bar: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))

    # mig 099 — Dimensiones por norma (DN/NPS)
    # bore_mm: diámetro de paso del estándar principal — el "dn_real" del spec.
    # Para multi-norma usar product_bore_dimensions (detalle completo).
    bore_mm: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 2),
        comment="Bore real (waterway) en mm — estándar principal. Detalle en product_bore_dimensions.",
    )
    dimensional_standard: Mapped[str | None] = mapped_column(
        String(16), comment="Sistema dimensional principal: DIN | ASME | AWWA | ISO"
    )

    # Editorial / SEO
    # Fase B drop (mig 065): products.tags ARRAY eliminado; sustituido por
    # vocabularios M:N (product_certifications + product_applications).
    video_url: Mapped[str | None] = mapped_column(Text)
    external_url: Mapped[str | None] = mapped_column(Text)

    # ---- Stage 1 Opción C — taxonomía FK (mig. 042) ----------------------
    # Stage 4a (mig. 048): brand_id + family_id promovidos a NOT NULL tras
    # cobertura 100% verificada. subfamily_id + type_id siguen NULLABLE hasta
    # Stage 4b (clasificación masiva).
    brand_id: Mapped[UUID] = mapped_column(
        UUID_PG, ForeignKey("brands.id", ondelete="RESTRICT"), nullable=False
    )
    family_id: Mapped[UUID] = mapped_column(
        UUID_PG, ForeignKey("families.id", ondelete="RESTRICT"), nullable=False
    )
    subfamily_id: Mapped[UUID | None] = mapped_column(
        UUID_PG, ForeignKey("subfamilies.id", ondelete="RESTRICT"), nullable=True
    )
    type_id: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("product_types.id", ondelete="RESTRICT"),
        nullable=True,
    )

    # ---- Stage 3 — Series rica + Material vocab + display pair (migs 045/046) ---
    # `series_id` y `material_id` coexisten con TEXT escalares (`series`, `material`).
    # `display_pair_sku` empareja modelos por color (4295 ↔ 42952) — self-FK.
    series_id: Mapped[UUID | None] = mapped_column(
        UUID_PG, ForeignKey("series.id", ondelete="RESTRICT"), nullable=True
    )
    model_id: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("product_models.id", ondelete="SET NULL"),
        nullable=True,
    )
    material_id: Mapped[UUID | None] = mapped_column(
        UUID_PG, ForeignKey("materials.id", ondelete="RESTRICT"), nullable=True
    )
    display_pair_sku: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("products.sku", ondelete="SET NULL", name="fk_products_display_pair_sku"),
        nullable=True,
    )

    # Embeddings (Sprint 2+) — nullable, sin índice HNSW por ahora.
    embedding_text: Mapped[Any] = mapped_column(_EMBEDDING_TYPE, nullable=True)
    embedding_image: Mapped[Any] = mapped_column(_EMBEDDING_TYPE, nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(Text)
    embedding_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    created_by: Mapped[UUID | None] = mapped_column(
        UUID_PG, ForeignKey("users.id", ondelete="SET NULL")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=text("now()"),
    )
    updated_by: Mapped[UUID | None] = mapped_column(
        UUID_PG, ForeignKey("users.id", ondelete="SET NULL")
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    translations: Mapped[list[ProductTranslation]] = relationship(
        back_populates="product", cascade="all, delete-orphan", lazy="selectin"
    )
    # `assets` — all asset kinds; `images` — backward compat alias (kind='photo' only)
    assets: Mapped[list[ProductAsset]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        foreign_keys="[ProductAsset.sku]",
        primaryjoin="Product.sku == ProductAsset.sku",
    )

    @property
    def images(self) -> list[ProductAsset]:
        """Backward-compat: returns only photo-kind assets."""
        return [a for a in self.assets if a.kind == "photo"]

    # Wave 4 — vocabularios M:N (selectin para incluir en ProductDetail)
    product_certifications: Mapped[list[ProductCertification]] = relationship(  # type: ignore[name-defined]
        "ProductCertification",
        back_populates="product",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    product_applications: Mapped[list[ProductApplication]] = relationship(  # type: ignore[name-defined]
        "ProductApplication",
        back_populates="product",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # Plan 2026-05-15 — model hierarchy link
    model: Mapped[ProductModel | None] = relationship(  # type: ignore[name-defined]
        "ProductModel",
        foreign_keys="[Product.model_id]",
        lazy="select",
    )

    # Wave 3 — componentes (materiales por componente, conexiones múltiples).
    materials: Mapped[list[ProductMaterial]] = relationship(  # type: ignore[name-defined]
        "ProductMaterial",
        back_populates="product",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    connections: Mapped[list[ProductConnection]] = relationship(  # type: ignore[name-defined]
        "ProductConnection",
        back_populates="product",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # Wave 6 — tech tables (P/T, materials matrix, dimensions by DN).
    tech_tables: Mapped[list[ProductTechTable]] = relationship(  # type: ignore[name-defined]
        "ProductTechTable",
        back_populates="product",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # Wave 7 — compatibilidades M:N (recambios/accesorios).
    # outgoing: enlaces donde este producto es el "origen".
    # incoming: enlaces donde este producto es el "destino" (viewonly — no mutamos desde aquí).
    compatibilities_outgoing: Mapped[list[ProductCompatibility]] = relationship(  # type: ignore[name-defined]
        "ProductCompatibility",
        foreign_keys="ProductCompatibility.product_sku",
        back_populates="product",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    compatibilities_incoming: Mapped[list[ProductCompatibility]] = relationship(  # type: ignore[name-defined]
        "ProductCompatibility",
        foreign_keys="ProductCompatibility.compatible_with_sku",
        back_populates="compatible_with",
        lazy="selectin",
        viewonly=True,
    )

    # Stage 3 — divisiones M:N (selectin para incluir en ProductDetail)
    product_divisions: Mapped[list[ProductDivision]] = relationship(  # type: ignore[name-defined]
        "ProductDivision",
        back_populates="product",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # Stage 3 — viewonly relationships para eager-load en GET /products/{sku}.
    # Nombres _rel evitan colisión con TEXT escalares legacy series/material.
    # lazy="raise" previene lazy-SQL accidental en contexto async.
    series_rel: Mapped[Any] = relationship(
        "Series",
        foreign_keys="[Product.series_id]",
        lazy="raise",
        viewonly=True,
    )
    material_rel: Mapped[Any] = relationship(
        "Material",
        foreign_keys="[Product.material_id]",
        lazy="raise",
        viewonly=True,
    )
    display_pair_rel: Mapped[Any] = relationship(
        "Product",
        foreign_keys="[Product.display_pair_sku]",
        primaryjoin="Product.display_pair_sku == Product.sku",
        lazy="raise",
        viewonly=True,
    )

    # ---- Fase B hybrid properties (read-only compat layer) ------------------
    # Permiten que código legacy siga leyendo prod.active / prod.name_en /
    # prod.description_en / prod.marketing_copy_en sin reescribir.
    # En contextos SQL (`Product.active`, `Product.name_en` dentro de select)
    # se traducen a expressions equivalentes — para name_en/description_en/
    # marketing_copy_en se usa un correlated subquery a product_translations
    # con lang='en'.

    @hybrid_property
    def active(self) -> bool:
        """`True` si lifecycle_status == 'active'. Read-only (escribir en lifecycle_status)."""
        return self.lifecycle_status == "active"

    @active.expression  # type: ignore[no-redef]
    def active(cls):
        return cls.lifecycle_status == "active"

    @hybrid_property
    def name_en(self) -> str | None:
        """Lee `name` de la traducción lang='en' si está cargada/disponible."""
        for t in self.translations or []:
            if t.lang == "en":
                return t.name
        return None

    @name_en.expression  # type: ignore[no-redef]
    def name_en(cls):
        from sqlalchemy import select as _select

        return (
            _select(ProductTranslation.name)
            .where(
                ProductTranslation.sku == cls.sku,
                ProductTranslation.lang == "en",
            )
            .correlate(cls)
            .scalar_subquery()
        )

    @hybrid_property
    def description_en(self) -> str | None:
        for t in self.translations or []:
            if t.lang == "en":
                return t.description
        return None

    @description_en.expression  # type: ignore[no-redef]
    def description_en(cls):
        from sqlalchemy import select as _select

        return (
            _select(ProductTranslation.description)
            .where(
                ProductTranslation.sku == cls.sku,
                ProductTranslation.lang == "en",
            )
            .correlate(cls)
            .scalar_subquery()
        )

    @hybrid_property
    def marketing_copy_en(self) -> str | None:
        for t in self.translations or []:
            if t.lang == "en":
                return t.marketing_copy
        return None

    @marketing_copy_en.expression  # type: ignore[no-redef]
    def marketing_copy_en(cls):
        from sqlalchemy import select as _select

        return (
            _select(ProductTranslation.marketing_copy)
            .where(
                ProductTranslation.sku == cls.sku,
                ProductTranslation.lang == "en",
            )
            .correlate(cls)
            .scalar_subquery()
        )

    @hybrid_property
    def tags(self) -> list[str]:
        """Read-only: lista vacía (campo legacy dropeado en Fase B mig 065).

        Sustituido por `product_certifications` y `product_applications`
        (vocabularios M:N). Esta compat-property evita romper código que
        leía `prod.tags` (effective_display_service); ahora siempre devuelve
        lista vacía y el caller debe migrar a los vocabs.
        """
        return []

    # Fase B drop (mig 065/066): idx_products_active e idx_products_name_trgm
    # removidos en BD; aquí se elimina la declaración para alinear modelo y
    # esquema. Cualquier full-text futuro debería indexar
    # product_translations.name por lang.
    # M1-04 — conversiones UoM alternativas (ej: 1 BOX = 12 UNIT)
    uom_conversions: Mapped[list[ProductUomConversion]] = relationship(
        "ProductUomConversion",
        back_populates="product",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # M1-01 — releases por mercado (ej: UAE, KSA, MX)
    releases: Mapped[list[ProductRelease]] = relationship(
        "ProductRelease",
        back_populates="product",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # mig 099 — dimensiones reales por norma (EN 558 / ASME B16.10 / AWWA C504)
    bore_dimensions: Mapped[list[ProductBoreDimension]] = relationship(
        "ProductBoreDimension",
        back_populates="product",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # Marketplace export listings (Task 1 migration — product_marketplace_listings)
    marketplace_listings: Mapped[list[MarketplaceListing]] = relationship(  # type: ignore[name-defined]
        "MarketplaceListing",
        back_populates="product",
        cascade="all, delete-orphan",
        lazy="select",
    )

    __table_args__ = (
        CheckConstraint(
            f"data_quality IN {values_csv(DataQuality)}",
            name="ck_products_data_quality",
        ),
        CheckConstraint(
            "gtin IS NULL OR (length(gtin) IN (8,12,13,14) AND gtin ~ '^[0-9]+$')",
            name="ck_products_gtin_format",
        ),
        Index("idx_products_family", "family"),
        Index("idx_products_brand", "brand"),
        Index("idx_products_specs_gin", "specs", postgresql_using="gin"),
        Index("idx_products_gtin", "gtin"),
        # HNSW para embeddings — Sprint 2+. No se crea ahora.
    )


class ProductTranslation(Base):
    __tablename__ = "product_translations"

    sku: Mapped[str] = mapped_column(
        Text, ForeignKey("products.sku", ondelete="CASCADE"), primary_key=True
    )
    lang: Mapped[str] = mapped_column(String(2), primary_key=True)
    name: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    marketing_copy: Mapped[str | None] = mapped_column(Text)
    # ---- Wave 8: SEO + editorial -----------------------------------------
    meta_title: Mapped[str | None] = mapped_column(Text)
    meta_description: Mapped[str | None] = mapped_column(Text)
    applications_text: Mapped[str | None] = mapped_column(Text)
    technical_limits: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    marketing_features: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'pending'")
    )
    translated_by: Mapped[UUID | None] = mapped_column(
        UUID_PG, ForeignKey("users.id", ondelete="SET NULL")
    )
    translated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by: Mapped[UUID | None] = mapped_column(
        UUID_PG, ForeignKey("users.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=text("now()"),
    )

    product: Mapped[Product] = relationship(back_populates="translations")

    __table_args__ = (
        CheckConstraint("lang IN ('es','ar','en')", name="ck_translations_lang"),
        CheckConstraint(
            f"status IN {values_csv(TranslationStatus)}",
            name="ck_translations_status",
        ),
        Index("idx_translations_status", "lang", "status"),
    )


class ProductAsset(UuidPkMixin, Base):
    """Unified asset table (Wave 1) — covers photos, PDFs, drawings, videos, etc.

    Replaces ``product_images`` (table renamed in migration 030).
    ``ProductImage`` is kept as a deprecated alias below.
    """

    __tablename__ = "product_assets"

    sku: Mapped[str] = mapped_column(
        Text, ForeignKey("products.sku", ondelete="CASCADE"), nullable=False
    )
    # kind — one of the 10 asset types.
    kind: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'photo'"))
    # bucket — Supabase Storage bucket name.
    bucket: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'product-images'")
    )
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    original_url: Mapped[str | None] = mapped_column(Text)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    # position — sort order within (sku, kind).
    position: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    alt_text: Mapped[str | None] = mapped_column(Text)
    locale: Mapped[str | None] = mapped_column(Text)
    caption: Mapped[str | None] = mapped_column(Text)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    bytes_size: Mapped[int | None] = mapped_column(BigInteger)
    mime_type: Mapped[str | None] = mapped_column(Text)
    hash_sha256: Mapped[str | None] = mapped_column(Text)
    # variants — jsonb storing thumbnail/avif/blurhash URLs keyed by size.
    variants: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    # asset_meta — jsonb for kind-specific metadata (dimensions, pages, etc.).
    # Note: Python attr uses `asset_meta` because `metadata` is reserved by SA.
    # The DB column is named `metadata` via mapped_column key param.
    asset_meta: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    revision: Mapped[str | None] = mapped_column(Text)
    # supersedes_id — self-referential FK for asset versioning.
    supersedes_id: Mapped[UUID | None] = mapped_column(
        UUID_PG, ForeignKey("product_assets.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'active'"))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_by: Mapped[UUID | None] = mapped_column(
        UUID_PG, ForeignKey("users.id", ondelete="SET NULL")
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    created_by: Mapped[UUID | None] = mapped_column(
        UUID_PG, ForeignKey("users.id", ondelete="SET NULL")
    )

    # Relationships.
    product: Mapped[Product] = relationship(
        back_populates="assets",
        foreign_keys=[sku],
        primaryjoin="ProductAsset.sku == Product.sku",
    )
    # Self-referential: which asset this one supersedes.
    parent: Mapped[ProductAsset | None] = relationship(
        "ProductAsset",
        remote_side="ProductAsset.id",
        foreign_keys=[supersedes_id],
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('active','archived','broken','pending_upload','processing')",
            name="ck_assets_status",
        ),
        CheckConstraint(
            "kind IN ("
            "'photo','banner','datasheet_pdf','exploded_3d',"
            "'section_drawing','dimension_drawing','certificate_pdf',"
            "'video_link','external_url','mirror_url'"
            ")",
            name="ck_assets_kind",
        ),
        # (bucket, storage_path) must be unique.
        # Note: unique=True on column would conflict with SA's handling when we
        # use the table-level constraint here; we define it as an Index with unique=True.
        Index("uq_assets_bucket_path", "bucket", "storage_path", unique=True),
        Index("idx_product_assets_sku_kind", "sku", "kind", "position"),
        Index("idx_product_assets_hash", "hash_sha256"),
    )


# ---------------------------------------------------------------------------
# Backward-compat alias — deprecated; use ProductAsset directly.
# ---------------------------------------------------------------------------
ProductImage = ProductAsset  # type: ignore[misc]


# ---------------------------------------------------------------------------
# M1-04 — Product UoM Conversions (SAP MM alternate UoM)
# ---------------------------------------------------------------------------
class ProductUomConversion(UuidPkMixin, Base):
    """Factores de conversión entre unidades de medida por producto.

    Ejemplo: 1 BOX de MT-V-038 = 12 UNIT.
    La tabla permite múltiples rutas: BOX→UNIT, PALLET→UNIT, KG→UNIT, etc.
    """

    __tablename__ = "product_uom_conversions"

    product_sku: Mapped[str] = mapped_column(
        Text, ForeignKey("products.sku", ondelete="CASCADE"), nullable=False
    )
    uom_from: Mapped[str] = mapped_column(String(10), nullable=False)
    uom_to: Mapped[str] = mapped_column(String(10), nullable=False)
    # Multiplicador: qty_in_uom_from × factor = qty_in_uom_to
    factor: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    # EP-ERP-01-03 (mig 20260514_106) — sentido canónico de la conversión.
    direction: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    product: Mapped[Product] = relationship(back_populates="uom_conversions")

    __table_args__ = (
        CheckConstraint("uom_from <> uom_to", name="ck_uom_conv_no_self_loop"),
        CheckConstraint("factor > 0", name="ck_uom_conv_positive_factor"),
        Index(
            "uq_uom_conv_product_pair",
            "product_sku",
            "uom_from",
            "uom_to",
            unique=True,
        ),
    )


# ---------------------------------------------------------------------------
# M1-01 — Product Release (D365 Released Product / SAP MM Plant Data)
# ---------------------------------------------------------------------------
class ProductRelease(UuidPkMixin, Base):
    """Activación de un producto global en un mercado específico.

    Inspirado en D365 "Released Product" y SAP MM "Plant / Sales Org data".
    Un producto existe una sola vez en `products` (identidad global) pero
    puede tener distintas configuraciones por mercado: precio local, clase
    fiscal, nombre en idioma local, SKU del distribuidor, etc.

    Regla: solo productos con release is_active=true aparecen en catálogo
    para ese market_code.
    """

    __tablename__ = "product_releases"

    product_sku: Mapped[str] = mapped_column(
        Text, ForeignKey("products.sku", ondelete="CASCADE"), nullable=False
    )
    # Código ISO o código interno de mercado: 'UAE', 'KSA', 'MX', 'ES', 'GLOBAL'
    market_code: Mapped[str] = mapped_column(String(10), nullable=False)

    # Datos locales del mercado
    local_name: Mapped[str | None] = mapped_column(Text)
    local_description: Mapped[str | None] = mapped_column(Text)
    # SKU que usa el distribuidor/canal local (puede diferir del SKU global)
    local_sku: Mapped[str | None] = mapped_column(String(50))
    # UoM de venta local (puede diferir del base_uom global — ej: vende en BOX)
    local_uom: Mapped[str | None] = mapped_column(String(10))

    # Precio de lista local y moneda
    list_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    price_currency: Mapped[str | None] = mapped_column(String(3))

    # Clase fiscal para determinar tasa de impuesto (Pricing M1-01 tax matrix)
    # Ejemplos: 'VAT_5_UAE', 'VAT_15_KSA', 'IVA_16_MX', 'EXEMPT'
    tax_class: Mapped[str | None] = mapped_column(String(50))

    # Estado del release en este mercado
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'draft'"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    released_by: Mapped[UUID | None] = mapped_column(
        UUID_PG, ForeignKey("users.id", ondelete="SET NULL")
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    created_by: Mapped[UUID | None] = mapped_column(
        UUID_PG, ForeignKey("users.id", ondelete="SET NULL")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=text("now()"),
    )

    product: Mapped[Product] = relationship(back_populates="releases")

    __table_args__ = (
        CheckConstraint(
            f"status IN {values_csv(ReleaseStatus)}",
            name="ck_product_releases_status",
        ),
        CheckConstraint(
            "price_currency IS NULL OR length(price_currency) = 3",
            name="ck_product_releases_currency_len",
        ),
        Index(
            "uq_product_releases_sku_market",
            "product_sku",
            "market_code",
            unique=True,
        ),
        Index("idx_product_releases_active", "market_code", "is_active"),
    )


# ---------------------------------------------------------------------------
# DN/NPS reference — equivalencias según ISO 6708 / ASME B36.10M (mig 099)
# ---------------------------------------------------------------------------


class DnNpsReference(Base):
    """Tabla de referencia global DN ↔ NPS ↔ OD de tubería.

    Dato inmutable de norma — no varía por producto ni fabricante.
    Fuente: ISO 6708 (DN) + ASME B36.10M (OD tubería).

    DN (Diamètre Nominal) per ISO 6708 es adimensional: la etiqueta "80"
    no implica que ninguna dimensión mida exactamente 80 mm.
    El OD real de la tubería DN80 es 88.9 mm (≡ NPS 3").
    """

    __tablename__ = "dn_nps_reference"

    dn_nominal: Mapped[str] = mapped_column(
        Text, primary_key=True, comment="Tamaño nominal métrico sin prefijo DN: '80', '100'"
    )
    nps_nominal: Mapped[str] = mapped_column(
        Text, nullable=False, comment="NPS sin comillas: '3', '4', '6'"
    )
    nps_label: Mapped[str] = mapped_column(
        Text, nullable=False, comment="Etiqueta legible: '3\"', '4\"'"
    )
    od_pipe_mm: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 2), comment="OD exterior de tubería según EN 10220 / ASME B36.10M (mm)"
    )
    notes: Mapped[str | None] = mapped_column(Text)

    # Backref desde ProductBoreDimension
    bore_dimensions: Mapped[list[ProductBoreDimension]] = relationship(
        "ProductBoreDimension",
        primaryjoin="DnNpsReference.dn_nominal == foreign(ProductBoreDimension.dn_nominal_ref)",
        viewonly=True,
    )


class ProductBoreDimension(UuidPkMixin, Base):
    """Dimensiones reales de un producto por norma aplicable.

    Un mismo SKU puede declarar dimensiones para múltiples estándares:
    ej. butterfly wafer MTFT_5114 cumple EN 558 Serie 20 Y ASME B16.10 Cl.150.

    El campo `bore_mm` de esta tabla es lo que el spec_viewer llama `dn_real`.
    Las dimensiones varían por estándar (EN vs ASME) y clase de presión (PN16 vs Cl.150).

    Campos clave:
      bore_mm          — diámetro de paso (waterway) — el "dn_real" del spec
      face_to_face_mm  — longitud de construcción (EN 558 / ASME B16.10)
      flange_od_mm     — diámetro exterior de brida (EN 1092 / ASME B16.5)
    """

    __tablename__ = "product_bore_dimensions"

    product_sku: Mapped[str] = mapped_column(
        Text, ForeignKey("products.sku", ondelete="CASCADE"), nullable=False
    )
    # Enlace opcional a la tabla de referencia DN/NPS
    dn_nominal_ref: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("dn_nps_reference.dn_nominal", ondelete="SET NULL"),
        nullable=True,
        comment="FK a dn_nps_reference para obtener OD de tubería y equivalencia NPS",
    )

    # Sistema y norma específica
    standard_system: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="DIN | ASME | AWWA | ISO | JIS | GOST"
    )
    standard_code: Mapped[str] = mapped_column(
        Text, nullable=False, comment="Ej: 'EN 558 Serie 20', 'ASME B16.10 Class 150', 'AWWA C504'"
    )
    pressure_class: Mapped[str | None] = mapped_column(
        String(20), comment="PN6 | PN10 | PN16 | Class 150 | Class 300 | Class 600"
    )

    # Dimensiones reales (todas opcionales — dependen del tipo de válvula)
    bore_mm: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 2), comment="Diámetro de paso en mm — equiv. a dn_real del spec_viewer"
    )
    face_to_face_mm: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 2), comment="Distancia cara a cara según la norma aplicable"
    )
    end_to_end_mm: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 2), comment="Distancia extremo a extremo (incluyendo bridas)"
    )
    flange_od_mm: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 2), comment="Diámetro exterior de brida"
    )
    bolt_circle_mm: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 2), comment="Diámetro del círculo de pernos"
    )
    bolt_count: Mapped[int | None] = mapped_column(Integer, comment="Número de pernos de brida")
    bolt_size: Mapped[str | None] = mapped_column(
        String(16), comment="Tamaño de perno: 'M16', '5/8\"'"
    )

    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        comment="True si este es el estándar de referencia principal del producto",
    )
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    product: Mapped[Product] = relationship(back_populates="bore_dimensions")

    __table_args__ = (
        CheckConstraint(
            "standard_system IN ('DIN','ASME','AWWA','ISO','JIS','GOST')",
            name="ck_bore_dim_system",
        ),
        Index(
            "uq_product_bore_dim_sku_std_pclass",
            "product_sku",
            "standard_code",
            "pressure_class",
            unique=True,
        ),
        Index("idx_product_bore_dim_sku", "product_sku"),
        Index("idx_product_bore_dim_system", "standard_system"),
    )

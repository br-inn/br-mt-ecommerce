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
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.enums import DataQuality, TranslationStatus, values_csv
from app.db.mixins import UuidPkMixin
from app.db.types import UUID_PG, HAS_PGVECTOR

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

    specs: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    dimensions: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    packaging: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    weight: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    weight_unit: Mapped[str | None] = mapped_column(
        String(8), server_default=text("'kg'")
    )
    intrastat_code: Mapped[str | None] = mapped_column(Text)
    erp_name: Mapped[str | None] = mapped_column(Text)

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
    lifecycle_status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'active'::lifecycle_status")
    )
    revision: Mapped[str | None] = mapped_column(Text)
    series: Mapped[str | None] = mapped_column(Text)
    parent_sku: Mapped[str | None] = mapped_column(
        Text, ForeignKey("products.sku", ondelete="SET NULL", name="fk_products_parent_sku")
    )
    is_parent: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    is_variant: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )

    # Technical scalars (solo transversales — los específicos de válvula
    # viven en `specs` JSONB validados por JSON Schema; ver mig. 043).
    size: Mapped[str | None] = mapped_column(Text)
    temp_min_c: Mapped[int | None] = mapped_column(Integer)
    temp_max_c: Mapped[int | None] = mapped_column(Integer)
    pressure_max_bar: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))

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

    translations: Mapped[list["ProductTranslation"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )
    # `assets` — all asset kinds; `images` — backward compat alias (kind='photo' only)
    assets: Mapped[list["ProductAsset"]] = relationship(
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
    product_certifications: Mapped[list["ProductCertification"]] = relationship(  # type: ignore[name-defined]
        "ProductCertification",
        back_populates="product",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    product_applications: Mapped[list["ProductApplication"]] = relationship(  # type: ignore[name-defined]
        "ProductApplication",
        back_populates="product",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # Wave 3 — componentes (materiales por componente, conexiones múltiples).
    materials: Mapped[list["ProductMaterial"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "ProductMaterial",
        back_populates="product",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    connections: Mapped[list["ProductConnection"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "ProductConnection",
        back_populates="product",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # Wave 6 — tech tables (P/T, materials matrix, dimensions by DN).
    tech_tables: Mapped[list["ProductTechTable"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "ProductTechTable",
        back_populates="product",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # Wave 7 — compatibilidades M:N (recambios/accesorios).
    # outgoing: enlaces donde este producto es el "origen".
    # incoming: enlaces donde este producto es el "destino" (viewonly — no mutamos desde aquí).
    compatibilities_outgoing: Mapped[list["ProductCompatibility"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "ProductCompatibility",
        foreign_keys="ProductCompatibility.product_sku",
        back_populates="product",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    compatibilities_incoming: Mapped[list["ProductCompatibility"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "ProductCompatibility",
        foreign_keys="ProductCompatibility.compatible_with_sku",
        back_populates="compatible_with",
        lazy="selectin",
        viewonly=True,
    )

    # Stage 3 — divisiones M:N (selectin para incluir en ProductDetail)
    product_divisions: Mapped[list["ProductDivision"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "ProductDivision",
        back_populates="product",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # ---- Fase B hybrid properties (read-only compat layer) ------------------
    # Permiten que código legacy siga leyendo prod.active / prod.name_en /
    # prod.description_en / prod.marketing_copy_en sin reescribir.
    # En contextos SQL (`Product.active`, `Product.name_en` dentro de select)
    # se traducen a expressions equivalentes — para name_en/description_en/
    # marketing_copy_en se usa un correlated subquery a product_translations
    # con lang='en'.

    @hybrid_property
    def active(self) -> bool:  # noqa: D401 — propiedad-bandera.
        """`True` si lifecycle_status == 'active'. Read-only (escribir en lifecycle_status)."""
        return self.lifecycle_status == "active"

    @active.expression  # type: ignore[no-redef]
    def active(cls):  # noqa: N805 — hybrid expression.
        return cls.lifecycle_status == "active"

    @hybrid_property
    def name_en(self) -> str | None:
        """Lee `name` de la traducción lang='en' si está cargada/disponible."""
        for t in (self.translations or []):
            if t.lang == "en":
                return t.name
        return None

    @name_en.expression  # type: ignore[no-redef]
    def name_en(cls):  # noqa: N805
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
        for t in (self.translations or []):
            if t.lang == "en":
                return t.description
        return None

    @description_en.expression  # type: ignore[no-redef]
    def description_en(cls):  # noqa: N805
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
        for t in (self.translations or []):
            if t.lang == "en":
                return t.marketing_copy
        return None

    @marketing_copy_en.expression  # type: ignore[no-redef]
    def marketing_copy_en(cls):  # noqa: N805
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
    __table_args__ = (
        CheckConstraint(
            f"data_quality IN {values_csv(DataQuality)}",
            name="ck_products_data_quality",
        ),
        Index("idx_products_family", "family"),
        Index("idx_products_brand", "brand"),
        Index("idx_products_specs_gin", "specs", postgresql_using="gin"),
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
    kind: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'photo'")
    )
    # bucket — Supabase Storage bucket name.
    bucket: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'product-images'")
    )
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    original_url: Mapped[str | None] = mapped_column(Text)
    is_primary: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    # position — sort order within (sku, kind).
    position: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
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
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'active'")
    )
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

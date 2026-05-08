"""Product + ProductTranslation + ProductImage.

Notas:
- PK del producto es `sku` TEXT (alineado con architecture §8.4); `internal_id`
  UUID adicional para joins sintéticos (FK desde tablas que prefieran UUID).
- `embedding` se modela placeholder ARRAY(Float) si pgvector no está disponible.
- `data_quality` es `String(16) + CHECK` (ver `enums.py` rationale).
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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.enums import DataQuality, ImageStatus, TranslationStatus, values_csv
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

    name_en: Mapped[str] = mapped_column(Text, nullable=False)
    description_en: Mapped[str | None] = mapped_column(Text)
    marketing_copy_en: Mapped[str | None] = mapped_column(Text)

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

    # Imagen primaria (preview) + auditoría URL externa antes del mirror.
    image_url: Mapped[str | None] = mapped_column(Text)
    image_origin_url: Mapped[str | None] = mapped_column(Text)
    image_status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'missing'")
    )

    data_quality: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'partial'")
    )
    manual_locked_fields: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")
    )
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
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
    images: Mapped[list["ProductImage"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )

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

    __table_args__ = (
        CheckConstraint(
            f"data_quality IN {values_csv(DataQuality)}",
            name="ck_products_data_quality",
        ),
        CheckConstraint(
            "image_status IN ('missing','mirrored','failed')",
            name="ck_products_image_status",
        ),
        Index("idx_products_family", "family"),
        Index("idx_products_brand", "brand"),
        Index(
            "idx_products_active",
            "active",
            postgresql_where=text("active = true"),
        ),
        Index("idx_products_specs_gin", "specs", postgresql_using="gin"),
        Index(
            "idx_products_name_trgm",
            "name_en",
            postgresql_using="gin",
            postgresql_ops={"name_en": "gin_trgm_ops"},
        ),
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


class ProductImage(UuidPkMixin, Base):
    __tablename__ = "product_images"

    sku: Mapped[str] = mapped_column(
        Text, ForeignKey("products.sku", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    original_url: Mapped[str | None] = mapped_column(Text)
    is_primary: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    alt_text: Mapped[str | None] = mapped_column(Text)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    bytes_size: Mapped[int | None] = mapped_column(BigInteger)
    mime_type: Mapped[str | None] = mapped_column(Text)
    hash_sha256: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'active'")
    )
    # Estado del pipeline de mirror (US-1A-02-07 — worker probe_mirror).
    image_status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'pending'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    created_by: Mapped[UUID | None] = mapped_column(
        UUID_PG, ForeignKey("users.id", ondelete="SET NULL")
    )

    product: Mapped[Product] = relationship(back_populates="images")

    __table_args__ = (
        CheckConstraint(
            "status IN ('active','archived','broken')", name="ck_images_status"
        ),
        CheckConstraint(
            f"image_status IN {values_csv(ImageStatus)}",
            name="ck_product_images_image_status",
        ),
        Index("idx_images_sku_role", "sku", "role"),
        Index("idx_product_images_hash", "hash_sha256"),
    )

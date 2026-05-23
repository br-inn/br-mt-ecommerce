"""ORM models — vocabularios curados.

- Wave 4: Certification, Application + M:N junctions
- Stage 1 Opción C (mig. 042): Brand, Family, Subfamily, ProductType — taxonomía
  jerárquica (family → subfamily → product_type) + brand orthogonal. FK desde
  ``products`` añadidas como nullable durante transición; promover a NOT NULL
  en Stage 2 una vez consumidores migrados.
- Stage 3 (migs. 044/045/046): Division (M:N), Series rica (tier, pressure,
  banner, certs default, translations, divisions), Material vocab.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    ARRAY,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import UuidPkMixin
from app.db.types import UUID_PG


class Certification(UuidPkMixin, Base):
    """Certificación homologada — catálogo curado por admin."""

    __tablename__ = "certifications"

    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    issued_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    scope: Mapped[str | None] = mapped_column(Text, nullable=True)
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    # Reverse side — products that carry this certification.
    product_certifications: Mapped[list["ProductCertification"]] = relationship(
        back_populates="certification", cascade="all, delete-orphan"
    )


class Application(UuidPkMixin, Base):
    """Aplicación / uso de producto — catálogo curado por admin."""

    __tablename__ = "applications"

    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    # Reverse side — products that have this application.
    product_applications: Mapped[list["ProductApplication"]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )


class ProductCertification(Base):
    """M:N junction: products ↔ certifications (con metadatos de certificado).

    Fase 5 — polymorphic owner:
        Para soportar certificaciones a nivel ``variant`` o ``series`` (no solo
        producto concreto), se añadieron las columnas ``owner_type`` y
        ``owner_id`` en la migración 20260514_064.

    **Compat layer:** ``product_sku`` se mantiene NOT NULL y como parte de la
    PK existente. Para owner_type='product', ``owner_id == product_sku`` (los
    métodos de servicio garantizan esta sincronía). Las filas con owner_type
    ∈ {variant, series} requieren una migración futura que relaje el NOT NULL
    de ``product_sku`` y deje de propagar valores. Por ahora todo flujo legacy
    funciona sin cambios.
    """

    __tablename__ = "product_certifications"

    product_sku: Mapped[str] = mapped_column(
        Text,
        ForeignKey("products.sku", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    certification_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("certifications.id", ondelete="RESTRICT"),
        primary_key=True,
        nullable=False,
    )
    # Fase 5 — polymorphic owner. Para filas legacy, owner_type='product' +
    # owner_id=product_sku (backfilled en migración 064).
    owner_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'product'"),
    )
    owner_id: Mapped[str] = mapped_column(Text, nullable=False)

    certificate_pdf_asset_id: Mapped[UUID | None] = mapped_column(UUID_PG, nullable=True)
    obtained_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    expires_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    certification: Mapped["Certification"] = relationship(back_populates="product_certifications")
    product: Mapped["Product"] = relationship(  # type: ignore[name-defined]
        "Product",
        back_populates="product_certifications",
    )

    __table_args__ = (
        Index("idx_product_certifications_cert", "certification_id"),
        Index("ix_product_certifications_owner", "owner_type", "owner_id"),
        UniqueConstraint(
            "owner_type",
            "owner_id",
            "certification_id",
            name="uq_product_certifications_owner",
        ),
    )


class ProductApplication(Base):
    """M:N junction: products ↔ applications (con posición y flag primario)."""

    __tablename__ = "product_applications"

    product_sku: Mapped[str] = mapped_column(
        Text,
        ForeignKey("products.sku", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    application_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("applications.id", ondelete="RESTRICT"),
        primary_key=True,
        nullable=False,
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    application: Mapped["Application"] = relationship(back_populates="product_applications")
    product: Mapped["Product"] = relationship(  # type: ignore[name-defined]
        "Product",
        back_populates="product_applications",
    )

    __table_args__ = (
        Index("idx_product_applications_app", "application_id"),
        Index(
            "idx_product_applications_primary",
            "product_sku",
            postgresql_where=text("is_primary = true"),
        ),
    )


# ---------------------------------------------------------------------------
# Stage 1 Opción C — taxonomía: brand + family → subfamily → product_type
# ---------------------------------------------------------------------------


class Brand(UuidPkMixin, Base):
    """Marca comercial — orthogonal a la jerarquía family/subfamily/type."""

    __tablename__ = "brands"

    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    website_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (Index("idx_brands_active", "active"),)


class Family(UuidPkMixin, Base):
    """Familia de producto — nivel superior de la taxonomía."""

    __tablename__ = "families"

    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    subfamilies: Mapped[list[Subfamily]] = relationship(
        back_populates="family",
        cascade="all, delete-orphan",
        order_by="Subfamily.sort_order",
    )

    __table_args__ = (Index("idx_families_active", "active"),)


class Subfamily(UuidPkMixin, Base):
    """Subfamilia — child de Family. Code único dentro de cada family."""

    __tablename__ = "subfamilies"

    family_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("families.id", ondelete="RESTRICT"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    family: Mapped[Family] = relationship(back_populates="subfamilies")
    product_types: Mapped[list[ProductType]] = relationship(
        back_populates="subfamily",
        cascade="all, delete-orphan",
        order_by="ProductType.sort_order",
    )

    __table_args__ = (
        UniqueConstraint("family_id", "code", name="uq_subfamilies_family_code"),
        Index("idx_subfamilies_family", "family_id"),
        Index("idx_subfamilies_active", "active"),
    )


class ProductType(UuidPkMixin, Base):
    """Tipo concreto de producto — child de Subfamily.

    Code único dentro de cada subfamily (ej. ``valve > ball > 2_way_1piece``).
    """

    __tablename__ = "product_types"

    subfamily_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("subfamilies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    subfamily: Mapped[Subfamily] = relationship(back_populates="product_types")

    __table_args__ = (
        UniqueConstraint("subfamily_id", "code", name="uq_product_types_subfamily_code"),
        Index("idx_product_types_subfamily", "subfamily_id"),
        Index("idx_product_types_active", "active"),
    )


# ---------------------------------------------------------------------------
# Stage 3 — Division (M:N), Series (rica), Material (vocab)
# ---------------------------------------------------------------------------


class Division(UuidPkMixin, Base):
    """División comercial / canal de catálogo (Hidrosanitario, Industrial, …).

    Eje ortogonal: un mismo SKU puede vivir en varias divisiones (M:N vía
    ``product_divisions``). NO es nivel jerárquico de family/subfamily/type.
    """

    __tablename__ = "divisions"

    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (Index("idx_divisions_active", "active"),)


class ProductDivision(Base):
    """M:N junction: products ↔ divisions."""

    __tablename__ = "product_divisions"

    product_sku: Mapped[str] = mapped_column(
        Text,
        ForeignKey("products.sku", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    division_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("divisions.id", ondelete="RESTRICT"),
        primary_key=True,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    product: Mapped["Product"] = relationship(  # type: ignore[name-defined]
        "Product", back_populates="product_divisions"
    )
    division: Mapped[Division] = relationship()

    __table_args__ = (Index("idx_product_divisions_division", "division_id"),)


class SeriesTier(UuidPkMixin, Base):
    """Tier comercial (PLATINUM, GOLD, SILVER, BRONZE, N/A)."""

    __tablename__ = "series_tiers"

    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    rank: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text("99"))
    display_color: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class Series(UuidPkMixin, Base):
    """Serie comercial — entidad rica con tier, pressure, banner, certs default."""

    __tablename__ = "series"

    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name_en: Mapped[str] = mapped_column(Text, nullable=False)
    tier_id: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("series_tiers.id", ondelete="RESTRICT"),
        nullable=True,
    )
    pressure_rating_pn: Mapped[int | None] = mapped_column(Integer, nullable=True)
    temperature_min_c: Mapped[int | None] = mapped_column(Integer, nullable=True)
    temperature_max_c: Mapped[int | None] = mapped_column(Integer, nullable=True)
    banner_color: Mapped[str | None] = mapped_column(Text, nullable=True)
    hero_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    description_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    bullets_en: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")
    )
    features_tags: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    thread_standard: Mapped[str | None] = mapped_column(
        String(32), nullable=True, comment="ISO 228-1 (BSP) | ISO 7/1 (BSPT) | ASME B1.20.1 (NPT)"
    )
    revision: Mapped[str | None] = mapped_column(Text, nullable=True)
    revision_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    tier: Mapped[SeriesTier | None] = relationship()
    translations: Mapped[list["SeriesTranslation"]] = relationship(
        back_populates="series", cascade="all, delete-orphan"
    )
    series_divisions: Mapped[list["SeriesDivision"]] = relationship(
        back_populates="series", cascade="all, delete-orphan"
    )
    series_certifications: Mapped[list["SeriesCertification"]] = relationship(
        back_populates="series", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_series_tier", "tier_id"),
        Index("idx_series_active", "active"),
        Index("idx_series_pressure_rating", "pressure_rating_pn"),
    )


class SeriesTranslation(Base):
    """Traducciones por idioma — name, description, bullets."""

    __tablename__ = "series_translations"

    series_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("series.id", ondelete="CASCADE"),
        primary_key=True,
    )
    lang: Mapped[str] = mapped_column(String(2), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    bullets: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    series: Mapped[Series] = relationship(back_populates="translations")


class SeriesDivision(Base):
    """M:N junction — qué series aparecen en qué catálogo (división)."""

    __tablename__ = "series_divisions"

    series_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("series.id", ondelete="CASCADE"),
        primary_key=True,
    )
    division_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("divisions.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    series: Mapped[Series] = relationship(back_populates="series_divisions")
    division: Mapped[Division] = relationship()

    __table_args__ = (Index("idx_series_divisions_division", "division_id"),)


class SeriesCertification(Base):
    """M:N junction — paquete default de certificaciones por serie."""

    __tablename__ = "series_certifications"

    series_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("series.id", ondelete="CASCADE"),
        primary_key=True,
    )
    certification_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("certifications.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    series: Mapped[Series] = relationship(back_populates="series_certifications")
    certification: Mapped[Certification] = relationship()

    __table_args__ = (Index("idx_series_certifications_cert", "certification_id"),)


class Material(UuidPkMixin, Base):
    """Vocabulario curado del agrupador material (Latón, Inox, Fundición, …).

    NO es nivel jerárquico — es agrupador visual del PDF (1.1 ACERO INOX,
    1.2 LATÓN, …). Coexiste con la columna TEXT ``products.material``.
    """

    __tablename__ = "materials"

    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    family_kind: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (Index("idx_materials_active", "active"),)

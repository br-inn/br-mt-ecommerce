"""Pydantic V2 schemas — vocabularios curados.

- Wave 4: Certifications, Applications + product link payloads
- Stage 1 Opción C: Brand, Family, Subfamily, ProductType (taxonomía)

Convenciones: Pydantic v2 ConfigDict, from_attributes=True para ORM.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CertificationOwnerType(str, Enum):
    """Tipo de owner polymorphic para certificaciones (Fase 5).

    Default 'product' preserva compat con clientes legacy. Las certificaciones
    pueden adjuntarse a un product, variant o series.
    """

    product = "product"
    variant = "variant"
    series = "series"


# ---------------------------------------------------------------------------
# Certification
# ---------------------------------------------------------------------------
class CertificationBase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    code: str = Field(min_length=1, max_length=32, description="Código único, e.g. 'CE', 'WRAS'.")
    name: str = Field(min_length=1, max_length=256)
    issued_by: str | None = Field(default=None, max_length=256)
    scope: str | None = Field(default=None, max_length=512)
    logo_url: str | None = Field(default=None, max_length=1024)
    active: bool = True


class CertificationCreate(CertificationBase):
    pass


class CertificationPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=256)
    issued_by: str | None = None
    scope: str | None = None
    logo_url: str | None = None
    active: bool | None = None


class CertificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    issued_by: str | None
    scope: str | None
    logo_url: str | None
    active: bool
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------
class ApplicationBase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    code: str = Field(min_length=1, max_length=64, description="Código único, e.g. 'water', 'gas'.")
    name: str = Field(min_length=1, max_length=256)
    description: str | None = Field(default=None, max_length=1024)
    active: bool = True


class ApplicationCreate(ApplicationBase):
    pass


class ApplicationPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=256)
    description: str | None = None
    active: bool | None = None


class ApplicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    description: str | None
    active: bool
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Product ↔ Certification link
# ---------------------------------------------------------------------------
class ProductCertificationLink(BaseModel):
    """Payload para enlazar un producto a una certificación.

    Fase 5 — admite owner_type opcional (default 'product') + owner_id opcional.
    Si no se pasa owner_id, el servicio asume owner_id=product_sku (compat).
    """

    model_config = ConfigDict(extra="forbid")

    certification_id: UUID
    # Fase 5 — polymorphic owner. owner_id se autorrellena desde product_sku
    # cuando owner_type='product' y el caller no lo especifica.
    owner_type: CertificationOwnerType = CertificationOwnerType.product
    owner_id: str | None = Field(default=None, max_length=64)
    certificate_pdf_asset_id: UUID | None = None
    obtained_at: date | None = None
    expires_at: date | None = None
    notes: str | None = Field(default=None, max_length=1024)


class ProductCertificationResponse(BaseModel):
    """Respuesta desnormalizada: datos de la cert + metadatos del link."""

    model_config = ConfigDict(from_attributes=True)

    # Cert details
    certification_id: UUID
    code: str
    name: str
    issued_by: str | None
    scope: str | None
    logo_url: str | None

    # Link metadata
    certificate_pdf_asset_id: UUID | None
    obtained_at: date | None
    expires_at: date | None
    notes: str | None
    created_at: datetime
    # Fase 5 — polymorphic owner.
    owner_type: CertificationOwnerType = CertificationOwnerType.product
    owner_id: str | None = None

    @classmethod
    def from_link(cls, link: object) -> "ProductCertificationResponse":
        """Construir desde un row ProductCertification (con cert eager-loaded).

        Fase 5 — extrae owner_type/owner_id defensivamente; si el atributo no
        está presente o no es un string válido, cae a defaults ('product' +
        product_sku) para preservar compat con tests legacy y rows pre-064.
        """
        cert = link.certification  # type: ignore[attr-defined]

        raw_owner_type = getattr(link, "owner_type", None)
        owner_type: CertificationOwnerType = CertificationOwnerType.product
        if isinstance(raw_owner_type, str):
            try:
                owner_type = CertificationOwnerType(raw_owner_type)
            except ValueError:
                owner_type = CertificationOwnerType.product
        elif isinstance(raw_owner_type, CertificationOwnerType):
            owner_type = raw_owner_type

        raw_owner_id = getattr(link, "owner_id", None)
        owner_id: str | None
        if isinstance(raw_owner_id, str):
            owner_id = raw_owner_id
        else:
            # Compat fallback: usar product_sku si está disponible.
            raw_sku = getattr(link, "product_sku", None)
            owner_id = raw_sku if isinstance(raw_sku, str) else None

        return cls(
            certification_id=link.certification_id,  # type: ignore[attr-defined]
            code=cert.code,
            name=cert.name,
            issued_by=cert.issued_by,
            scope=cert.scope,
            logo_url=cert.logo_url,
            certificate_pdf_asset_id=link.certificate_pdf_asset_id,  # type: ignore[attr-defined]
            obtained_at=link.obtained_at,  # type: ignore[attr-defined]
            expires_at=link.expires_at,  # type: ignore[attr-defined]
            notes=link.notes,  # type: ignore[attr-defined]
            created_at=link.created_at,  # type: ignore[attr-defined]
            owner_type=owner_type,
            owner_id=owner_id,
        )


# ---------------------------------------------------------------------------
# Product ↔ Application link
# ---------------------------------------------------------------------------
class ProductApplicationLink(BaseModel):
    """Payload para enlazar un producto a una aplicación."""

    model_config = ConfigDict(extra="forbid")

    application_id: UUID
    is_primary: bool = False
    position: int = Field(default=0, ge=0, le=32767)


class ProductApplicationResponse(BaseModel):
    """Respuesta desnormalizada: datos de la app + metadatos del link."""

    model_config = ConfigDict(from_attributes=True)

    # App details
    application_id: UUID
    code: str
    name: str
    description: str | None

    # Link metadata
    is_primary: bool
    position: int
    created_at: datetime

    @classmethod
    def from_link(cls, link: object) -> "ProductApplicationResponse":
        """Construir desde un row ProductApplication (con application eager-loaded)."""
        app = link.application  # type: ignore[attr-defined]
        return cls(
            application_id=link.application_id,  # type: ignore[attr-defined]
            code=app.code,
            name=app.name,
            description=app.description,
            is_primary=link.is_primary,  # type: ignore[attr-defined]
            position=link.position,  # type: ignore[attr-defined]
            created_at=link.created_at,  # type: ignore[attr-defined]
        )


# ---------------------------------------------------------------------------
# Stage 1 Opción C — Taxonomía: Brand, Family, Subfamily, ProductType
# ---------------------------------------------------------------------------

# Reglas de naming compartidas (snake_case lowercase, dígitos, guión bajo).
_CODE_PATTERN = r"^[a-z][a-z0-9_]{0,63}$"


# ---- Brand ---------------------------------------------------------------
class BrandBase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    code: str = Field(
        min_length=1,
        max_length=64,
        pattern=_CODE_PATTERN,
        description="Código único snake_case lowercase, e.g. 'mt'.",
    )
    name: str = Field(min_length=1, max_length=256)
    logo_url: str | None = Field(default=None, max_length=1024)
    website_url: str | None = Field(default=None, max_length=1024)
    active: bool = True


class BrandCreate(BrandBase):
    pass


class BrandPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=256)
    logo_url: str | None = None
    website_url: str | None = None
    active: bool | None = None


class BrandResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    logo_url: str | None
    website_url: str | None
    active: bool
    created_at: datetime
    updated_at: datetime


# ---- Family --------------------------------------------------------------
class FamilyBase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    code: str = Field(
        min_length=1,
        max_length=64,
        pattern=_CODE_PATTERN,
        description="Código único, e.g. 'valve', 'elbow'.",
    )
    name: str = Field(min_length=1, max_length=256)
    description: str | None = Field(default=None, max_length=1024)
    sort_order: int = Field(default=0, ge=0, le=32767)
    active: bool = True


class FamilyCreate(FamilyBase):
    pass


class FamilyPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=256)
    description: str | None = None
    sort_order: int | None = Field(default=None, ge=0, le=32767)
    active: bool | None = None


class FamilyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    description: str | None
    sort_order: int
    active: bool
    created_at: datetime
    updated_at: datetime


# ---- Subfamily -----------------------------------------------------------
class SubfamilyBase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    family_id: UUID
    code: str = Field(min_length=1, max_length=64, pattern=_CODE_PATTERN)
    name: str = Field(min_length=1, max_length=256)
    description: str | None = Field(default=None, max_length=1024)
    sort_order: int = Field(default=0, ge=0, le=32767)
    active: bool = True


class SubfamilyCreate(SubfamilyBase):
    pass


class SubfamilyPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=256)
    description: str | None = None
    sort_order: int | None = Field(default=None, ge=0, le=32767)
    active: bool | None = None


class SubfamilyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    family_id: UUID
    code: str
    name: str
    description: str | None
    sort_order: int
    active: bool
    created_at: datetime
    updated_at: datetime


# ---- ProductType ---------------------------------------------------------
class ProductTypeBase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    subfamily_id: UUID
    code: str = Field(min_length=1, max_length=64, pattern=_CODE_PATTERN)
    name: str = Field(min_length=1, max_length=256)
    description: str | None = Field(default=None, max_length=1024)
    sort_order: int = Field(default=0, ge=0, le=32767)
    active: bool = True


class ProductTypeCreate(ProductTypeBase):
    pass


class ProductTypePatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=256)
    description: str | None = None
    sort_order: int | None = Field(default=None, ge=0, le=32767)
    active: bool | None = None


class ProductTypeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    subfamily_id: UUID
    code: str
    name: str
    description: str | None
    sort_order: int
    active: bool
    created_at: datetime
    updated_at: datetime


# ---- Tree response (jerarquía completa para wizard / UI) -----------------
class SubfamilyTreeNode(SubfamilyResponse):
    """Subfamily + sus product_types anidados."""

    types: list[ProductTypeResponse] = Field(default_factory=list)


class FamilyTreeNode(FamilyResponse):
    """Family + sus subfamilies (con types anidados)."""

    subfamilies: list[SubfamilyTreeNode] = Field(default_factory=list)


class TaxonomyTreeResponse(BaseModel):
    """Snapshot completo de la taxonomía: families → subfamilies → types."""

    model_config = ConfigDict(from_attributes=True)

    families: list[FamilyTreeNode]


# ---------------------------------------------------------------------------
# Stage 3 — Division
# ---------------------------------------------------------------------------
class DivisionBase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    code: str = Field(
        min_length=1,
        max_length=64,
        pattern=_CODE_PATTERN,
        description="Código único, e.g. 'hidrosanitario', 'industrial'.",
    )
    name: str = Field(min_length=1, max_length=256)
    description: str | None = Field(default=None, max_length=1024)
    sort_order: int = Field(default=0, ge=0, le=32767)
    active: bool = True


class DivisionCreate(DivisionBase):
    pass


class DivisionPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=256)
    description: str | None = None
    sort_order: int | None = Field(default=None, ge=0, le=32767)
    active: bool | None = None


class DivisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    description: str | None
    sort_order: int
    active: bool
    created_at: datetime
    updated_at: datetime


class ProductDivisionLink(BaseModel):
    """Payload mínimo para enlazar product ↔ division."""

    model_config = ConfigDict(extra="forbid")

    division_id: UUID


class ProductDivisionResponse(BaseModel):
    """Respuesta desnormalizada con datos de la división."""

    model_config = ConfigDict(from_attributes=True)

    division_id: UUID
    code: str
    name: str
    created_at: datetime

    @classmethod
    def from_link(cls, link: object) -> "ProductDivisionResponse":
        d = link.division  # type: ignore[attr-defined]
        return cls(
            division_id=link.division_id,  # type: ignore[attr-defined]
            code=d.code,
            name=d.name,
            created_at=link.created_at,  # type: ignore[attr-defined]
        )


# ---------------------------------------------------------------------------
# Stage 3 — SeriesTier (vocab cerrado)
# ---------------------------------------------------------------------------
class SeriesTierBase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    code: str = Field(min_length=1, max_length=32, pattern=_CODE_PATTERN)
    name: str = Field(min_length=1, max_length=64)
    rank: int = Field(default=99, ge=1, le=99)
    display_color: str | None = Field(default=None, max_length=16)
    active: bool = True


class SeriesTierCreate(SeriesTierBase):
    pass


class SeriesTierPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=64)
    rank: int | None = Field(default=None, ge=1, le=99)
    display_color: str | None = None
    active: bool | None = None


class SeriesTierResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    rank: int
    display_color: str | None
    active: bool
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Stage 3 — Series (rica) + translations + junctions
# ---------------------------------------------------------------------------
class SeriesBase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    code: str = Field(
        min_length=1,
        max_length=64,
        pattern=_CODE_PATTERN,
        description="Código único, e.g. 'pn40_platinum', 'mt_press'.",
    )
    name_en: str = Field(min_length=1, max_length=256)
    tier_id: UUID | None = None
    pressure_rating_pn: int | None = Field(default=None, ge=0, le=10000)
    temperature_min_c: int | None = Field(default=None, ge=-273, le=2000)
    temperature_max_c: int | None = Field(default=None, ge=-273, le=2000)
    banner_color: str | None = Field(default=None, max_length=32)
    hero_image_url: str | None = Field(default=None, max_length=2048)
    description_en: str | None = Field(default=None, max_length=4000)
    bullets_en: list[str] = Field(default_factory=list)
    features_tags: list[str] = Field(default_factory=list)
    sort_order: int = Field(default=0, ge=0, le=32767)
    active: bool = True


class SeriesCreate(SeriesBase):
    pass


class SeriesPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name_en: str | None = Field(default=None, min_length=1, max_length=256)
    tier_id: UUID | None = None
    pressure_rating_pn: int | None = Field(default=None, ge=0, le=10000)
    temperature_min_c: int | None = Field(default=None, ge=-273, le=2000)
    temperature_max_c: int | None = Field(default=None, ge=-273, le=2000)
    banner_color: str | None = None
    hero_image_url: str | None = None
    description_en: str | None = None
    bullets_en: list[str] | None = None
    features_tags: list[str] | None = None
    sort_order: int | None = Field(default=None, ge=0, le=32767)
    active: bool | None = None


class SeriesResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name_en: str
    tier_id: UUID | None
    pressure_rating_pn: int | None
    temperature_min_c: int | None
    temperature_max_c: int | None
    banner_color: str | None
    hero_image_url: str | None
    description_en: str | None
    bullets_en: list[str]
    features_tags: list[str]
    sort_order: int
    active: bool
    created_at: datetime
    updated_at: datetime
    thread_standard: str | None = None
    revision: str | None = None
    revision_date: date | None = None


class SeriesTranslationUpsert(BaseModel):
    """Payload para crear/actualizar una traducción de serie."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    lang: str = Field(min_length=2, max_length=2, pattern=r"^(es|ar|en)$")
    name: str = Field(min_length=1, max_length=256)
    description: str | None = Field(default=None, max_length=4000)
    bullets: list[str] = Field(default_factory=list)


class SeriesTranslationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    series_id: UUID
    lang: str
    name: str
    description: str | None
    bullets: list[str]
    created_at: datetime
    updated_at: datetime


class SeriesDivisionLink(BaseModel):
    model_config = ConfigDict(extra="forbid")

    division_id: UUID


class SeriesCertificationLink(BaseModel):
    model_config = ConfigDict(extra="forbid")

    certification_id: UUID


# ---------------------------------------------------------------------------
# Stage 3 — Material (vocab)
# ---------------------------------------------------------------------------
class MaterialBase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    code: str = Field(
        min_length=1,
        max_length=64,
        pattern=_CODE_PATTERN,
        description="Código único, e.g. 'laton', 'acero_inoxidable'.",
    )
    name: str = Field(min_length=1, max_length=256)
    family_kind: str | None = Field(
        default=None,
        max_length=32,
        description="Agrupador grueso: 'metal', 'polymer', 'composite'.",
    )
    notes: str | None = Field(default=None, max_length=1024)
    sort_order: int = Field(default=0, ge=0, le=32767)
    active: bool = True


class MaterialCreate(MaterialBase):
    pass


class MaterialPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=256)
    family_kind: str | None = Field(default=None, max_length=32)
    notes: str | None = None
    sort_order: int | None = Field(default=None, ge=0, le=32767)
    active: bool | None = None


class MaterialResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    family_kind: str | None
    notes: str | None
    sort_order: int
    active: bool
    created_at: datetime
    updated_at: datetime

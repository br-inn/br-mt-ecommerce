"""Pydantic V2 schemas para Products / Translations / Images.

Alineado con `_bmad-output/planning-artifacts/mt-api-contract-openapi.yaml`
(tags Products / ProductTranslations / ProductImages).

Notas de diseño:
- Pydantic V2 con `model_config = ConfigDict(...)`.
- Validators para SKU regex, DN/PN whitelisted, lang ISO 639-1, MIME, etc.
- `from_attributes=True` para mapear directo desde modelos SQLAlchemy.
- Los schemas de respuesta NO exponen embeddings (Sprint 2+).
- Stage 2 (mig. 043) movió valve scalars (manufacturing_method, actuator, kv,
  kv2, torque_nm, iso5211_interface) a specs JSONB validados por JSON Schema.
  dn_real ≡ dn (decisión usuario 2026-05-11) — no se expone como campo separado.
"""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    computed_field,
    field_validator,
    model_validator,
)

from app.schemas.product_models import ProductModelResponse

# Wave 1: import asset schemas — must be before ProductDetail definition.
from app.schemas.assets import (
    ProductAssetConfirmRequest,
    ProductAssetResponse,
    ProductAssetUploadRequest,
)

# Backward-compat aliases — deprecated, will be removed in Wave 2.
ProductImageResponse = ProductAssetResponse
ProductImageUploadRequest = ProductAssetUploadRequest
ProductImageConfirmRequest = ProductAssetConfirmRequest

# ---------------------------------------------------------------------------
# Constants — reglas de validación
# ---------------------------------------------------------------------------
# SKU: prefijo MT + family token + número (ej. MT-V-038, MT-FT-12345). Permitimos
# alfanuméricos en mayúsculas + guiones; min 3, max 64.
SKU_REGEX = r"^[A-Z0-9][A-Z0-9\-_]{2,63}$"

# DN: tamaños nominales típicos (mm). PN: presiones nominales (bar).
# Wave 10 fix: BD guarda valor numérico ("15", "20") sin prefijo.
# El validator acepta:
#   - forma canónica numérica: "15", "DN15" (compat) — ambas se normalizan a "15"
#   - mismo para PN: "16", "PN16" → "16"
# Esto desbloquea los filtros DN/PN del catálogo que antes daban 0 resultados.
ALLOWED_DN: frozenset[str] = frozenset(
    {
        "8",
        "10",
        "15",
        "20",
        "25",
        "32",
        "40",
        "50",
        "65",
        "80",
        "100",
        "125",
        "150",
        "200",
        "250",
        "300",
    }
)
ALLOWED_PN: frozenset[str] = frozenset({"6", "10", "16", "20", "25", "30", "40", "63", "100"})
ALLOWED_WEIGHT_UNITS: frozenset[str] = frozenset({"kg", "g", "lb"})
ALLOWED_LANGS: frozenset[str] = frozenset({"es", "ar"})  # `en` es base, no se traduce
ALLOWED_DATA_QUALITY: frozenset[str] = frozenset(
    {"complete", "partial", "blocked", "migrated_demo"}
)
ALLOWED_TRANSLATION_STATUS: frozenset[str] = frozenset({"pending", "draft", "approved"})
ALLOWED_IMAGE_MIME: frozenset[str] = frozenset(
    {"image/jpeg", "image/png", "image/webp", "image/avif"}
)
# Wave 2 — vocabulario controlado de lifecycle.
ALLOWED_LIFECYCLE_STATUS: frozenset[str] = frozenset(
    {"draft", "in_review", "active", "deprecated", "replaced", "discontinued"}
)
ALLOWED_MARKETS: frozenset[str] = frozenset({"UAE", "KSA", "MX", "ES", "GLOBAL", "US", "EU"})
ALLOWED_RELEASE_STATUS: frozenset[str] = frozenset({"draft", "active", "suspended", "discontinued"})
# Wave 2 — métodos de fabricación más comunes (no exhaustivo, validación blanda).
ALLOWED_MANUFACTURING_METHOD: frozenset[str] = frozenset(
    {"forged", "cast", "machined", "welded", "molded", "extruded", "stamped", "sintered"}
)
# Wave 2 — tipos de accionador.
ALLOWED_ACTUATOR: frozenset[str] = frozenset(
    {"lever", "handwheel", "electric", "pneumatic", "hydraulic", "gear", "manual"}
)


# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------
SkuStr = Annotated[
    str,
    StringConstraints(min_length=3, max_length=64, pattern=SKU_REGEX, strip_whitespace=True),
]
LangStr = Annotated[
    str,
    StringConstraints(min_length=2, max_length=2, pattern=r"^(es|ar)$"),
]


# ---------------------------------------------------------------------------
# Product — base / create / patch / response
# ---------------------------------------------------------------------------
class ProductBase(BaseModel):
    """Campos comunes — heredados por Create/Patch/Response.

    Fase B (mig 065): los campos textuales en inglés (``name_en``,
    ``description_en``, ``marketing_copy_en``) y ``tags`` se eliminaron del
    schema base — ahora viven en ``product_translations(lang='en')`` y en los
    vocabularios M:N respectivamente. Para crear un producto, las traducciones
    se gestionan vía ``ProductService.upsert_translation``.
    Fase B (mig 066): ``active`` boolean eliminado — derivable de
    ``lifecycle_status='active'``; ProductResponse lo expone como
    ``computed_field`` read-only.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    family: str = Field(min_length=1, max_length=64)
    subfamily: str | None = Field(default=None, max_length=64)
    type: str | None = Field(default=None, max_length=64)
    material: str | None = Field(default=None, max_length=64)
    dn: str | None = Field(default=None, max_length=8)
    pn: str | None = Field(default=None, max_length=8)
    connection: str | None = Field(default=None, max_length=64)
    brand: str | None = Field(default=None, max_length=64)
    specs: dict[str, Any] = Field(default_factory=dict)
    dimensions: dict[str, Any] = Field(default_factory=dict)
    weight: Decimal | None = Field(default=None, ge=0, le=Decimal("99999999.9999"))
    weight_unit: str | None = Field(default=None, max_length=8)
    packaging: dict[str, Any] = Field(default_factory=dict)
    intrastat_code: str | None = Field(default=None, max_length=16)
    erp_name: str | None = Field(default=None, max_length=128)
    data_quality: str = Field(default="partial")

    # ---- Wave 2: lifecycle / identity --------------------------------------
    lifecycle_status: str = Field(default="active")
    revision: str | None = Field(default=None, max_length=32)
    series: str | None = Field(default=None, max_length=64)
    parent_sku: str | None = Field(default=None, max_length=64)
    is_parent: bool = False
    is_variant: bool = False

    # ---- Wave 2: technical scalars (sólo transversales) --------------------
    # Stage 2 (mig. 043) movió valve scalars a specs JSONB; dn_real ≡ dn
    # (decisión usuario 2026-05-11) → dn_real no se expone aquí.
    size: str | None = Field(default=None, max_length=64)
    temp_min_c: int | None = Field(default=None, ge=-273, le=2000)
    temp_max_c: int | None = Field(default=None, ge=-273, le=2000)
    pressure_max_bar: Decimal | None = Field(default=None, ge=0, le=Decimal("9999.99"))

    # ---- Wave 2: editorial / SEO -------------------------------------------
    # Fase B (mig 065): `tags` dropeado; usar vocabularios M:N
    # (product_certifications, product_applications).
    video_url: str | None = Field(default=None, max_length=2048)
    external_url: str | None = Field(default=None, max_length=2048)

    @field_validator("lifecycle_status")
    @classmethod
    def _validate_lifecycle(cls, v: str) -> str:
        if v not in ALLOWED_LIFECYCLE_STATUS:
            raise ValueError(
                f"lifecycle_status inválido: {v}; permitidos: {sorted(ALLOWED_LIFECYCLE_STATUS)}"
            )
        return v

    @model_validator(mode="after")
    def _validate_temp_range(self) -> "ProductBase":
        if (
            self.temp_min_c is not None
            and self.temp_max_c is not None
            and self.temp_max_c < self.temp_min_c
        ):
            raise ValueError("temp_max_c debe ser >= temp_min_c")
        return self

    @field_validator("dn")
    @classmethod
    def _validate_dn(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.upper()
        if v.startswith("DN"):
            v = v[2:]
        if v not in ALLOWED_DN:
            raise ValueError(f"dn inválido: {v}; permitidos: {sorted(ALLOWED_DN)}")
        return v

    @field_validator("pn")
    @classmethod
    def _validate_pn(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.upper()
        if v.startswith("PN"):
            v = v[2:]
        if v not in ALLOWED_PN:
            raise ValueError(f"pn inválido: {v}; permitidos: {sorted(ALLOWED_PN)}")
        return v

    @field_validator("weight_unit")
    @classmethod
    def _validate_weight_unit(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if v not in ALLOWED_WEIGHT_UNITS:
            raise ValueError(
                f"weight_unit inválido: {v}; permitidos: {sorted(ALLOWED_WEIGHT_UNITS)}"
            )
        return v

    @field_validator("data_quality")
    @classmethod
    def _validate_data_quality(cls, v: str) -> str:
        if v not in ALLOWED_DATA_QUALITY:
            raise ValueError(
                f"data_quality inválido: {v}; permitidos: {sorted(ALLOWED_DATA_QUALITY)}"
            )
        return v


class ProductCreate(ProductBase):
    """Request para POST /products."""

    sku: SkuStr = Field(description="SKU canónico (PK). Mayúsculas + dígitos + guiones.")

    # ---- Stage 3 (Wave 11): catalog hierarchy refinement (CREATE) ---------
    series_id: UUID | None = None
    material_id: UUID | None = None
    display_pair_sku: str | None = Field(default=None, max_length=64)
    division_codes: list[str] = Field(
        default_factory=list,
        description=(
            "Divisiones a las que pertenece este SKU (M:N). "
            "Si vacío, no se enlaza a ninguna división."
        ),
    )


class ProductPatch(BaseModel):
    """Request para PATCH /products/{sku} — todos opcionales.

    Fase B (mig 065/066): se eliminaron campos legacy (name_en,
    description_en, marketing_copy_en, tags, active). Para editar textos en
    inglés usar PATCH /products/{sku}/translations/en. Para inactivar usar
    lifecycle_status='deprecated'.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    family: str | None = Field(default=None, min_length=1, max_length=64)
    subfamily: str | None = Field(default=None, max_length=64)
    type: str | None = Field(default=None, max_length=64)
    material: str | None = Field(default=None, max_length=64)
    dn: str | None = Field(default=None, max_length=8)
    pn: str | None = Field(default=None, max_length=8)
    connection: str | None = Field(default=None, max_length=64)
    brand: str | None = Field(default=None, max_length=64)
    # M1-08 (mig 097) — GS1 global trade item number (EAN-8/12/13/14).
    gtin: str | None = Field(default=None, max_length=14)
    specs: dict[str, Any] | None = None
    dimensions: dict[str, Any] | None = None
    weight: Decimal | None = Field(default=None, ge=0)
    weight_unit: str | None = Field(default=None, max_length=8)
    packaging: dict[str, Any] | None = None
    intrastat_code: str | None = Field(default=None, max_length=16)
    erp_name: str | None = Field(default=None, max_length=128)
    data_quality: str | None = None
    manual_locked_fields: list[str] | None = None

    # ---- Wave 2: lifecycle / identity (PATCH) ------------------------------
    lifecycle_status: str | None = None
    revision: str | None = Field(default=None, max_length=32)
    series: str | None = Field(default=None, max_length=64)
    parent_sku: str | None = Field(default=None, max_length=64)
    is_parent: bool | None = None
    is_variant: bool | None = None

    # ---- Wave 2: technical scalars (PATCH) --------------------------------
    # Stage 2 (mig. 043): valve scalars viven en specs JSONB; dn_real ≡ dn.
    size: str | None = Field(default=None, max_length=64)
    temp_min_c: int | None = Field(default=None, ge=-273, le=2000)
    temp_max_c: int | None = Field(default=None, ge=-273, le=2000)
    pressure_max_bar: Decimal | None = Field(default=None, ge=0, le=Decimal("9999.99"))

    # ---- Wave 2: editorial / SEO (PATCH) ----------------------------------
    # Fase B (mig 065): `tags` dropeado.
    video_url: str | None = Field(default=None, max_length=2048)
    external_url: str | None = Field(default=None, max_length=2048)

    # ---- Stage 3 (Wave 11): catalog hierarchy refinement (PATCH) ----------
    series_id: UUID | None = None
    material_id: UUID | None = None
    display_pair_sku: str | None = Field(default=None, max_length=64)

    @field_validator("dn")
    @classmethod
    def _validate_dn(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.upper()
        if v.startswith("DN"):
            v = v[2:]
        if v not in ALLOWED_DN:
            raise ValueError(f"dn inválido: {v}")
        return v

    @field_validator("pn")
    @classmethod
    def _validate_pn(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.upper()
        if v.startswith("PN"):
            v = v[2:]
        if v not in ALLOWED_PN:
            raise ValueError(f"pn inválido: {v}")
        return v

    @field_validator("weight_unit")
    @classmethod
    def _validate_weight_unit(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if v not in ALLOWED_WEIGHT_UNITS:
            raise ValueError(f"weight_unit inválido: {v}")
        return v

    @field_validator("data_quality")
    @classmethod
    def _validate_data_quality(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if v not in ALLOWED_DATA_QUALITY:
            raise ValueError(f"data_quality inválido: {v}")
        return v

    @field_validator("gtin")
    @classmethod
    def _validate_gtin(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not v.isdigit() or len(v) not in (8, 12, 13, 14):
            raise ValueError("gtin debe ser numérico y de 8, 12, 13 o 14 dígitos")
        return v

    @field_validator("lifecycle_status")
    @classmethod
    def _validate_lifecycle(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if v not in ALLOWED_LIFECYCLE_STATUS:
            raise ValueError(
                f"lifecycle_status inválido: {v}; permitidos: {sorted(ALLOWED_LIFECYCLE_STATUS)}"
            )
        return v

    @model_validator(mode="after")
    def _at_least_one_field(self) -> ProductPatch:
        if not self.model_dump(exclude_unset=True):
            raise ValueError("PATCH payload vacío — al menos un campo requerido.")
        # Validar rango de temperatura cuando ambos se proveen.
        if (
            self.temp_min_c is not None
            and self.temp_max_c is not None
            and self.temp_max_c < self.temp_min_c
        ):
            raise ValueError("temp_max_c debe ser >= temp_min_c")
        return self


class ProductReplace(ProductBase):
    """PUT body — full replacement de la ficha de un SKU.

    A diferencia de ``ProductCreate``, NO incluye ``sku`` (viene en path y es
    inmutable BR-1a-01). Tampoco permite ``manual_locked_fields`` mediante
    campo separado — quien quiera tocar locks usa PATCH.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    # Permite reasignar el set de locks por completo desde la UI de "configurar
    # campos bloqueados" — admin/comercial avanzado.
    manual_locked_fields: list[str] = Field(default_factory=list)


class ProductDataQualityPatch(BaseModel):
    """PATCH body para `/products/{sku}/data-quality` — toggle del flag."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    data_quality: Literal["complete", "partial", "blocked", "migrated_demo"]
    reason: str | None = Field(default=None, max_length=512)


class ProductTranslationSummary(BaseModel):
    """Resumen de traducción para `ProductResponse` (sin marketing_copy)."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    lang: str
    status: str
    name: str | None = None
    updated_at: datetime | None = None


class ProductResponse(BaseModel):
    """Response estándar — listados y mutaciones.

    Fase B (mig 065/066):
    - ``name_en/description_en/marketing_copy_en`` siguen exponiéndose como
      campos *opcionales* para preservar contrato API hacia FE. Se rellenan
      desde el modelo SQLAlchemy vía hybrid_property que lee de
      ``product_translations(lang='en')`` cuando esa relationship está cargada.
    - ``active`` se expone como **computed_field** read-only derivado de
      ``lifecycle_status == 'active'``.
    - ``tags`` se mantiene como lista vacía read-only (canónico en vocabs M:N).
    - ``family_id`` (UUID) ahora se expone explícitamente (Fase 2 EAV FE).
    """

    model_config = ConfigDict(from_attributes=True, extra="ignore")

    sku: str
    internal_id: UUID
    # Fase B: opcionales — populated vía Product hybrid props desde translations(en).
    name_en: str | None = None
    description_en: str | None = None
    marketing_copy_en: str | None = None
    family: str
    family_id: UUID | None = None
    subfamily: str | None = None
    type: str | None = None
    material: str | None = None
    dn: str | None = None
    pn: str | None = None
    connection: str | None = None
    brand: str | None = None
    specs: dict[str, Any] = Field(default_factory=dict)
    dimensions: dict[str, Any] = Field(default_factory=dict)
    weight: Decimal | None = None
    weight_unit: str | None = None
    packaging: dict[str, Any] = Field(default_factory=dict)
    intrastat_code: str | None = None
    erp_name: str | None = None
    data_quality: str
    manual_locked_fields: list[str] = Field(default_factory=list)
    # Fase B: `active` se expone como computed_field (ver al final de la clase).
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    # ---- Wave 2: lifecycle / identity --------------------------------------
    lifecycle_status: str = "active"
    revision: str | None = None
    series: str | None = None
    parent_sku: str | None = None
    is_parent: bool = False
    is_variant: bool = False
    # ---- Wave 2: technical scalars (sólo transversales) --------------------
    # Stage 2 (mig. 043): valve scalars viven en specs JSONB; dn_real ≡ dn.
    size: str | None = None
    temp_min_c: int | None = None
    temp_max_c: int | None = None
    pressure_max_bar: Decimal | None = None
    # ---- Wave 2: editorial / SEO -------------------------------------------
    tags: list[str] = Field(default_factory=list)
    video_url: str | None = None
    external_url: str | None = None
    # Agregados denormalizados — sólo poblados por el listado (`GET /products`).
    translation_status_es: str | None = None
    translation_status_ar: str | None = None
    primary_image_url: str | None = None
    # ---- Stage 3 (Wave 11) — refinamiento del catálogo --------------------
    series_id: UUID | None = None
    material_id: UUID | None = None
    display_pair_sku: str | None = None
    division_codes: list[str] = Field(default_factory=list)
    model_id: UUID | None = None
    gtin: str | None = None  # ADD THIS LINE

    # Fase B (mig 066): active deriva de lifecycle_status para preservar
    # contrato API (FE puede seguir leyendo `.active`) mientras
    # input/storage usan sólo lifecycle_status.
    @computed_field  # type: ignore[prop-decorator]
    @property
    def active(self) -> bool:
        return self.lifecycle_status == "active"


class ProductMini(BaseModel):
    """Mini-summary de producto — usado para emparejado por color (display_pair).

    Fase B: ``name_en`` ahora opcional; viene de hybrid_property en Product
    SQLAlchemy model.
    """

    model_config = ConfigDict(from_attributes=True, extra="ignore")

    sku: str
    name_en: str | None = None
    primary_image_url: str | None = None


class ProductDetail(ProductResponse):
    """Response extendida — incluye full translations + assets (photos via images)."""

    translations: list[ProductTranslationResponse] = Field(default_factory=list)
    images: list[ProductAssetResponse] = Field(default_factory=list)
    # ---- Stage 3 (Wave 11) — series/material/display pair eager-loaded ----
    # Use *_detail fields to avoid shadowing the scalar str fields on ProductResponse.
    series_detail: "SeriesResponse | None" = None
    material_detail: "MaterialResponse | None" = None
    display_pair: ProductMini | None = None
    model_detail: ProductModelResponse | None = None


# ---------------------------------------------------------------------------
# Translations
# ---------------------------------------------------------------------------
class ProductTranslationBase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, max_length=512)
    description: str | None = Field(default=None, max_length=4000)
    marketing_copy: str | None = Field(default=None, max_length=8000)
    # ---- Wave 8: SEO + editorial -----------------------------------------
    meta_title: str | None = Field(default=None, max_length=70)
    meta_description: str | None = Field(default=None, max_length=160)
    applications_text: str | None = Field(default=None, max_length=4000)
    technical_limits: str | None = Field(default=None, max_length=4000)
    notes: str | None = Field(default=None, max_length=4000)
    marketing_features: str | None = Field(default=None, max_length=8000)
    status: Literal["pending", "draft", "approved"] = "draft"


class ProductTranslationCreate(ProductTranslationBase):
    """PUT body — `lang` viene en path."""


class ProductTranslationPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, max_length=512)
    description: str | None = Field(default=None, max_length=4000)
    marketing_copy: str | None = Field(default=None, max_length=8000)
    # ---- Wave 8: SEO + editorial (PATCH) ---------------------------------
    meta_title: str | None = Field(default=None, max_length=70)
    meta_description: str | None = Field(default=None, max_length=160)
    applications_text: str | None = Field(default=None, max_length=4000)
    technical_limits: str | None = Field(default=None, max_length=4000)
    notes: str | None = Field(default=None, max_length=4000)
    marketing_features: str | None = Field(default=None, max_length=8000)
    status: Literal["pending", "draft", "approved"] | None = None

    @model_validator(mode="after")
    def _at_least_one_field(self) -> ProductTranslationPatch:
        if not self.model_dump(exclude_unset=True):
            raise ValueError("PATCH payload vacío — al menos un campo requerido.")
        return self


class ProductTranslationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    sku: str
    lang: str
    name: str | None = None
    description: str | None = None
    marketing_copy: str | None = None
    # ---- Wave 8: SEO + editorial -----------------------------------------
    meta_title: str | None = None
    meta_description: str | None = None
    applications_text: str | None = None
    technical_limits: str | None = None
    notes: str | None = None
    marketing_features: str | None = None
    status: str
    translated_by: UUID | None = None
    translated_at: datetime | None = None
    reviewed_by: UUID | None = None
    reviewed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Search params (query params bundle — usado por endpoints lista)
# ---------------------------------------------------------------------------
class ProductSearchParams(BaseModel):
    """Filtros para `GET /products` — agrupa query params."""

    model_config = ConfigDict(extra="forbid")

    family: str | None = None
    brand: str | None = None
    translation_status: Literal["pending", "draft", "approved"] | None = None
    lang: Literal["es", "ar"] | None = None
    data_quality: Literal["complete", "partial", "blocked", "migrated_demo"] | None = None
    active: bool | None = None
    search: str | None = Field(default=None, min_length=2, max_length=128)


# ---------------------------------------------------------------------------
# M1-04 — ProductUomConversion schemas
# ---------------------------------------------------------------------------
class ProductUomConversionBase(BaseModel):
    uom_from: str = Field(min_length=1, max_length=10)
    uom_to: str = Field(min_length=1, max_length=10)
    factor: Decimal = Field(gt=0, description="qty_uom_from × factor = qty_uom_to")
    is_active: bool = True

    @model_validator(mode="after")
    def uom_pair_not_equal(self) -> "ProductUomConversionBase":
        if self.uom_from == self.uom_to:
            raise ValueError("uom_from and uom_to must be different")
        return self


class ProductUomConversionCreate(ProductUomConversionBase):
    model_config = ConfigDict(extra="forbid")


class ProductUomConversionResponse(ProductUomConversionBase):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    product_sku: str
    # EP-ERP-01-03 (mig 20260514_106) — sentido canónico de la conversión.
    direction: str | None = None
    created_at: datetime


# ---------------------------------------------------------------------------
# M1-01 — ProductRelease schemas
# ---------------------------------------------------------------------------
class ProductReleaseBase(BaseModel):
    market_code: str = Field(min_length=2, max_length=10)
    local_name: str | None = Field(default=None, max_length=200)
    local_description: str | None = None
    local_sku: str | None = Field(default=None, max_length=50)
    local_uom: str | None = Field(default=None, max_length=10)
    list_price: Decimal | None = Field(default=None, gt=0)
    price_currency: str | None = Field(default=None, min_length=3, max_length=3)
    tax_class: str | None = Field(default=None, max_length=50)

    @field_validator("market_code")
    @classmethod
    def market_code_upper(cls, v: str) -> str:
        return v.upper()

    @field_validator("price_currency")
    @classmethod
    def currency_upper(cls, v: str | None) -> str | None:
        return v.upper() if v else v


class ProductReleaseCreate(ProductReleaseBase):
    model_config = ConfigDict(extra="forbid")


class ProductReleasePatch(BaseModel):
    """Actualización parcial de un release — todos los campos opcionales."""

    model_config = ConfigDict(extra="forbid")

    local_name: str | None = Field(default=None, max_length=200)
    local_description: str | None = None
    local_sku: str | None = Field(default=None, max_length=50)
    local_uom: str | None = Field(default=None, max_length=10)
    list_price: Decimal | None = Field(default=None, gt=0)
    price_currency: str | None = Field(default=None, min_length=3, max_length=3)
    tax_class: str | None = Field(default=None, max_length=50)

    @field_validator("price_currency")
    @classmethod
    def currency_upper(cls, v: str | None) -> str | None:
        return v.upper() if v else v


class ProductReleaseResponse(ProductReleaseBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_sku: str
    status: str
    is_active: bool
    released_at: datetime | None
    released_by: UUID | None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# BoreDimension — mig 099 — dimensiones por SKU × norma aplicable
# ---------------------------------------------------------------------------
class BoreDimensionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_sku: str
    dn_nominal_ref: str | None
    standard_system: str
    standard_code: str
    pressure_class: str | None
    bore_mm: Decimal | None
    face_to_face_mm: Decimal | None
    end_to_end_mm: Decimal | None
    flange_od_mm: Decimal | None
    bolt_circle_mm: Decimal | None
    bolt_count: int | None
    bolt_size: str | None
    is_primary: bool
    notes: str | None
    created_at: datetime


# Re-bind forward references — ProductDetail referencia translations/images
# Import vocabularios al final (al pie) para evitar ciclo de import al cargar
# `app.schemas.vocabularies`. Sólo se necesitan a la hora de model_rebuild.
from app.schemas.vocabularies import MaterialResponse, SeriesResponse  # noqa: E402

ProductDetail.model_rebuild()

"""Pydantic V2 schemas para Products / Translations / Images.

Alineado con `_bmad-output/planning-artifacts/mt-api-contract-openapi.yaml`
(tags Products / ProductTranslations / ProductImages).

Notas de diseño:
- Pydantic V2 con `model_config = ConfigDict(...)`.
- Validators para SKU regex, DN/PN whitelisted, lang ISO 639-1, MIME, etc.
- `from_attributes=True` para mapear directo desde modelos SQLAlchemy.
- Los schemas de respuesta NO exponen embeddings (Sprint 2+).
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
    field_validator,
    model_validator,
)

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
    {"8", "10", "15", "20", "25", "32", "40", "50",
     "65", "80", "100", "125", "150", "200", "250", "300"}
)
ALLOWED_PN: frozenset[str] = frozenset({"6", "10", "16", "20", "25", "30", "40", "63", "100"})
ALLOWED_WEIGHT_UNITS: frozenset[str] = frozenset({"kg", "g", "lb"})
ALLOWED_LANGS: frozenset[str] = frozenset({"es", "ar"})  # `en` es base, no se traduce
ALLOWED_DATA_QUALITY: frozenset[str] = frozenset({"complete", "partial", "blocked", "migrated_demo"})
ALLOWED_TRANSLATION_STATUS: frozenset[str] = frozenset({"pending", "draft", "approved"})
ALLOWED_IMAGE_MIME: frozenset[str] = frozenset(
    {"image/jpeg", "image/png", "image/webp", "image/avif"}
)
# Wave 2 — vocabulario controlado de lifecycle.
ALLOWED_LIFECYCLE_STATUS: frozenset[str] = frozenset(
    {"draft", "active", "deprecated", "replaced", "discontinued"}
)
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
    """Campos comunes — heredados por Create/Patch/Response."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name_en: str = Field(min_length=1, max_length=512, description="Nombre canónico en inglés.")
    description_en: str | None = Field(default=None, max_length=4000)
    marketing_copy_en: str | None = Field(default=None, max_length=8000)
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
    image_url: str | None = Field(default=None, max_length=2048)
    data_quality: str = Field(default="partial")
    active: bool = True

    # ---- Wave 2: lifecycle / identity --------------------------------------
    lifecycle_status: str = Field(default="active")
    revision: str | None = Field(default=None, max_length=32)
    series: str | None = Field(default=None, max_length=64)
    parent_sku: str | None = Field(default=None, max_length=64)
    is_parent: bool = False
    is_variant: bool = False

    # ---- Wave 2: technical scalars -----------------------------------------
    dn_real: str | None = Field(default=None, max_length=16)
    size: str | None = Field(default=None, max_length=64)
    temp_min_c: int | None = Field(default=None, ge=-273, le=2000)
    temp_max_c: int | None = Field(default=None, ge=-273, le=2000)
    pressure_max_bar: Decimal | None = Field(default=None, ge=0, le=Decimal("9999.99"))
    manufacturing_method: str | None = Field(default=None, max_length=32)
    actuator: str | None = Field(default=None, max_length=32)
    kv: Decimal | None = Field(default=None, ge=0, le=Decimal("999999.99"))
    kv2: Decimal | None = Field(default=None, ge=0, le=Decimal("999999.99"))
    torque_nm: Decimal | None = Field(default=None, ge=0, le=Decimal("99999.99"))
    iso5211_interface: str | None = Field(default=None, max_length=16)

    # ---- Wave 2: editorial / SEO -------------------------------------------
    tags: list[str] = Field(default_factory=list)
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

    @field_validator("manufacturing_method")
    @classmethod
    def _validate_manufacturing_method(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.lower()
        if v not in ALLOWED_MANUFACTURING_METHOD:
            raise ValueError(
                f"manufacturing_method inválido: {v}; permitidos: {sorted(ALLOWED_MANUFACTURING_METHOD)}"
            )
        return v

    @field_validator("actuator")
    @classmethod
    def _validate_actuator(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.lower()
        if v not in ALLOWED_ACTUATOR:
            raise ValueError(
                f"actuator inválido: {v}; permitidos: {sorted(ALLOWED_ACTUATOR)}"
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
            raise ValueError(f"weight_unit inválido: {v}; permitidos: {sorted(ALLOWED_WEIGHT_UNITS)}")
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
    """Request para PATCH /products/{sku} — todos opcionales."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name_en: str | None = Field(default=None, min_length=1, max_length=512)
    description_en: str | None = Field(default=None, max_length=4000)
    marketing_copy_en: str | None = Field(default=None, max_length=8000)
    family: str | None = Field(default=None, min_length=1, max_length=64)
    subfamily: str | None = Field(default=None, max_length=64)
    type: str | None = Field(default=None, max_length=64)
    material: str | None = Field(default=None, max_length=64)
    dn: str | None = Field(default=None, max_length=8)
    pn: str | None = Field(default=None, max_length=8)
    connection: str | None = Field(default=None, max_length=64)
    brand: str | None = Field(default=None, max_length=64)
    specs: dict[str, Any] | None = None
    dimensions: dict[str, Any] | None = None
    weight: Decimal | None = Field(default=None, ge=0)
    weight_unit: str | None = Field(default=None, max_length=8)
    packaging: dict[str, Any] | None = None
    intrastat_code: str | None = Field(default=None, max_length=16)
    erp_name: str | None = Field(default=None, max_length=128)
    image_url: str | None = Field(default=None, max_length=2048)
    data_quality: str | None = None
    manual_locked_fields: list[str] | None = None
    active: bool | None = None

    # ---- Wave 2: lifecycle / identity (PATCH) ------------------------------
    lifecycle_status: str | None = None
    revision: str | None = Field(default=None, max_length=32)
    series: str | None = Field(default=None, max_length=64)
    parent_sku: str | None = Field(default=None, max_length=64)
    is_parent: bool | None = None
    is_variant: bool | None = None

    # ---- Wave 2: technical scalars (PATCH) --------------------------------
    dn_real: str | None = Field(default=None, max_length=16)
    size: str | None = Field(default=None, max_length=64)
    temp_min_c: int | None = Field(default=None, ge=-273, le=2000)
    temp_max_c: int | None = Field(default=None, ge=-273, le=2000)
    pressure_max_bar: Decimal | None = Field(default=None, ge=0, le=Decimal("9999.99"))
    manufacturing_method: str | None = Field(default=None, max_length=32)
    actuator: str | None = Field(default=None, max_length=32)
    kv: Decimal | None = Field(default=None, ge=0, le=Decimal("999999.99"))
    kv2: Decimal | None = Field(default=None, ge=0, le=Decimal("999999.99"))
    torque_nm: Decimal | None = Field(default=None, ge=0, le=Decimal("99999.99"))
    iso5211_interface: str | None = Field(default=None, max_length=16)

    # ---- Wave 2: editorial / SEO (PATCH) ----------------------------------
    tags: list[str] | None = None
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

    @field_validator("manufacturing_method")
    @classmethod
    def _validate_manufacturing_method(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.lower()
        if v not in ALLOWED_MANUFACTURING_METHOD:
            raise ValueError(f"manufacturing_method inválido: {v}")
        return v

    @field_validator("actuator")
    @classmethod
    def _validate_actuator(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.lower()
        if v not in ALLOWED_ACTUATOR:
            raise ValueError(f"actuator inválido: {v}")
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
    """Response estándar — listados y mutaciones."""

    model_config = ConfigDict(from_attributes=True, extra="ignore")

    sku: str
    internal_id: UUID
    name_en: str
    description_en: str | None = None
    marketing_copy_en: str | None = None
    family: str
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
    image_url: str | None = None
    image_status: str
    data_quality: str
    manual_locked_fields: list[str] = Field(default_factory=list)
    active: bool
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
    # ---- Wave 2: technical scalars -----------------------------------------
    dn_real: str | None = None
    size: str | None = None
    temp_min_c: int | None = None
    temp_max_c: int | None = None
    pressure_max_bar: Decimal | None = None
    manufacturing_method: str | None = None
    actuator: str | None = None
    kv: Decimal | None = None
    kv2: Decimal | None = None
    torque_nm: Decimal | None = None
    iso5211_interface: str | None = None
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


class ProductMini(BaseModel):
    """Mini-summary de producto — usado para emparejado por color (display_pair)."""

    model_config = ConfigDict(from_attributes=True, extra="ignore")

    sku: str
    name_en: str
    primary_image_url: str | None = None


class ProductDetail(ProductResponse):
    """Response extendida — incluye full translations + assets (photos via images)."""

    translations: list[ProductTranslationResponse] = Field(default_factory=list)
    images: list[ProductAssetResponse] = Field(default_factory=list)
    # ---- Stage 3 (Wave 11) — series/material/display pair eager-loaded ----
    series: "SeriesResponse | None" = None
    material: "MaterialResponse | None" = None
    display_pair: ProductMini | None = None


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


# Re-bind forward references — ProductDetail referencia translations/images
# Import vocabularios al final (al pie) para evitar ciclo de import al cargar
# `app.schemas.vocabularies`. Sólo se necesitan a la hora de model_rebuild.
from app.schemas.vocabularies import MaterialResponse, SeriesResponse  # noqa: E402

ProductDetail.model_rebuild()

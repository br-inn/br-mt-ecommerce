"""Schemas para el módulo de enriquecimiento desde ficha técnica."""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class ExtractedScalars(BaseModel):
    """Campos escalares extraídos del PDF — mapean 1:1 a ProductPatch."""

    model_config = ConfigDict(extra="allow")

    family: str | None = None
    subfamily: str | None = None
    type: str | None = None
    material: str | None = None
    dn: str | None = None
    pn: str | None = None
    connection: str | None = None
    brand: str | None = None
    weight: float | None = None
    weight_unit: str | None = None
    temp_min_c: int | None = None
    temp_max_c: int | None = None
    pressure_max_bar: float | None = None
    size: str | None = None


class ExtractedMaterial(BaseModel):
    component: str
    position: int = 0
    material: str
    observations: str | None = None
    material_grade: str | None = None
    material_standard: str | None = None
    surface_treatment: str | None = None


class ExtractedDimensionRow(BaseModel):
    dn_label: str
    values: dict[str, float | str]
    dn_secondary_label: str | None = None


class ExtractedTranslation(BaseModel):
    lang: str
    name: str | None = None
    description: str | None = None


class PageClassification(BaseModel):
    page_index: int
    kind: str
    confidence: float = Field(ge=0.0, le=1.0)
    description: str = ""


class ExtractedAsset(BaseModel):
    page_index: int
    asset_kind: str
    storage_path: str = ""
    mime_type: str = "image/png"
    description: str = ""


class ExtractedSpecs(BaseModel):
    seat_material: str | None = None
    seal_material: str | None = None
    stem_material: str | None = None
    standards: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    no_frost: bool | None = None
    actuation_type: str | None = None
    bore_type: str | None = None
    end_connection_gender: str | None = None
    inlet_connection: str | None = None
    outlet_connection: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class ExtractedCertificate(BaseModel):
    """Certificado emitido detectado en el PDF."""

    certification_code: str  # e.g. "ACS", "WRAS", "PZH", "CE"
    cert_number: str | None = None
    issuer: str | None = None
    issued_at: str | None = None  # ISO date string "YYYY-MM-DD"
    expires_at: str | None = None  # ISO date string "YYYY-MM-DD"
    signatory_name: str | None = None
    signatory_role: str | None = None


class ExtractedFlowData(BaseModel):
    """Coeficiente de flujo Kv/Cv + malla por DN."""

    dn_label: str
    kv: float | None = None
    cv: float | None = None
    mesh_mm: float | None = None


class FichaExtractionResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    scalars: ExtractedScalars
    specs: ExtractedSpecs
    materials: list[ExtractedMaterial] = Field(default_factory=list)
    dimensions: list[ExtractedDimensionRow] = Field(default_factory=list)
    translations: list[ExtractedTranslation] = Field(default_factory=list)
    page_classifications: list[PageClassification] = Field(default_factory=list)
    extracted_assets: list[ExtractedAsset] = Field(default_factory=list)
    pt_curve_points: list[dict[str, float]] = Field(
        default_factory=list,
        description="Puntos de curva P/T: [{temperature_c, pressure_max_bar}]",
    )
    certificates: list[ExtractedCertificate] = Field(default_factory=list)
    flow_data: list[ExtractedFlowData] = Field(default_factory=list)
    model_gaps: list[str] = Field(
        default_factory=list,
        description="Campos detectados en PDF sin mapeo al modelo actual.",
    )
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    raw_text_preview: str = ""


class FieldDiff(BaseModel):
    field_name: str
    current_value: Any = None
    extracted_value: Any
    has_change: bool
    validation_error: str | None = None


class SkuDiffResult(BaseModel):
    """Diffs de un SKU concreto dentro de la serie."""

    sku: str
    status: Literal["existing", "new"] = "existing"
    diffs: list[FieldDiff]


class FichaEnrichPreviewResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    sku: str  # SKU anchor (el del URL)
    series: str  # prefijo de serie detectado, ej. "4097"
    filename: str
    extraction: FichaExtractionResult
    series_skus: list[SkuDiffResult]  # un entry por cada SKU de la serie
    model_gaps: list[str]
    page_count: int
    confidence: float


class FichaEnrichApplyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    extraction: FichaExtractionResult
    apply_to_skus: list[str] = Field(description="SKUs a los que aplicar. Vacío = ninguno.")
    apply_scalars: bool = True
    apply_specs: bool = True
    apply_materials: bool = True
    apply_dimensions: bool = True
    apply_translations: bool = False
    apply_assets: bool = False
    apply_pt_curve: bool = False
    selected_scalar_fields: list[str] = Field(
        default_factory=list,
        description="Si vacío aplica todos los scalars extraídos; si hay lista, solo esos.",
    )


class SkuApplyResult(BaseModel):
    """Resultado de aplicar la extracción a un SKU concreto."""

    sku: str
    applied_fields: list[str]
    skipped_fields: list[str]
    warnings: list[str]


class FichaEnrichApplyResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    series: str
    results: list[SkuApplyResult]


class SeriesGroupResult(BaseModel):
    """Grupo de serie base + variante de color opcional (ej. 4097 rojo + 40972 azul)."""

    base_series: str
    variant_series: str | None = None
    base_skus: list[SkuDiffResult]
    variant_skus: list[SkuDiffResult] = Field(default_factory=list)


class FichaSeriesPreviewResponse(BaseModel):
    """Respuesta de preview serie-level (sin SKU anchor)."""

    model_config = ConfigDict(extra="ignore")

    series: str
    filename: str
    extraction: FichaExtractionResult
    series_skus: list[SkuDiffResult]  # todos los SKUs flat (compat)
    series_groups: list[SeriesGroupResult] = Field(default_factory=list)  # agrupados
    detected_series: list[str] = Field(default_factory=list)
    model_gaps: list[str]
    page_count: int
    confidence: float


class FichaSeriesApplyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    extraction: FichaExtractionResult
    apply_to_skus: list[str]
    series: str
    pdf_filename: str = ""
    apply_scalars: bool = True
    apply_specs: bool = True
    apply_materials: bool = True
    apply_dimensions: bool = True
    apply_translations: bool = False
    apply_assets: bool = False
    apply_pt_curve: bool = False
    selected_scalar_fields: list[str] = Field(default_factory=list)
    save_document: bool = True
    variant_links: dict[str, str] = Field(
        default_factory=dict,
        description="Mapa variant_sku→base_sku para vincular variantes de color al crear.",
    )
    variant_series: str | None = Field(
        default=None,
        description="Prefijo de la serie variante (color pair). Si se provee, se crea su ProductModel.",
    )


class FichaSeriesApplyResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    series: str
    results: list[SkuApplyResult]
    document_id: str | None = None
    skus_created: list[str] = Field(default_factory=list)
    skus_updated: list[str] = Field(default_factory=list)


__all__ = [
    "ExtractedScalars",
    "ExtractedMaterial",
    "ExtractedDimensionRow",
    "ExtractedTranslation",
    "PageClassification",
    "ExtractedAsset",
    "ExtractedSpecs",
    "ExtractedCertificate",
    "ExtractedFlowData",
    "FichaExtractionResult",
    "FieldDiff",
    "SkuDiffResult",
    "SeriesGroupResult",
    "FichaEnrichPreviewResponse",
    "FichaEnrichApplyRequest",
    "SkuApplyResult",
    "FichaEnrichApplyResponse",
    "FichaSeriesPreviewResponse",
    "FichaSeriesApplyRequest",
    "FichaSeriesApplyResponse",
]

# Ficha Técnica Enrichment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Subir una ficha técnica PDF (ej. `MTFT_4097.pdf`) y extraer automáticamente todos los campos del producto correspondiente (ej. `4097015`) con diff interactivo + apply selectivo por campo — y así validar si el modelo de datos cubre lo que las fichas contienen.

**Architecture:** Un nuevo endpoint `POST /products/{sku}/ficha-enrich/preview` recibe el PDF, extrae texto+tablas con pdfplumber y llama a Claude (claude-sonnet-4-6 vía anthropic SDK ya instalado) para estructurar TODOS los campos del modelo. Devuelve un `FichaEnrichmentResult` con: campos extraídos, diff vs. producto actual, y `model_gaps` (campos en el PDF que no tienen mapeo en el modelo). El endpoint `POST /products/{sku}/ficha-enrich/apply` aplica los campos seleccionados usando los endpoints existentes del ProductService.

**Tech Stack:** FastAPI + pdfplumber (ya instalado) + anthropic SDK (ya instalado, `claude-sonnet-4-6`) + SQLAlchemy async + Next.js 16 + React 19 + Tailwind v4 + Shadcn/ui new-york. Sin migración DB — todo cabe en tablas existentes (`products`, `product_materials`, `product_translations`, `product_tech_tables`, `product_datasheets`).

---

## Context — Infraestructura existente (NO duplicar)

- `app/services/importer_datasheets/pdf_extractor.py` → `extract_text_from_pdf()`, `extract_tables_from_pdf()`, `extract_pdf_metadata()` — reusar directo.
- `app/services/importer_datasheets/spec_parser.py` → `DatasheetSpecs` (solo dn/pn/material/seal via regex) — NO reusar; el nuevo extractor reemplaza con Claude.
- `app/services/importer_datasheets/vision_extractor.py` → solo dn/pn/material/seal via VLM imagen; NO reusar aquí.
- `app/api/routes/products.py` → `PATCH /products/{sku}`, `PUT /products/{sku}/materials`, `PUT /products/{sku}/translations/{lang}`, `PUT /products/{sku}/tech-tables/{kind}` — el applier llama internamente al ProductService.
- `app/schemas/products.py` → `ProductPatch`, `ProductBase` — campos disponibles: `family`, `subfamily`, `type`, `material`, `dn`, `pn`, `connection`, `brand`, `specs` (JSONB), `dimensions` (JSONB), `weight`, `weight_unit`, `temp_min_c`, `temp_max_c`, `pressure_max_bar`, `intrastat_code`, `erp_name`, `lifecycle_status`, `series`, `size`, `video_url`.

## PDF MTFT_4097.pdf — Campos extraíbles confirmados

Del análisis del PDF (`MTFT_4097.pdf`, 9 páginas):
- family: "válvulas de esfera"
- type: "esfera roscada PN30"
- material: "brass_cw617n"
- pn: "30", pressure_max_bar: 30
- connection: "bsp" (ISO 228/1 / DIN259)
- temp_min_c: -20, temp_max_c: 120
- brand: "MT Business Key"
- specs.seat_material: "ptfe", specs.seal_material: "nbr", specs.no_frost: true
- specs.standards: ["ISO 228/1", "DIN259", "WRAS", "ACS", "PZH"]
- ProductMaterials: [{component:"body", material:"brass_cw617n"}, {component:"seat", material:"ptfe"}, {component:"seal", material:"nbr"}]
- Translations es: name="Válvula esfera PN30 con palanca inox y maneta ergonómica"
- Table: dimensiones por tamaño (1/4" a 2") → tech-table kind=dimensions_by_dn

---

## File Map

**Backend (crear):**
- `app/schemas/ficha_enrich.py` — Pydantic schemas para request/response del módulo
- `app/services/ficha_enrichment/__init__.py` — exports
- `app/services/ficha_enrichment/extractor.py` — Claude extraction (texto+tablas → campos estructurados)
- `app/services/ficha_enrichment/differ.py` — diff campos extraídos vs. producto actual en DB
- `app/services/ficha_enrichment/applier.py` — apply selectivo al ProductService
- `app/api/routes/ficha_enrich.py` — endpoints preview + apply
- `tests/unit/services/ficha_enrichment/test_extractor.py`
- `tests/unit/services/ficha_enrichment/test_differ.py`
- `tests/unit/services/ficha_enrichment/test_applier.py`

**Backend (modificar):**
- `app/api/routes/__init__.py` — registrar el nuevo router

**Frontend (crear):**
- `components/domain/ficha-enrichment/enrichment-diff-table.tsx` — tabla campo-a-campo con checkboxes
- `app/(app)/catalogo/[sku]/enriquecer/page.tsx` — server component wrapper
- `app/(app)/catalogo/[sku]/enriquecer/_client.tsx` — wizard upload → diff → apply
- `lib/api/endpoints/ficha-enrich.ts` — tipado API
- `lib/hooks/ficha-enrichment/use-ficha-enrich.ts` — React Query hooks

**Frontend (modificar):**
- `app/(app)/catalogo/[sku]/layout.tsx` — añadir tab "Enriquecer" (si existe barra de tabs)

---

## Task 1: Backend schema `ficha_enrich.py`

**Files:**
- Create: `mt-pricing-backend/app/schemas/ficha_enrich.py`
- Test: `mt-pricing-backend/tests/unit/schemas/test_ficha_enrich.py`

- [ ] **Step 1: Crear el schema file**

```python
# mt-pricing-backend/app/schemas/ficha_enrich.py
"""Schemas para el módulo de enriquecimiento desde ficha técnica."""

from __future__ import annotations

from typing import Any
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
    component: str        # "body" | "seat" | "stem" | "seal" | "disc"
    position: int = 0
    material: str
    observations: str | None = None


class ExtractedDimensionRow(BaseModel):
    dn_label: str          # e.g. "1/2\"" or "DN15"
    values: dict[str, float | str]  # col_name → value


class ExtractedTranslation(BaseModel):
    lang: str              # "es" | "ar"
    name: str | None = None
    description: str | None = None


class ExtractedSpecs(BaseModel):
    """Campos para specs JSONB — específicos por tipo de producto."""
    seat_material: str | None = None
    seal_material: str | None = None
    stem_material: str | None = None
    standards: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    no_frost: bool | None = None
    actuation_type: str | None = None
    bore_type: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class FichaExtractionResult(BaseModel):
    """Output del extractor Claude — campos crudos del PDF."""
    model_config = ConfigDict(extra="ignore")

    scalars: ExtractedScalars
    specs: ExtractedSpecs
    materials: list[ExtractedMaterial] = Field(default_factory=list)
    dimensions: list[ExtractedDimensionRow] = Field(default_factory=list)
    translations: list[ExtractedTranslation] = Field(default_factory=list)
    model_gaps: list[str] = Field(
        default_factory=list,
        description="Campos detectados en PDF sin mapeo al modelo actual.",
    )
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    raw_text_preview: str = ""


class FieldDiff(BaseModel):
    """Diff para un campo individual."""
    field_name: str
    current_value: Any = None
    extracted_value: Any
    has_change: bool
    validation_error: str | None = None


class FichaEnrichPreviewResponse(BaseModel):
    """Response de POST /products/{sku}/ficha-enrich/preview."""
    model_config = ConfigDict(extra="ignore")

    sku: str
    filename: str
    extraction: FichaExtractionResult
    diffs: list[FieldDiff]
    model_gaps: list[str]
    page_count: int
    confidence: float


class FichaEnrichApplyRequest(BaseModel):
    """Request de POST /products/{sku}/ficha-enrich/apply."""
    model_config = ConfigDict(extra="forbid")

    extraction: FichaExtractionResult
    apply_scalars: bool = True
    apply_specs: bool = True
    apply_materials: bool = True
    apply_dimensions: bool = True
    apply_translations: bool = False
    selected_scalar_fields: list[str] = Field(
        default_factory=list,
        description="Si vacío, aplica todos los scalars extraídos. Si hay lista, solo esos.",
    )


class FichaEnrichApplyResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    sku: str
    applied_fields: list[str]
    skipped_fields: list[str]
    errors: list[str]


__all__ = [
    "ExtractedScalars",
    "ExtractedMaterial",
    "ExtractedDimensionRow",
    "ExtractedTranslation",
    "ExtractedSpecs",
    "FichaExtractionResult",
    "FieldDiff",
    "FichaEnrichPreviewResponse",
    "FichaEnrichApplyRequest",
    "FichaEnrichApplyResponse",
]
```

- [ ] **Step 2: Test básico de schema**

```python
# mt-pricing-backend/tests/unit/schemas/test_ficha_enrich.py
from app.schemas.ficha_enrich import (
    ExtractedScalars, FichaExtractionResult, FichaEnrichApplyRequest
)

def test_extracted_scalars_partial():
    s = ExtractedScalars(pn="30", temp_min_c=-20, temp_max_c=120)
    assert s.pn == "30"
    assert s.temp_min_c == -20
    d = s.model_dump(exclude_none=True)
    assert "family" not in d

def test_apply_request_defaults():
    req = FichaEnrichApplyRequest(
        extraction=FichaExtractionResult(
            scalars=ExtractedScalars(),
            specs=__import__("app.schemas.ficha_enrich", fromlist=["ExtractedSpecs"]).ExtractedSpecs(),
        )
    )
    assert req.apply_scalars is True
    assert req.apply_translations is False
```

- [ ] **Step 3: Correr test**

```bash
cd mt-pricing-backend
python -m pytest tests/unit/schemas/test_ficha_enrich.py -v
```
Expected: PASS (2 tests)

- [ ] **Step 4: Commit**

```bash
git add mt-pricing-backend/app/schemas/ficha_enrich.py mt-pricing-backend/tests/unit/schemas/test_ficha_enrich.py
git commit -m "feat(ficha-enrich): schemas FichaExtractionResult + diff + apply"
```

---

## Task 2: Backend — FichaEnrichmentExtractor (Claude)

**Files:**
- Create: `mt-pricing-backend/app/services/ficha_enrichment/__init__.py`
- Create: `mt-pricing-backend/app/services/ficha_enrichment/extractor.py`
- Create: `mt-pricing-backend/tests/unit/services/ficha_enrichment/__init__.py`
- Create: `mt-pricing-backend/tests/unit/services/ficha_enrichment/test_extractor.py`

- [ ] **Step 1: Crear `__init__.py`**

```python
# mt-pricing-backend/app/services/ficha_enrichment/__init__.py
from app.services.ficha_enrichment.extractor import FichaEnrichmentExtractor
from app.services.ficha_enrichment.differ import FichaEnrichmentDiffer
from app.services.ficha_enrichment.applier import FichaEnrichmentApplier

__all__ = ["FichaEnrichmentExtractor", "FichaEnrichmentDiffer", "FichaEnrichmentApplier"]
```

- [ ] **Step 2: Crear `extractor.py`**

```python
# mt-pricing-backend/app/services/ficha_enrichment/extractor.py
"""Extrae campos del modelo de producto desde texto+tablas de una ficha técnica.

Usa Claude claude-sonnet-4-6 via anthropic SDK con tool_use para output estructurado.
Si no hay API key o no está en live mode, devuelve resultado vacío sin lanzar.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

from app.schemas.ficha_enrich import (
    ExtractedDimensionRow,
    ExtractedMaterial,
    ExtractedScalars,
    ExtractedSpecs,
    ExtractedTranslation,
    FichaExtractionResult,
)
from app.services.importer_datasheets.pdf_extractor import (
    extract_pdf_metadata,
    extract_tables_from_pdf,
    extract_text_from_pdf,
)

logger = logging.getLogger(__name__)

_TOOL_SCHEMA: dict[str, Any] = {
    "name": "extract_product_fields",
    "description": (
        "Extrae todos los campos del producto de una ficha técnica PVF "
        "(válvulas, tuberías, accesorios). Omite los campos que no aparecen en el PDF."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "family": {"type": "string", "description": "Familia del producto (ej. 'válvulas de esfera', 'válvulas de mariposa')"},
            "subfamily": {"type": "string"},
            "type": {"type": "string", "description": "Tipo específico (ej. 'esfera roscada PN30', 'mariposa wafer PN16')"},
            "material": {"type": "string", "description": "Material cuerpo canónico (ej. 'brass_cw617n', 'ss316', 'ductile_iron')"},
            "dn": {"type": "string", "description": "Diámetro nominal principal (ej. '50', '25'). Solo número sin prefijo DN."},
            "pn": {"type": "string", "description": "Presión nominal (ej. '16', '30'). Solo número sin prefijo PN."},
            "connection": {"type": "string", "description": "Tipo de conexión (ej. 'bsp', 'npt', 'flanged', 'wafer', 'lug')"},
            "brand": {"type": "string"},
            "temp_min_c": {"type": "integer", "description": "Temperatura mínima de trabajo en °C"},
            "temp_max_c": {"type": "integer", "description": "Temperatura máxima de trabajo en °C"},
            "pressure_max_bar": {"type": "number", "description": "Presión máxima de trabajo en bar"},
            "weight": {"type": "number", "description": "Peso en kg (si hay una sola talla; si hay tabla, dejar null)"},
            "weight_unit": {"type": "string", "enum": ["kg", "g", "lb"]},
            "size": {"type": "string", "description": "Descripción del rango de tamaños (ej. '1/4\" a 2\"')"},
            "specs": {
                "type": "object",
                "description": "Campos técnicos específicos",
                "properties": {
                    "seat_material": {"type": "string"},
                    "seal_material": {"type": "string"},
                    "stem_material": {"type": "string"},
                    "standards": {"type": "array", "items": {"type": "string"}},
                    "certifications": {"type": "array", "items": {"type": "string"}},
                    "no_frost": {"type": "boolean"},
                    "actuation_type": {"type": "string"},
                    "bore_type": {"type": "string"},
                    "extra": {"type": "object"},
                },
            },
            "materials": {
                "type": "array",
                "description": "Materiales por componente",
                "items": {
                    "type": "object",
                    "required": ["component", "material"],
                    "properties": {
                        "component": {"type": "string", "enum": ["body", "seat", "stem", "seal", "disc", "nut", "handle"]},
                        "position": {"type": "integer", "default": 0},
                        "material": {"type": "string"},
                        "observations": {"type": "string"},
                    },
                },
            },
            "dimensions": {
                "type": "array",
                "description": "Tabla de dimensiones por talla/DN",
                "items": {
                    "type": "object",
                    "required": ["dn_label", "values"],
                    "properties": {
                        "dn_label": {"type": "string"},
                        "values": {"type": "object"},
                    },
                },
            },
            "translations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["lang"],
                    "properties": {
                        "lang": {"type": "string", "enum": ["es", "ar", "en"]},
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                    },
                },
            },
            "model_gaps": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Información relevante en el PDF que NO tiene campo en el modelo (para validación del modelo de datos).",
            },
            "confidence": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "description": "Confianza general de la extracción (0-1)",
            },
        },
        "required": ["confidence"],
    },
}

_SYSTEM_PROMPT = (
    "Eres un especialista en datos de productos PVF (válvulas, tuberías, accesorios industriales). "
    "Tu tarea es extraer TODOS los campos del modelo de producto de una ficha técnica. "
    "Sé preciso: si no ves el dato claramente, no lo incluyas. "
    "Para materiales, usa nombres canónicos en inglés lowercase (brass_cw617n, ss316, ptfe, nbr, epdm). "
    "Para dn/pn, usa solo el número sin prefijo (ej. '30' no 'PN30'). "
    "El campo model_gaps es IMPORTANTE: lista todo lo que encuentres en el PDF que no tenga campo "
    "correspondiente en el modelo (ej. 'tabla de par de apriete', 'curva Kv', 'certificado CE número X')."
)


class FichaEnrichmentExtractor:
    """Extrae campos estructurados de un PDF ficha técnica usando Claude."""

    def __init__(self, *, api_key: str | None = None, model: str = "claude-sonnet-4-6") -> None:
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self._model = model

    def _is_enabled(self) -> bool:
        return bool(self._api_key) and os.environ.get("MT_LIVE_NETWORK", "").lower() == "true"

    async def extract(self, *, pdf_bytes: bytes, filename: str = "ficha.pdf") -> FichaExtractionResult:
        meta = extract_pdf_metadata(pdf_bytes)
        text: str = meta.get("text", "") or ""
        tables: list[dict] = meta.get("tables", []) or []

        if not self._is_enabled():
            logger.info("ficha_enrichment: extractor disabled (no API key or live network off)")
            return FichaExtractionResult(
                scalars=ExtractedScalars(),
                specs=ExtractedSpecs(),
                model_gaps=["extractor_disabled_no_api_key"],
                confidence=0.0,
                raw_text_preview=text[:500],
            )

        tables_str = _format_tables(tables)
        user_message = (
            f"Filename: {filename}\n\n"
            f"=== TEXTO EXTRAÍDO ===\n{text[:8000]}\n\n"
            f"=== TABLAS DETECTADAS ===\n{tables_str[:4000]}"
        )

        try:
            import anthropic  # lazy import — evita error en tests sin SDK

            client = anthropic.AsyncAnthropic(api_key=self._api_key)
            response = await client.messages.create(
                model=self._model,
                max_tokens=4096,
                system=_SYSTEM_PROMPT,
                tools=[_TOOL_SCHEMA],
                tool_choice={"type": "tool", "name": "extract_product_fields"},
                messages=[{"role": "user", "content": user_message}],
            )
        except Exception as exc:
            logger.exception("ficha_enrichment: Claude call failed")
            return FichaExtractionResult(
                scalars=ExtractedScalars(),
                specs=ExtractedSpecs(),
                model_gaps=[f"claude_error: {type(exc).__name__}"],
                confidence=0.0,
                raw_text_preview=text[:500],
            )

        tool_input = _parse_tool_response(response)
        return _build_result(tool_input, raw_text=text)


def _format_tables(tables: list[dict]) -> str:
    if not tables:
        return "(sin tablas detectadas)"
    lines: list[str] = []
    for t in tables:
        lines.append(f"[Página {t.get('page', '?')}]")
        headers = t.get("headers", [])
        rows = t.get("rows", [])
        if headers:
            lines.append(" | ".join(str(h) for h in headers))
        for row in rows[:20]:
            lines.append(" | ".join(str(c) for c in row))
        lines.append("")
    return "\n".join(lines)


def _parse_tool_response(response: Any) -> dict[str, Any]:
    for block in response.content:
        if block.type == "tool_use" and block.name == "extract_product_fields":
            inp = block.input
            if isinstance(inp, str):
                return json.loads(inp)
            return inp  # type: ignore[return-value]
    return {}


def _build_result(data: dict[str, Any], raw_text: str) -> FichaExtractionResult:
    specs_data = data.get("specs") or {}
    scalars = ExtractedScalars(
        family=data.get("family"),
        subfamily=data.get("subfamily"),
        type=data.get("type"),
        material=data.get("material"),
        dn=data.get("dn"),
        pn=data.get("pn"),
        connection=data.get("connection"),
        brand=data.get("brand"),
        weight=data.get("weight"),
        weight_unit=data.get("weight_unit"),
        temp_min_c=data.get("temp_min_c"),
        temp_max_c=data.get("temp_max_c"),
        pressure_max_bar=data.get("pressure_max_bar"),
        size=data.get("size"),
    )
    specs = ExtractedSpecs(
        seat_material=specs_data.get("seat_material"),
        seal_material=specs_data.get("seal_material"),
        stem_material=specs_data.get("stem_material"),
        standards=specs_data.get("standards") or [],
        certifications=specs_data.get("certifications") or [],
        no_frost=specs_data.get("no_frost"),
        actuation_type=specs_data.get("actuation_type"),
        bore_type=specs_data.get("bore_type"),
        extra=specs_data.get("extra") or {},
    )
    materials = [
        ExtractedMaterial(
            component=m["component"],
            position=m.get("position", 0),
            material=m["material"],
            observations=m.get("observations"),
        )
        for m in (data.get("materials") or [])
        if m.get("component") and m.get("material")
    ]
    dimensions = [
        ExtractedDimensionRow(dn_label=d["dn_label"], values=d.get("values", {}))
        for d in (data.get("dimensions") or [])
        if d.get("dn_label")
    ]
    translations = [
        ExtractedTranslation(lang=t["lang"], name=t.get("name"), description=t.get("description"))
        for t in (data.get("translations") or [])
        if t.get("lang")
    ]
    return FichaExtractionResult(
        scalars=scalars,
        specs=specs,
        materials=materials,
        dimensions=dimensions,
        translations=translations,
        model_gaps=data.get("model_gaps") or [],
        confidence=float(data.get("confidence") or 0.0),
        raw_text_preview=raw_text[:500],
    )


__all__ = ["FichaEnrichmentExtractor"]
```

- [ ] **Step 3: Escribir test con mock de Claude**

```python
# mt-pricing-backend/tests/unit/services/ficha_enrichment/__init__.py
# (vacío)

# mt-pricing-backend/tests/unit/services/ficha_enrichment/test_extractor.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.ficha_enrichment.extractor import (
    FichaEnrichmentExtractor,
    _build_result,
    _format_tables,
)
from app.schemas.ficha_enrich import FichaExtractionResult


MINIMAL_PDF = b"%PDF-1.4\n1 0 obj\n<</Type/Catalog>>\nendobj\nxref\n0 1\n0000000000 65535 f\ntrailer\n<</Root 1 0 R>>\nstartxref\n9\n%%EOF"

_MOCK_TOOL_INPUT = {
    "family": "válvulas de esfera",
    "type": "esfera roscada PN30",
    "material": "brass_cw617n",
    "pn": "30",
    "temp_min_c": -20,
    "temp_max_c": 120,
    "pressure_max_bar": 30.0,
    "brand": "MT Business Key",
    "connection": "bsp",
    "specs": {
        "seat_material": "ptfe",
        "seal_material": "nbr",
        "standards": ["ISO 228/1", "WRAS"],
        "no_frost": True,
    },
    "materials": [
        {"component": "body", "material": "brass_cw617n"},
        {"component": "seat", "material": "ptfe"},
        {"component": "seal", "material": "nbr"},
    ],
    "dimensions": [
        {"dn_label": "1/4\"", "values": {"L": 54.0, "H": 57.0}},
        {"dn_label": "1/2\"", "values": {"L": 63.0, "H": 64.0}},
    ],
    "model_gaps": ["tabla par de apriete"],
    "confidence": 0.92,
}


def _make_mock_response() -> MagicMock:
    block = MagicMock()
    block.type = "tool_use"
    block.name = "extract_product_fields"
    block.input = _MOCK_TOOL_INPUT
    resp = MagicMock()
    resp.content = [block]
    return resp


@pytest.mark.asyncio
async def test_extract_disabled_returns_empty():
    extractor = FichaEnrichmentExtractor(api_key="")
    result = await extractor.extract(pdf_bytes=MINIMAL_PDF, filename="test.pdf")
    assert result.confidence == 0.0
    assert "extractor_disabled_no_api_key" in result.model_gaps


@pytest.mark.asyncio
async def test_extract_with_mock_claude(monkeypatch):
    monkeypatch.setenv("MT_LIVE_NETWORK", "true")
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=_make_mock_response())

    with patch("anthropic.AsyncAnthropic", return_value=mock_client):
        extractor = FichaEnrichmentExtractor(api_key="sk-test")
        result = await extractor.extract(pdf_bytes=MINIMAL_PDF, filename="MTFT_4097.pdf")

    assert result.scalars.pn == "30"
    assert result.scalars.temp_min_c == -20
    assert result.scalars.material == "brass_cw617n"
    assert result.specs.seat_material == "ptfe"
    assert len(result.materials) == 3
    assert result.materials[0].component == "body"
    assert len(result.dimensions) == 2
    assert result.model_gaps == ["tabla par de apriete"]
    assert result.confidence == 0.92


def test_build_result_empty_data():
    r = _build_result({}, raw_text="")
    assert isinstance(r, FichaExtractionResult)
    assert r.confidence == 0.0
    assert r.materials == []


def test_format_tables_empty():
    s = _format_tables([])
    assert "sin tablas" in s


def test_format_tables_with_data():
    tables = [{"page": 1, "headers": ["DN", "L", "H"], "rows": [["1/2\"", "63", "64"]]}]
    s = _format_tables(tables)
    assert "DN" in s
    assert "63" in s
```

- [ ] **Step 4: Correr test**

```bash
cd mt-pricing-backend
python -m pytest tests/unit/services/ficha_enrichment/test_extractor.py -v
```
Expected: PASS (5 tests — los dos async necesitan pytest-asyncio ya configurado)

- [ ] **Step 5: Commit**

```bash
git add mt-pricing-backend/app/services/ficha_enrichment/ mt-pricing-backend/tests/unit/services/ficha_enrichment/
git commit -m "feat(ficha-enrich): FichaEnrichmentExtractor — Claude tool_use extraction"
```

---

## Task 3: Backend — FichaEnrichmentDiffer

**Files:**
- Create: `mt-pricing-backend/app/services/ficha_enrichment/differ.py`
- Test: `mt-pricing-backend/tests/unit/services/ficha_enrichment/test_differ.py`

- [ ] **Step 1: Crear `differ.py`**

```python
# mt-pricing-backend/app/services/ficha_enrichment/differ.py
"""Compara campos extraídos del PDF con los valores actuales del producto en DB."""
from __future__ import annotations

from typing import Any

from app.db.models.product import Product
from app.schemas.ficha_enrich import FieldDiff, FichaExtractionResult

_SCALAR_FIELD_MAP: dict[str, str] = {
    "family": "family",
    "subfamily": "subfamily",
    "type": "type",
    "material": "material",
    "dn": "dn",
    "pn": "pn",
    "connection": "connection",
    "brand": "brand",
    "weight": "weight",
    "weight_unit": "weight_unit",
    "temp_min_c": "temp_min_c",
    "temp_max_c": "temp_max_c",
    "pressure_max_bar": "pressure_max_bar",
    "size": "size",
}


class FichaEnrichmentDiffer:
    """Genera lista de FieldDiff comparando extracción vs. Product ORM."""

    def compute(self, product: Product, extraction: FichaExtractionResult) -> list[FieldDiff]:
        diffs: list[FieldDiff] = []
        scalars_dict = extraction.scalars.model_dump(exclude_none=True)

        for extracted_field, model_attr in _SCALAR_FIELD_MAP.items():
            if extracted_field not in scalars_dict:
                continue
            extracted_val = scalars_dict[extracted_field]
            current_val = getattr(product, model_attr, None)
            if isinstance(current_val, __import__("decimal").Decimal):
                current_val = float(current_val)
            has_change = _values_differ(current_val, extracted_val)
            diffs.append(FieldDiff(
                field_name=extracted_field,
                current_value=current_val,
                extracted_value=extracted_val,
                has_change=has_change,
            ))

        # specs JSONB diff — mostrar como un único campo
        specs_extracted = _specs_to_dict(extraction)
        if specs_extracted:
            current_specs = dict(product.specs or {})
            merged = {**current_specs, **specs_extracted}
            has_change = any(
                _values_differ(current_specs.get(k), v)
                for k, v in specs_extracted.items()
            )
            diffs.append(FieldDiff(
                field_name="specs",
                current_value=current_specs,
                extracted_value=merged,
                has_change=has_change,
            ))

        # materials diff — como bloque
        if extraction.materials:
            diffs.append(FieldDiff(
                field_name="materials",
                current_value=None,
                extracted_value=[m.model_dump() for m in extraction.materials],
                has_change=True,
            ))

        # dimensions diff — como bloque
        if extraction.dimensions:
            diffs.append(FieldDiff(
                field_name="dimensions_by_dn",
                current_value=None,
                extracted_value=[d.model_dump() for d in extraction.dimensions],
                has_change=True,
            ))

        # translations diff — como bloque
        if extraction.translations:
            diffs.append(FieldDiff(
                field_name="translations",
                current_value=None,
                extracted_value=[t.model_dump() for t in extraction.translations],
                has_change=True,
            ))

        return diffs


def _values_differ(current: Any, extracted: Any) -> bool:
    if current is None and extracted is None:
        return False
    if current is None or extracted is None:
        return True
    if isinstance(current, float) or isinstance(extracted, float):
        try:
            return abs(float(current) - float(extracted)) > 0.001
        except (TypeError, ValueError):
            pass
    return str(current).strip() != str(extracted).strip()


def _specs_to_dict(extraction: FichaExtractionResult) -> dict[str, Any]:
    out: dict[str, Any] = {}
    s = extraction.specs
    if s.seat_material:
        out["seat_material"] = s.seat_material
    if s.seal_material:
        out["seal_material"] = s.seal_material
    if s.stem_material:
        out["stem_material"] = s.stem_material
    if s.standards:
        out["standards"] = s.standards
    if s.certifications:
        out["certifications"] = s.certifications
    if s.no_frost is not None:
        out["no_frost"] = s.no_frost
    if s.actuation_type:
        out["actuation_type"] = s.actuation_type
    if s.bore_type:
        out["bore_type"] = s.bore_type
    if s.extra:
        out.update(s.extra)
    return out


__all__ = ["FichaEnrichmentDiffer"]
```

- [ ] **Step 2: Test del differ**

```python
# mt-pricing-backend/tests/unit/services/ficha_enrichment/test_differ.py
from unittest.mock import MagicMock
from app.services.ficha_enrichment.differ import FichaEnrichmentDiffer
from app.schemas.ficha_enrich import (
    ExtractedScalars, ExtractedSpecs, FichaExtractionResult, ExtractedMaterial
)

def _make_product(**kwargs):
    p = MagicMock()
    p.family = "válvulas"
    p.pn = None
    p.temp_min_c = None
    p.temp_max_c = None
    p.material = None
    p.specs = {}
    for k, v in kwargs.items():
        setattr(p, k, v)
    return p


def test_differ_detects_new_fields():
    product = _make_product()
    extraction = FichaExtractionResult(
        scalars=ExtractedScalars(pn="30", temp_min_c=-20, temp_max_c=120),
        specs=ExtractedSpecs(),
        confidence=0.9,
    )
    differ = FichaEnrichmentDiffer()
    diffs = differ.compute(product, extraction)
    pn_diff = next(d for d in diffs if d.field_name == "pn")
    assert pn_diff.has_change is True
    assert pn_diff.current_value is None
    assert pn_diff.extracted_value == "30"


def test_differ_no_change_when_same():
    product = _make_product(pn="30")
    extraction = FichaExtractionResult(
        scalars=ExtractedScalars(pn="30"),
        specs=ExtractedSpecs(),
        confidence=0.9,
    )
    differ = FichaEnrichmentDiffer()
    diffs = differ.compute(product, extraction)
    pn_diff = next(d for d in diffs if d.field_name == "pn")
    assert pn_diff.has_change is False


def test_differ_materials_block():
    product = _make_product()
    extraction = FichaExtractionResult(
        scalars=ExtractedScalars(),
        specs=ExtractedSpecs(),
        materials=[ExtractedMaterial(component="body", material="brass_cw617n")],
        confidence=0.9,
    )
    differ = FichaEnrichmentDiffer()
    diffs = differ.compute(product, extraction)
    mat_diff = next(d for d in diffs if d.field_name == "materials")
    assert mat_diff.has_change is True
    assert mat_diff.extracted_value[0]["component"] == "body"
```

- [ ] **Step 3: Correr test**

```bash
cd mt-pricing-backend
python -m pytest tests/unit/services/ficha_enrichment/test_differ.py -v
```
Expected: PASS (3 tests)

- [ ] **Step 4: Commit**

```bash
git add mt-pricing-backend/app/services/ficha_enrichment/differ.py mt-pricing-backend/tests/unit/services/ficha_enrichment/test_differ.py
git commit -m "feat(ficha-enrich): FichaEnrichmentDiffer — diff extraído vs. producto"
```

---

## Task 4: Backend — FichaEnrichmentApplier

**Files:**
- Create: `mt-pricing-backend/app/services/ficha_enrichment/applier.py`
- Test: `mt-pricing-backend/tests/unit/services/ficha_enrichment/test_applier.py`

- [ ] **Step 1: Crear `applier.py`**

```python
# mt-pricing-backend/app/services/ficha_enrichment/applier.py
"""Aplica los campos extraídos de una ficha técnica al producto en DB."""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.product import Product, ProductMaterial
from app.db.models.tech_tables import ProductTechTable
from app.db.models.user import User
from app.schemas.ficha_enrich import FichaEnrichApplyRequest, FichaEnrichApplyResponse
from app.services.ficha_enrichment.differ import _specs_to_dict

logger = logging.getLogger(__name__)

_PATCHABLE_SCALAR_FIELDS = {
    "family", "subfamily", "type", "material", "dn", "pn", "connection", "brand",
    "weight", "weight_unit", "temp_min_c", "temp_max_c", "pressure_max_bar", "size",
}


class FichaEnrichmentApplier:

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def apply(
        self,
        sku: str,
        request: FichaEnrichApplyRequest,
        actor: User,
    ) -> FichaEnrichApplyResponse:
        applied: list[str] = []
        skipped: list[str] = []
        errors: list[str] = []

        product = await self._load_product(sku)
        if product is None:
            errors.append(f"product_not_found: {sku}")
            return FichaEnrichApplyResponse(sku=sku, applied_fields=[], skipped_fields=[], errors=errors)

        # --- scalars ---
        if request.apply_scalars:
            scalars_dict = request.extraction.scalars.model_dump(exclude_none=True)
            allowed = set(request.selected_scalar_fields) if request.selected_scalar_fields else _PATCHABLE_SCALAR_FIELDS
            for field, value in scalars_dict.items():
                if field not in allowed:
                    skipped.append(field)
                    continue
                if field in product.manual_locked_fields:
                    skipped.append(f"{field}(locked)")
                    continue
                try:
                    setattr(product, field, value)
                    applied.append(field)
                except Exception as exc:
                    errors.append(f"{field}: {exc}")

        # --- specs JSONB merge ---
        if request.apply_specs:
            specs_patch = _specs_to_dict(request.extraction)
            if specs_patch:
                merged = {**(product.specs or {}), **specs_patch}
                product.specs = merged
                applied.append("specs")

        await self._session.flush()

        # --- materials ---
        if request.apply_materials and request.extraction.materials:
            try:
                await self._replace_materials(sku, request.extraction.materials)
                applied.append("materials")
            except Exception as exc:
                errors.append(f"materials: {exc}")

        # --- dimensions tech-table ---
        if request.apply_dimensions and request.extraction.dimensions:
            try:
                await self._upsert_dimensions_table(sku, request.extraction.dimensions)
                applied.append("dimensions_by_dn")
            except Exception as exc:
                errors.append(f"dimensions_by_dn: {exc}")

        # --- translations ---
        if request.apply_translations and request.extraction.translations:
            try:
                await self._upsert_translations(sku, request.extraction.translations, actor)
                applied.append("translations")
            except Exception as exc:
                errors.append(f"translations: {exc}")

        return FichaEnrichApplyResponse(
            sku=sku,
            applied_fields=applied,
            skipped_fields=skipped,
            errors=errors,
        )

    async def _load_product(self, sku: str) -> Product | None:
        result = await self._session.execute(select(Product).where(Product.sku == sku))
        return result.scalar_one_or_none()

    async def _replace_materials(self, sku: str, materials: list[Any]) -> None:
        from app.db.models.components import ProductMaterial as PM

        existing = (await self._session.execute(
            select(PM).where(PM.product_sku == sku)
        )).scalars().all()
        for row in existing:
            await self._session.delete(row)
        await self._session.flush()

        for m in materials:
            row = PM(
                product_sku=sku,
                component=m.component,
                position=m.position,
                material=m.material,
                observations=m.observations,
            )
            self._session.add(row)
        await self._session.flush()

    async def _upsert_dimensions_table(self, sku: str, dimensions: list[Any]) -> None:
        data_payload: dict[str, Any] = {
            "rows": [{"dn_label": d.dn_label, "values": d.values} for d in dimensions]
        }
        existing = (await self._session.execute(
            select(ProductTechTable).where(
                ProductTechTable.product_sku == sku,
                ProductTechTable.kind == "dimensions_by_dn",
            )
        )).scalar_one_or_none()

        if existing:
            existing.data = data_payload
            existing.source = "ficha_enrich"
        else:
            self._session.add(ProductTechTable(
                product_sku=sku,
                kind="dimensions_by_dn",
                source="ficha_enrich",
                data=data_payload,
            ))
        await self._session.flush()

    async def _upsert_translations(self, sku: str, translations: list[Any], actor: User) -> None:
        from app.db.models.product import ProductTranslation

        for t in translations:
            if not t.name and not t.description:
                continue
            existing = (await self._session.execute(
                select(ProductTranslation).where(
                    ProductTranslation.sku == sku,
                    ProductTranslation.lang == t.lang,
                )
            )).scalar_one_or_none()
            if existing:
                if t.name:
                    existing.name = t.name
                if t.description:
                    existing.description = t.description
            else:
                self._session.add(ProductTranslation(
                    sku=sku,
                    lang=t.lang,
                    name=t.name or "",
                    description=t.description,
                    status="draft",
                    translated_by=actor.id,
                ))
        await self._session.flush()


__all__ = ["FichaEnrichmentApplier"]
```

- [ ] **Step 2: Test del applier con DB mock**

```python
# mt-pricing-backend/tests/unit/services/ficha_enrichment/test_applier.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.ficha_enrichment.applier import FichaEnrichmentApplier
from app.schemas.ficha_enrich import (
    FichaEnrichApplyRequest, FichaExtractionResult,
    ExtractedScalars, ExtractedSpecs, ExtractedMaterial,
)


def _make_actor():
    actor = MagicMock()
    actor.id = "00000000-0000-0000-0000-000000000001"
    return actor


def _make_product(sku="4097015"):
    p = MagicMock()
    p.sku = sku
    p.manual_locked_fields = []
    p.specs = {}
    return p


@pytest.mark.asyncio
async def test_apply_scalars_updates_product():
    session = AsyncMock()
    product = _make_product()
    session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=product)))
    session.flush = AsyncMock()

    applier = FichaEnrichmentApplier(session)
    req = FichaEnrichApplyRequest(
        extraction=FichaExtractionResult(
            scalars=ExtractedScalars(pn="30", temp_min_c=-20, temp_max_c=120),
            specs=ExtractedSpecs(),
            confidence=0.9,
        ),
        apply_scalars=True,
        apply_specs=False,
        apply_materials=False,
        apply_dimensions=False,
    )
    result = await applier.apply("4097015", req, _make_actor())

    assert "pn" in result.applied_fields
    assert "temp_min_c" in result.applied_fields
    assert product.pn == "30"
    assert product.temp_min_c == -20
    assert result.errors == []


@pytest.mark.asyncio
async def test_apply_product_not_found():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

    applier = FichaEnrichmentApplier(session)
    req = FichaEnrichApplyRequest(
        extraction=FichaExtractionResult(
            scalars=ExtractedScalars(pn="30"),
            specs=ExtractedSpecs(),
            confidence=0.9,
        ),
    )
    result = await applier.apply("9999999", req, _make_actor())
    assert any("product_not_found" in e for e in result.errors)


@pytest.mark.asyncio
async def test_apply_locked_field_skipped():
    session = AsyncMock()
    product = _make_product()
    product.manual_locked_fields = ["pn"]
    session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=product)))
    session.flush = AsyncMock()

    applier = FichaEnrichmentApplier(session)
    req = FichaEnrichApplyRequest(
        extraction=FichaExtractionResult(
            scalars=ExtractedScalars(pn="30", temp_min_c=-20),
            specs=ExtractedSpecs(),
            confidence=0.9,
        ),
        apply_materials=False,
        apply_dimensions=False,
    )
    result = await applier.apply("4097015", req, _make_actor())
    assert any("pn" in s for s in result.skipped_fields)
    assert "temp_min_c" in result.applied_fields
```

- [ ] **Step 3: Correr test**

```bash
cd mt-pricing-backend
python -m pytest tests/unit/services/ficha_enrichment/test_applier.py -v
```
Expected: PASS (3 tests)

- [ ] **Step 4: Commit**

```bash
git add mt-pricing-backend/app/services/ficha_enrichment/applier.py mt-pricing-backend/tests/unit/services/ficha_enrichment/test_applier.py
git commit -m "feat(ficha-enrich): FichaEnrichmentApplier — apply selectivo campos extraídos"
```

---

## Task 5: Backend — API Route + Register

**Files:**
- Create: `mt-pricing-backend/app/api/routes/ficha_enrich.py`
- Modify: `mt-pricing-backend/app/api/routes/__init__.py`

- [ ] **Step 1: Crear el router**

```python
# mt-pricing-backend/app/api/routes/ficha_enrich.py
"""Ficha técnica enrichment endpoints.

POST /products/{sku}/ficha-enrich/preview   — sube PDF, extrae campos, compara con producto.
POST /products/{sku}/ficha-enrich/apply     — aplica campos seleccionados al producto.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Path, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_permissions
from app.db.models.product import Product
from app.db.models.user import User
from app.schemas.common import ProblemDetails
from app.schemas.ficha_enrich import (
    FichaEnrichApplyRequest,
    FichaEnrichApplyResponse,
    FichaEnrichPreviewResponse,
)
from app.services.ficha_enrichment import (
    FichaEnrichmentApplier,
    FichaEnrichmentDiffer,
    FichaEnrichmentExtractor,
)

from sqlalchemy import select as _sa_select

router = APIRouter(tags=["products", "ficha-enrich"])

_MAX_PDF_BYTES = 50 * 1024 * 1024  # 50 MB


@router.post(
    "/products/{sku}/ficha-enrich/preview",
    response_model=FichaEnrichPreviewResponse,
    summary="Extraer campos de ficha técnica PDF y comparar con producto",
    responses={
        404: {"model": ProblemDetails},
        413: {"model": ProblemDetails, "description": "PDF > 50 MB"},
        422: {"model": ProblemDetails},
    },
)
async def preview_ficha_enrich(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    file: Annotated[UploadFile, File(description="PDF de ficha técnica (≤ 50 MB)")],
    _user: Annotated[User, Depends(require_permissions("products:write"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> FichaEnrichPreviewResponse:
    if file.filename is None:
        raise HTTPException(status_code=422, detail={"code": "missing_filename", "title": "Filename requerido"})

    pdf_bytes = await file.read()
    if len(pdf_bytes) > _MAX_PDF_BYTES:
        raise HTTPException(status_code=413, detail={"code": "pdf_too_large", "title": "PDF > 50 MB"})
    if not pdf_bytes.lstrip().startswith(b"%PDF"):
        raise HTTPException(status_code=422, detail={"code": "not_a_pdf", "title": "El archivo no es un PDF válido"})

    product = await _load_product_or_404(session, sku)

    extractor = FichaEnrichmentExtractor()
    extraction = await extractor.extract(pdf_bytes=pdf_bytes, filename=file.filename)

    differ = FichaEnrichmentDiffer()
    diffs = differ.compute(product, extraction)

    from app.services.importer_datasheets.pdf_extractor import extract_pdf_metadata
    meta = extract_pdf_metadata(pdf_bytes)

    return FichaEnrichPreviewResponse(
        sku=sku,
        filename=file.filename,
        extraction=extraction,
        diffs=diffs,
        model_gaps=extraction.model_gaps,
        page_count=meta.get("page_count", 0),
        confidence=extraction.confidence,
    )


@router.post(
    "/products/{sku}/ficha-enrich/apply",
    response_model=FichaEnrichApplyResponse,
    summary="Aplicar campos extraídos de ficha técnica al producto",
    responses={
        404: {"model": ProblemDetails},
        409: {"model": ProblemDetails, "description": "Campo bloqueado manualmente"},
    },
)
async def apply_ficha_enrich(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    body: FichaEnrichApplyRequest,
    user: Annotated[User, Depends(require_permissions("products:write"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> FichaEnrichApplyResponse:
    await _load_product_or_404(session, sku)

    applier = FichaEnrichmentApplier(session)
    return await applier.apply(sku, body, user)


async def _load_product_or_404(session: AsyncSession, sku: str) -> Product:
    result = await session.execute(_sa_select(Product).where(Product.sku == sku))
    product = result.scalar_one_or_none()
    if product is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "product_not_found", "title": f"SKU {sku!r} no encontrado"},
        )
    return product


__all__ = ["router"]
```

- [ ] **Step 2: Registrar en `__init__.py`**

Abrir `mt-pricing-backend/app/api/routes/__init__.py` y añadir dentro de la función de registro de routers (buscar el patrón `app.include_router`):

```python
# Al final de los includes existentes, añadir:
from app.api.routes.ficha_enrich import router as ficha_enrich_router
app.include_router(ficha_enrich_router, prefix="/api/v1")
```

Verificar dónde está la función `create_app` o `include_router` en ese archivo y añadir la línea en el lugar correcto.

- [ ] **Step 3: Verificar que el backend arranca**

```bash
cd mt-pricing-backend
python -c "from app.main import app; print('OK')"
```
Expected: `OK` sin errores de import.

- [ ] **Step 4: Smoke test manual del endpoint**

```bash
# Con el backend corriendo en Docker:
curl -s http://localhost:8081/api/v1/openapi.json | python -c "import json,sys; d=json.load(sys.stdin); paths=[p for p in d['paths'] if 'ficha-enrich' in p]; print(paths)"
```
Expected: `['/api/v1/products/{sku}/ficha-enrich/preview', '/api/v1/products/{sku}/ficha-enrich/apply']`

- [ ] **Step 5: Commit**

```bash
git add mt-pricing-backend/app/api/routes/ficha_enrich.py mt-pricing-backend/app/api/routes/__init__.py
git commit -m "feat(ficha-enrich): API endpoints preview + apply — registrados en router"
```

---

## Task 6: Redeploy backend y smoke test real con MTFT_4097.pdf

- [ ] **Step 1: Rebuild y restart backend**

```bash
docker restart mt-backend
```

- [ ] **Step 2: Verificar health**

```bash
curl -s http://localhost:8081/health/live
```
Expected: `{"status": "ok"}` o similar.

- [ ] **Step 3: Upload real PDF contra un SKU real**

Obtener un JWT válido del Supabase local y ejecutar:

```bash
# Reemplazar <TOKEN> por el JWT de un usuario con products:write
SKU="4097015"
PDF="C:/BR-Github/br-mt/br-mt-ecommerce/Documentos referencia de articulos/FICHAS TÉCNICAS/MTFT_4097.pdf"

curl -X POST \
  "http://localhost:8081/api/v1/products/${SKU}/ficha-enrich/preview" \
  -H "Authorization: Bearer <TOKEN>" \
  -F "file=@${PDF}" \
  | python -m json.tool
```

Expected:
```json
{
  "sku": "4097015",
  "filename": "MTFT_4097.pdf",
  "confidence": 0.8+,
  "model_gaps": [...],
  "diffs": [
    {"field_name": "pn", "extracted_value": "30", "has_change": true},
    {"field_name": "temp_min_c", "extracted_value": -20, "has_change": true},
    ...
  ]
}
```

**Si `MT_LIVE_NETWORK` no está en `true`:** el extractor devuelve vacío — revisar `.env.local` del backend y añadir `MT_LIVE_NETWORK=true` + `ANTHROPIC_API_KEY=<key>`, luego `docker restart mt-backend`.

- [ ] **Step 4: Registrar model_gaps para validación del modelo**

Anotar los valores de `model_gaps` en el response — estos son los campos de la ficha que NO tienen mapeo en el modelo de datos. Son el output clave de esta tarea.

- [ ] **Step 5: Commit anotación**

```bash
git commit --allow-empty -m "docs(ficha-enrich): smoke test MTFT_4097 — model_gaps documented"
```

---

## Task 7: Frontend — API layer + hooks

**Files:**
- Create: `mt-pricing-frontend/lib/api/endpoints/ficha-enrich.ts`
- Create: `mt-pricing-frontend/lib/hooks/ficha-enrichment/use-ficha-enrich.ts`

- [ ] **Step 1: Crear tipado API**

```typescript
// mt-pricing-frontend/lib/api/endpoints/ficha-enrich.ts
import { apiClient } from "@/lib/api/client";

export interface ExtractedScalars {
  family?: string;
  subfamily?: string;
  type?: string;
  material?: string;
  dn?: string;
  pn?: string;
  connection?: string;
  brand?: string;
  weight?: number;
  weight_unit?: string;
  temp_min_c?: number;
  temp_max_c?: number;
  pressure_max_bar?: number;
  size?: string;
}

export interface ExtractedSpecs {
  seat_material?: string;
  seal_material?: string;
  stem_material?: string;
  standards?: string[];
  certifications?: string[];
  no_frost?: boolean;
  actuation_type?: string;
  extra?: Record<string, unknown>;
}

export interface ExtractedMaterial {
  component: string;
  position: number;
  material: string;
  observations?: string;
}

export interface FichaExtractionResult {
  scalars: ExtractedScalars;
  specs: ExtractedSpecs;
  materials: ExtractedMaterial[];
  dimensions: Array<{ dn_label: string; values: Record<string, number | string> }>;
  translations: Array<{ lang: string; name?: string; description?: string }>;
  model_gaps: string[];
  confidence: number;
  raw_text_preview: string;
}

export interface FieldDiff {
  field_name: string;
  current_value: unknown;
  extracted_value: unknown;
  has_change: boolean;
  validation_error?: string;
}

export interface FichaEnrichPreviewResponse {
  sku: string;
  filename: string;
  extraction: FichaExtractionResult;
  diffs: FieldDiff[];
  model_gaps: string[];
  page_count: number;
  confidence: number;
}

export interface FichaEnrichApplyRequest {
  extraction: FichaExtractionResult;
  apply_scalars?: boolean;
  apply_specs?: boolean;
  apply_materials?: boolean;
  apply_dimensions?: boolean;
  apply_translations?: boolean;
  selected_scalar_fields?: string[];
}

export interface FichaEnrichApplyResponse {
  sku: string;
  applied_fields: string[];
  skipped_fields: string[];
  errors: string[];
}

export async function previewFichaEnrich(
  sku: string,
  file: File
): Promise<FichaEnrichPreviewResponse> {
  const form = new FormData();
  form.append("file", file);
  return apiClient.postForm(`/products/${sku}/ficha-enrich/preview`, form);
}

export async function applyFichaEnrich(
  sku: string,
  body: FichaEnrichApplyRequest
): Promise<FichaEnrichApplyResponse> {
  return apiClient.post(`/products/${sku}/ficha-enrich/apply`, body);
}
```

- [ ] **Step 2: Crear hooks React Query**

```typescript
// mt-pricing-frontend/lib/hooks/ficha-enrichment/use-ficha-enrich.ts
import { useMutation } from "@tanstack/react-query";
import {
  applyFichaEnrich,
  previewFichaEnrich,
  type FichaEnrichApplyRequest,
  type FichaEnrichApplyResponse,
  type FichaEnrichPreviewResponse,
} from "@/lib/api/endpoints/ficha-enrich";

export function usePreviewFichaEnrich(sku: string) {
  return useMutation<FichaEnrichPreviewResponse, Error, File>({
    mutationFn: (file) => previewFichaEnrich(sku, file),
  });
}

export function useApplyFichaEnrich(sku: string) {
  return useMutation<FichaEnrichApplyResponse, Error, FichaEnrichApplyRequest>({
    mutationFn: (body) => applyFichaEnrich(sku, body),
  });
}
```

- [ ] **Step 3: Verificar que TypeScript compila**

```bash
cd mt-pricing-frontend
npx tsc --noEmit 2>&1 | head -30
```
Expected: 0 errores en los nuevos archivos.

- [ ] **Step 4: Commit**

```bash
git add mt-pricing-frontend/lib/api/endpoints/ficha-enrich.ts mt-pricing-frontend/lib/hooks/ficha-enrichment/use-ficha-enrich.ts
git commit -m "feat(ficha-enrich): API client y React Query hooks"
```

---

## Task 8: Frontend — EnrichmentDiffTable component

**Files:**
- Create: `mt-pricing-frontend/components/domain/ficha-enrichment/enrichment-diff-table.tsx`

- [ ] **Step 1: Crear el componente**

```typescript
// mt-pricing-frontend/components/domain/ficha-enrichment/enrichment-diff-table.tsx
"use client";

import * as React from "react";
import { CheckCircle2, Minus, AlertCircle } from "lucide-react";
import { MT } from "@/components/mt/tokens";
import { Pill } from "@/components/mt/primitives";
import type { FieldDiff } from "@/lib/api/endpoints/ficha-enrich";

interface Props {
  diffs: FieldDiff[];
  selectedFields: Set<string>;
  onToggleField: (fieldName: string) => void;
}

const FIELD_LABELS: Record<string, string> = {
  family: "Familia",
  subfamily: "Subfamilia",
  type: "Tipo",
  material: "Material",
  dn: "DN",
  pn: "PN",
  connection: "Conexión",
  brand: "Marca",
  weight: "Peso",
  weight_unit: "Ud. peso",
  temp_min_c: "Temp. mín. (°C)",
  temp_max_c: "Temp. máx. (°C)",
  pressure_max_bar: "Presión máx. (bar)",
  size: "Talla",
  specs: "Specs (JSONB)",
  materials: "Materiales",
  dimensions_by_dn: "Tabla dimensiones",
  translations: "Traducciones",
};

function formatValue(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "object") return JSON.stringify(v, null, 2).slice(0, 120) + "…";
  return String(v);
}

export function EnrichmentDiffTable({ diffs, selectedFields, onToggleField }: Props) {
  const changedDiffs = diffs.filter((d) => d.has_change);
  const unchangedDiffs = diffs.filter((d) => !d.has_change);

  if (diffs.length === 0) {
    return (
      <p className="text-sm py-4 text-center" style={{ color: MT.ink3 }}>
        No se detectaron campos extraíbles.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      {changedDiffs.length > 0 && (
        <table className="w-full text-[12.5px]">
          <thead>
            <tr style={{ borderBottom: `1px solid ${MT.border}` }}>
              <th className="py-2 text-left pl-2 w-8" />
              <th className="py-2 text-left" style={{ color: MT.ink3 }}>Campo</th>
              <th className="py-2 text-left" style={{ color: MT.ink3 }}>Valor actual</th>
              <th className="py-2 text-left" style={{ color: MT.ink3 }}>Valor extraído</th>
            </tr>
          </thead>
          <tbody>
            {changedDiffs.map((diff) => (
              <tr
                key={diff.field_name}
                className="cursor-pointer hover:bg-zinc-50"
                onClick={() => onToggleField(diff.field_name)}
                style={{ borderBottom: `1px solid ${MT.border}` }}
              >
                <td className="py-2 pl-2">
                  <input
                    type="checkbox"
                    checked={selectedFields.has(diff.field_name)}
                    onChange={() => onToggleField(diff.field_name)}
                    className="rounded"
                    onClick={(e) => e.stopPropagation()}
                  />
                </td>
                <td className="py-2 font-medium" style={{ color: MT.ink }}>
                  {FIELD_LABELS[diff.field_name] ?? diff.field_name}
                </td>
                <td className="py-2" style={{ color: MT.ink3 }}>
                  <span className="mt-mono">{formatValue(diff.current_value)}</span>
                </td>
                <td className="py-2">
                  <span className="mt-mono font-medium" style={{ color: MT.brand }}>
                    {formatValue(diff.extracted_value)}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {unchangedDiffs.length > 0 && (
        <details className="text-[11.5px]">
          <summary className="cursor-pointer py-1" style={{ color: MT.ink3 }}>
            {unchangedDiffs.length} campo(s) sin cambios
          </summary>
          <ul className="mt-2 space-y-1 pl-2">
            {unchangedDiffs.map((d) => (
              <li key={d.field_name} className="flex items-center gap-2" style={{ color: MT.ink3 }}>
                <CheckCircle2 className="size-3.5 shrink-0" />
                <span>{FIELD_LABELS[d.field_name] ?? d.field_name}</span>
                <span className="mt-mono">{formatValue(d.current_value)}</span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add mt-pricing-frontend/components/domain/ficha-enrichment/enrichment-diff-table.tsx
git commit -m "feat(ficha-enrich): EnrichmentDiffTable con checkboxes por campo"
```

---

## Task 9: Frontend — Página `/catalogo/[sku]/enriquecer`

**Files:**
- Create: `mt-pricing-frontend/app/(app)/catalogo/[sku]/enriquecer/page.tsx`
- Create: `mt-pricing-frontend/app/(app)/catalogo/[sku]/enriquecer/_client.tsx`

- [ ] **Step 1: Crear el server component wrapper**

```typescript
// mt-pricing-frontend/app/(app)/catalogo/[sku]/enriquecer/page.tsx
import { FichaEnrichClient } from "./_client";

interface PageProps {
  params: Promise<{ sku: string }>;
}

export default async function FichaEnrichPage({ params }: PageProps) {
  const { sku } = await params;
  return <FichaEnrichClient sku={decodeURIComponent(sku)} />;
}
```

- [ ] **Step 2: Crear el client component wizard**

```typescript
// mt-pricing-frontend/app/(app)/catalogo/[sku]/enriquecer/_client.tsx
"use client";

/**
 * Wizard de enriquecimiento desde ficha técnica.
 * Step 0: dropzone PDF
 * Step 1: diff de campos extraídos + selección
 * Step 2: resultado apply
 */
import * as React from "react";
import { toast } from "sonner";
import { Upload, Sparkles, CheckCircle2, AlertCircle } from "lucide-react";
import { MtButton, Pill, SectionCard } from "@/components/mt/primitives";
import { MT } from "@/components/mt/tokens";
import { EnrichmentDiffTable } from "@/components/domain/ficha-enrichment/enrichment-diff-table";
import { usePreviewFichaEnrich, useApplyFichaEnrich } from "@/lib/hooks/ficha-enrichment/use-ficha-enrich";
import type { FichaEnrichPreviewResponse, FieldDiff } from "@/lib/api/endpoints/ficha-enrich";

interface Props { sku: string }

export function FichaEnrichClient({ sku }: Props) {
  const [step, setStep] = React.useState<0 | 1 | 2>(0);
  const [preview, setPreview] = React.useState<FichaEnrichPreviewResponse | null>(null);
  const [selectedFields, setSelectedFields] = React.useState<Set<string>>(new Set());

  const previewMut = usePreviewFichaEnrich(sku);
  const applyMut = useApplyFichaEnrich(sku);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const result = await previewMut.mutateAsync(file);
      setPreview(result);
      // Auto-seleccionar todos los campos con cambio
      const changed = new Set(result.diffs.filter((d) => d.has_change).map((d) => d.field_name));
      setSelectedFields(changed);
      setStep(1);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Error analizando PDF");
    }
  };

  const toggleField = (name: string) => {
    setSelectedFields((prev) => {
      const next = new Set(prev);
      next.has(name) ? next.delete(name) : next.add(name);
      return next;
    });
  };

  const handleApply = async () => {
    if (!preview) return;
    const scalarFieldNames = [
      "family","subfamily","type","material","dn","pn","connection","brand",
      "weight","weight_unit","temp_min_c","temp_max_c","pressure_max_bar","size",
    ];
    const selectedScalars = [...selectedFields].filter((f) => scalarFieldNames.includes(f));

    try {
      await applyMut.mutateAsync({
        extraction: preview.extraction,
        apply_scalars: selectedFields.has("specs") || selectedScalars.length > 0,
        apply_specs: selectedFields.has("specs"),
        apply_materials: selectedFields.has("materials"),
        apply_dimensions: selectedFields.has("dimensions_by_dn"),
        apply_translations: selectedFields.has("translations"),
        selected_scalar_fields: selectedScalars,
      });
      setStep(2);
      toast.success("Campos aplicados al producto");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Error aplicando");
    }
  };

  return (
    <div className="space-y-6 max-w-3xl">
      <SectionCard
        title="Enriquecer producto desde ficha técnica"
        subtitle={`SKU: ${sku} — Sube un PDF para extraer y aplicar campos automáticamente`}
        actions={
          preview ? (
            <Pill tone="brand">
              {(preview.confidence * 100).toFixed(0)}% confianza
            </Pill>
          ) : null
        }
      >
        <div className="px-4 py-4">
          {step === 0 && (
            <label className="flex flex-col items-center gap-3 p-8 border-2 border-dashed rounded-lg cursor-pointer transition-colors hover:border-brand"
              style={{ borderColor: MT.border }}>
              <Upload className="size-8" style={{ color: MT.ink3 }} />
              <span className="text-sm" style={{ color: MT.ink3 }}>
                Arrastra o haz clic para subir la ficha técnica PDF
              </span>
              <span className="text-[11.5px]" style={{ color: MT.ink3 }}>
                Formato: MTFT_*.pdf — máx. 50 MB
              </span>
              <input
                type="file"
                accept="application/pdf"
                className="hidden"
                onChange={handleFileChange}
              />
              {previewMut.isPending && (
                <span className="text-sm animate-pulse" style={{ color: MT.brand }}>
                  Analizando con Claude…
                </span>
              )}
            </label>
          )}

          {step === 1 && preview && (
            <div className="space-y-4">
              <div className="flex items-center gap-3 text-[12.5px]" style={{ color: MT.ink3 }}>
                <span>Archivo: <strong className="mt-mono">{preview.filename}</strong></span>
                <span>·</span>
                <span>{preview.page_count} páginas</span>
                <span>·</span>
                <span>{preview.diffs.filter(d => d.has_change).length} campos con cambios</span>
              </div>

              <EnrichmentDiffTable
                diffs={preview.diffs}
                selectedFields={selectedFields}
                onToggleField={toggleField}
              />

              {preview.model_gaps.length > 0 && (
                <div className="rounded-lg p-3 text-[12px] space-y-1"
                  style={{ background: MT.surface, border: `1px solid ${MT.border}` }}>
                  <div className="flex items-center gap-2 font-medium" style={{ color: MT.ink }}>
                    <AlertCircle className="size-4" />
                    Campos sin mapeo en el modelo de datos ({preview.model_gaps.length})
                  </div>
                  <ul className="pl-6 list-disc space-y-0.5" style={{ color: MT.ink3 }}>
                    {preview.model_gaps.map((gap) => (
                      <li key={gap}>{gap}</li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="flex items-center justify-between pt-2">
                <MtButton tone="ghost" onClick={() => setStep(0)}>
                  Subir otro PDF
                </MtButton>
                <MtButton
                  tone="primary"
                  onClick={() => void handleApply()}
                  disabled={selectedFields.size === 0 || applyMut.isPending}
                  icon={<Sparkles className="size-4" />}
                >
                  {applyMut.isPending ? "Aplicando…" : `Aplicar ${selectedFields.size} campo(s)`}
                </MtButton>
              </div>
            </div>
          )}

          {step === 2 && applyMut.data && (
            <div className="space-y-3">
              <div className="flex items-center gap-2" style={{ color: MT.success ?? "green" }}>
                <CheckCircle2 className="size-5" />
                <span className="font-medium text-sm">
                  {applyMut.data.applied_fields.length} campo(s) aplicados correctamente
                </span>
              </div>
              {applyMut.data.applied_fields.length > 0 && (
                <ul className="pl-6 list-disc text-[12.5px] space-y-0.5" style={{ color: MT.ink }}>
                  {applyMut.data.applied_fields.map((f) => <li key={f}>{f}</li>)}
                </ul>
              )}
              {applyMut.data.errors.length > 0 && (
                <div className="text-[12px]" style={{ color: "red" }}>
                  Errores: {applyMut.data.errors.join(", ")}
                </div>
              )}
              <MtButton tone="ghost" onClick={() => { setStep(0); setPreview(null); }}>
                Enriquecer con otra ficha
              </MtButton>
            </div>
          )}
        </div>
      </SectionCard>
    </div>
  );
}
```

- [ ] **Step 3: Añadir tab en el layout del SKU (si existe nav bar)**

Buscar `mt-pricing-frontend/app/(app)/catalogo/[sku]/layout.tsx` — si tiene una lista de tabs (array con `href` y `label`), añadir:
```typescript
{ href: `/catalogo/${sku}/enriquecer`, label: "Enriquecer" },
```

- [ ] **Step 4: Verificar TypeScript**

```bash
cd mt-pricing-frontend
npx tsc --noEmit 2>&1 | grep -E "enriquec|ficha-enrich" | head -20
```
Expected: sin errores en los archivos nuevos.

- [ ] **Step 5: Commit**

```bash
git add mt-pricing-frontend/app/(app)/catalogo/\[sku\]/enriquecer/ mt-pricing-frontend/app/(app)/catalogo/\[sku\]/layout.tsx
git commit -m "feat(ficha-enrich): página /enriquecer — wizard upload→diff→apply"
```

---

## Task 10: E2E Validation — MTFT_4097.pdf → SKU 4097015

- [ ] **Step 1: Rebuild frontend**

```bash
docker restart mt-frontend
```

- [ ] **Step 2: Navegar a `http://localhost:3000/catalogo/4097015/enriquecer`**

- [ ] **Step 3: Subir `MTFT_4097.pdf` en la página**

Verificar en la UI:
- `confidence` ≥ 80%
- Campos con cambio incluyen: `pn`, `temp_min_c`, `temp_max_c`, `material`, `connection`, `brand`
- `specs` incluye `seat_material=ptfe`, `seal_material=nbr`
- `materials` tiene 3 filas (body, seat, seal)
- `dimensions_by_dn` tiene las filas de 1/4" a 2"
- `model_gaps` lista los campos no mapeados (validación del modelo)

- [ ] **Step 4: Seleccionar todos los campos y hacer Apply**

Verificar en la UI (step 2):
- `applied_fields` lista todos los campos seleccionados
- `errors` vacío

- [ ] **Step 5: Verificar en DB**

```bash
# Conectar al Supabase local:
psql postgresql://postgres:postgres@localhost:54322/postgres -c \
  "SELECT sku, pn, temp_min_c, temp_max_c, material, connection, data_quality FROM products WHERE sku = '4097015';"
```

Expected:
```
sku     | pn | temp_min_c | temp_max_c | material       | connection
--------+----+------------+------------+----------------+-----------
4097015 | 30 | -20        | 120        | brass_cw617n   | bsp
```

- [ ] **Step 6: Verificar materials en DB**

```bash
psql postgresql://postgres:postgres@localhost:54322/postgres -c \
  "SELECT product_sku, component, material FROM product_materials WHERE product_sku = '4097015';"
```

Expected: 3 filas (body, seat, seal)

- [ ] **Step 7: Commit de resultado**

```bash
git commit --allow-empty -m "test(ficha-enrich): E2E MTFT_4097 → 4097015 validado — model_gaps documentados en issue"
```

---

---

## Task 11: Backend — Clasificación de páginas y extracción de assets visuales

Cada página del PDF se clasifica en: `specs_text` | `dimension_drawing` | `section_drawing` | `pt_curve` | `certificate` | `exploded_view` | `materials_table` | `other`. Las páginas de plano/certificado se renderizan a PNG y se suben a Supabase Storage como `ProductAsset`.

**Files:**
- Modify: `mt-pricing-backend/app/schemas/ficha_enrich.py` — añadir `PageClassification`, `ExtractedAsset`, campos en `FichaExtractionResult` y `FichaEnrichApplyRequest`
- Modify: `mt-pricing-backend/app/services/ficha_enrichment/extractor.py` — clasificar páginas con Claude + renderizar
- Modify: `mt-pricing-backend/app/services/ficha_enrichment/applier.py` — subir PNG a Supabase Storage + crear ProductAsset rows
- Test: `mt-pricing-backend/tests/unit/services/ficha_enrichment/test_page_classifier.py`

**Prerrequisito:** `pdfplumber.to_image()` ya usado en `vision_extractor.py`. Supabase Storage client disponible en `app.core.config.settings.SUPABASE_URL` + `SUPABASE_SERVICE_KEY`.

- [ ] **Step 1: Añadir tipos en `ficha_enrich.py`**

Añadir después de `ExtractedTranslation`:

```python
class PageClassification(BaseModel):
    page_index: int           # 0-based
    kind: str                 # "specs_text" | "dimension_drawing" | "section_drawing"
                              # | "pt_curve" | "certificate" | "exploded_view"
                              # | "materials_table" | "other"
    confidence: float = Field(ge=0.0, le=1.0)
    description: str = ""     # breve descripción del contenido de la página


class ExtractedAsset(BaseModel):
    page_index: int
    asset_kind: str           # mapea a ProductAsset.kind: "dimension_drawing" |
                              # "section_drawing" | "certificate_pdf" | "exploded_3d"
    storage_path: str = ""    # se rellena tras subir a Supabase Storage
    mime_type: str = "image/png"
    description: str = ""
```

Añadir campos en `FichaExtractionResult`:

```python
    page_classifications: list[PageClassification] = Field(default_factory=list)
    extracted_assets: list[ExtractedAsset] = Field(default_factory=list)
    pt_curve_points: list[dict[str, float]] = Field(
        default_factory=list,
        description="Puntos de curva P/T extraídos: [{temperature_c, pressure_max_bar}]"
    )
```

Añadir en `FichaEnrichApplyRequest`:

```python
    apply_assets: bool = True
    apply_pt_curve: bool = True
```

- [ ] **Step 2: Añadir clasificador de páginas en `extractor.py`**

Añadir método `_classify_pages` en `FichaEnrichmentExtractor`:

```python
_PAGE_CLASSIFICATION_TOOL: dict[str, Any] = {
    "name": "classify_pdf_page",
    "description": "Clasifica una página de ficha técnica PVF.",
    "input_schema": {
        "type": "object",
        "required": ["kind", "confidence"],
        "properties": {
            "kind": {
                "type": "string",
                "enum": ["specs_text", "dimension_drawing", "section_drawing",
                         "pt_curve", "certificate", "exploded_view", "materials_table", "other"],
            },
            "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "description": {"type": "string"},
        },
    },
}

_PAGE_CLASSIFICATION_PROMPT = (
    "You are a PVF datasheet page classifier.\n"
    "Classify this PDF page into exactly one category:\n"
    "- specs_text: text with technical specs (temp, pressure, materials, standards)\n"
    "- dimension_drawing: dimensional drawing with measurements (L, H, A, etc.)\n"
    "- section_drawing: cross-section view showing internal components\n"
    "- pt_curve: pressure-temperature curve or chart\n"
    "- certificate: certification page (CE, WRAS, ACS, etc.)\n"
    "- exploded_view: exploded/assembly view showing parts\n"
    "- materials_table: table listing materials by component\n"
    "- other: cover page, legal text, contact info\n"
    "Respond using the classify_pdf_page tool."
)

_ASSET_KIND_MAP = {
    "dimension_drawing": "dimension_drawing",
    "section_drawing": "section_drawing",
    "exploded_view": "exploded_3d",
    "certificate": "certificate_pdf",
}


async def _classify_pages(
    self,
    pdf_bytes: bytes,
    client: Any,
    max_pages: int = 9,
) -> tuple[list[PageClassification], list[ExtractedAsset]]:
    """Renderiza páginas a PNG y clasifica cada una con Claude vision."""
    from app.services.importer_datasheets.vision_extractor import _render_pdf_pages
    from app.schemas.ficha_enrich import ExtractedAsset, PageClassification

    pngs = _render_pdf_pages(pdf_bytes, max_pages=max_pages, resolution=120)
    classifications: list[PageClassification] = []
    assets: list[ExtractedAsset] = []

    for idx, png in enumerate(pngs):
        b64 = base64.b64encode(png).decode("ascii")
        try:
            resp = await client.messages.create(
                model=self._model,
                max_tokens=256,
                tools=[_PAGE_CLASSIFICATION_TOOL],
                tool_choice={"type": "tool", "name": "classify_pdf_page"},
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": _PAGE_CLASSIFICATION_PROMPT},
                        {"type": "image", "source": {
                            "type": "base64", "media_type": "image/png", "data": b64
                        }},
                    ],
                }],
            )
        except Exception as exc:
            logger.warning("page_classify failed idx=%d err=%s", idx, exc)
            continue

        tool_input = _parse_tool_response(resp)
        kind = tool_input.get("kind", "other")
        clf = PageClassification(
            page_index=idx,
            kind=kind,
            confidence=float(tool_input.get("confidence", 0.5)),
            description=tool_input.get("description", ""),
        )
        classifications.append(clf)

        if kind in _ASSET_KIND_MAP:
            assets.append(ExtractedAsset(
                page_index=idx,
                asset_kind=_ASSET_KIND_MAP[kind],
                description=clf.description,
                mime_type="image/png",
            ))

    return classifications, assets
```

Llamar `_classify_pages` al final de `extract()`, antes del return, y añadir los resultados al `FichaExtractionResult`:

```python
        # Después del bloque principal de extracción Claude:
        if self._is_enabled():
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=self._api_key)
            page_clfs, page_assets = await self._classify_pages(pdf_bytes, client)
            result.page_classifications = page_clfs
            result.extracted_assets = page_assets
```

- [ ] **Step 3: Test clasificación de páginas**

```python
# mt-pricing-backend/tests/unit/services/ficha_enrichment/test_page_classifier.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.ficha_enrichment.extractor import (
    FichaEnrichmentExtractor,
    _PAGE_CLASSIFICATION_TOOL,
)

def _make_clf_response(kind: str, confidence: float = 0.9):
    block = MagicMock()
    block.type = "tool_use"
    block.name = "classify_pdf_page"
    block.input = {"kind": kind, "confidence": confidence, "description": "test"}
    resp = MagicMock()
    resp.content = [block]
    return resp


@pytest.mark.asyncio
async def test_classify_pages_dimension_drawing(monkeypatch):
    monkeypatch.setenv("MT_LIVE_NETWORK", "true")
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=_make_clf_response("dimension_drawing"))

    extractor = FichaEnrichmentExtractor(api_key="sk-test")
    fake_pngs = [b"\x89PNG\r\n\x1a\n"]  # PNG magic bytes

    with patch(
        "app.services.importer_datasheets.vision_extractor._render_pdf_pages",
        return_value=fake_pngs,
    ):
        clfs, assets = await extractor._classify_pages(b"%PDF", mock_client)

    assert len(clfs) == 1
    assert clfs[0].kind == "dimension_drawing"
    assert len(assets) == 1
    assert assets[0].asset_kind == "dimension_drawing"


@pytest.mark.asyncio
async def test_classify_pages_specs_text_no_asset(monkeypatch):
    monkeypatch.setenv("MT_LIVE_NETWORK", "true")
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=_make_clf_response("specs_text"))

    extractor = FichaEnrichmentExtractor(api_key="sk-test")
    with patch(
        "app.services.importer_datasheets.vision_extractor._render_pdf_pages",
        return_value=[b"\x89PNG\r\n\x1a\n"],
    ):
        clfs, assets = await extractor._classify_pages(b"%PDF", mock_client)

    assert clfs[0].kind == "specs_text"
    assert assets == []  # specs_text no genera asset
```

- [ ] **Step 4: Correr test**

```bash
cd mt-pricing-backend
python -m pytest tests/unit/services/ficha_enrichment/test_page_classifier.py -v
```
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add mt-pricing-backend/app/schemas/ficha_enrich.py \
        mt-pricing-backend/app/services/ficha_enrichment/extractor.py \
        mt-pricing-backend/tests/unit/services/ficha_enrichment/test_page_classifier.py
git commit -m "feat(ficha-enrich): clasificación de páginas PDF — planos, certificados, P/T, vistas"
```

---

## Task 12: Backend — Extracción de curva P/T y subida de assets a Storage

**Files:**
- Modify: `mt-pricing-backend/app/services/ficha_enrichment/extractor.py` — extraer puntos P/T de páginas tipo `pt_curve`
- Modify: `mt-pricing-backend/app/services/ficha_enrichment/applier.py` — subir PNGs a Supabase Storage + crear `ProductAsset` + insertar `PressureTemperaturePoint`

- [ ] **Step 1: Añadir extracción de curva P/T en `extractor.py`**

Añadir herramienta de extracción de curva:

```python
_PT_CURVE_TOOL: dict[str, Any] = {
    "name": "extract_pt_curve",
    "description": "Extrae puntos de la curva Presión-Temperatura de un gráfico.",
    "input_schema": {
        "type": "object",
        "required": ["points"],
        "properties": {
            "points": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["temperature_c", "pressure_max_bar"],
                    "properties": {
                        "temperature_c": {"type": "number"},
                        "pressure_max_bar": {"type": "number"},
                    },
                },
            },
        },
    },
}

_PT_CURVE_PROMPT = (
    "This is a pressure-temperature (P/T) rating curve from a PVF datasheet. "
    "Extract all visible data points from the curve. "
    "Each point has a temperature in °C (x-axis) and maximum pressure in bar (y-axis). "
    "Use the extract_pt_curve tool to return the points array."
)


async def _extract_pt_curve(self, png_bytes: bytes, client: Any) -> list[dict[str, float]]:
    b64 = base64.b64encode(png_bytes).decode("ascii")
    try:
        resp = await client.messages.create(
            model=self._model,
            max_tokens=512,
            tools=[_PT_CURVE_TOOL],
            tool_choice={"type": "tool", "name": "extract_pt_curve"},
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": _PT_CURVE_PROMPT},
                    {"type": "image", "source": {
                        "type": "base64", "media_type": "image/png", "data": b64,
                    }},
                ],
            }],
        )
    except Exception as exc:
        logger.warning("pt_curve_extract failed: %s", exc)
        return []
    tool_input = _parse_tool_response(resp)
    return [
        {"temperature_c": float(p["temperature_c"]), "pressure_max_bar": float(p["pressure_max_bar"])}
        for p in (tool_input.get("points") or [])
        if "temperature_c" in p and "pressure_max_bar" in p
    ]
```

En `extract()`, tras `_classify_pages`, para cada asset con `asset_kind` derivado de `pt_curve`:

```python
        # Extraer puntos P/T de páginas clasificadas como pt_curve
        pt_points: list[dict[str, float]] = []
        for clf in page_clfs:
            if clf.kind == "pt_curve" and clf.page_index < len(pngs):
                pts = await self._extract_pt_curve(pngs[clf.page_index], client)
                pt_points.extend(pts)
        result.pt_curve_points = pt_points
```

- [ ] **Step 2: Añadir subida de assets en `applier.py`**

```python
async def _upload_page_assets(
    self,
    sku: str,
    pdf_bytes: bytes,
    assets: list[Any],
    actor: User,
) -> list[str]:
    """Renderiza páginas de interés a PNG, sube a Supabase Storage y crea ProductAsset rows."""
    from app.services.importer_datasheets.vision_extractor import _render_pdf_pages
    from app.db.models.product import ProductAsset
    import hashlib

    pngs = _render_pdf_pages(pdf_bytes, max_pages=20, resolution=150)
    uploaded: list[str] = []

    for asset_meta in assets:
        idx = asset_meta.page_index
        if idx >= len(pngs):
            continue
        png = pngs[idx]
        sha = hashlib.sha256(png).hexdigest()[:16]
        storage_path = f"datasheets/{sku}/{asset_meta.asset_kind}_p{idx}_{sha}.png"

        # Intentar subir a Supabase Storage — si falla, registrar pero no lanzar
        try:
            from app.core.config import settings
            from supabase import create_client

            sb = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
            sb.storage.from_("product-images").upload(
                path=storage_path,
                file=png,
                file_options={"content-type": "image/png", "upsert": "true"},
            )
        except Exception as exc:
            logger.warning("asset_upload failed path=%s err=%s", storage_path, exc)
            continue

        row = ProductAsset(
            sku=sku,
            kind=asset_meta.asset_kind,
            bucket="product-images",
            storage_path=storage_path,
            mime_type="image/png",
            bytes_size=len(png),
            hash_sha256=hashlib.sha256(png).hexdigest(),
            caption=asset_meta.description or None,
            status="active",
            created_by=actor.id,
        )
        self._session.add(row)
        uploaded.append(storage_path)

    await self._session.flush()
    return uploaded
```

Llamar en `apply()` si `request.apply_assets`:

```python
        if request.apply_assets and request.extraction.extracted_assets:
            try:
                uploaded = await self._upload_page_assets(
                    sku, pdf_bytes_cache, request.extraction.extracted_assets, actor
                )
                if uploaded:
                    applied.append(f"assets({len(uploaded)})")
            except Exception as exc:
                errors.append(f"assets: {exc}")
```

> **Nota:** `pdf_bytes_cache` requiere pasar los bytes del PDF al applier. Actualizar la firma de `apply()` para incluir `pdf_bytes: bytes | None = None`.

- [ ] **Step 3: Insertar puntos P/T en `applier.py`**

```python
async def _upsert_pt_curve(self, sku: str, points: list[dict[str, float]]) -> None:
    from app.db.models.dimensions import PressureTemperaturePoint

    # Borrar curva existente del producto
    existing = (await self._session.execute(
        select(PressureTemperaturePoint).where(PressureTemperaturePoint.product_sku == sku)
    )).scalars().all()
    for row in existing:
        await self._session.delete(row)
    await self._session.flush()

    for order, pt in enumerate(points):
        self._session.add(PressureTemperaturePoint(
            product_sku=sku,
            temperature_c=pt["temperature_c"],
            pressure_max_bar=pt["pressure_max_bar"],
            order_index=order,
        ))
    await self._session.flush()
```

Llamar en `apply()` si `request.apply_pt_curve`:

```python
        if request.apply_pt_curve and request.extraction.pt_curve_points:
            try:
                await self._upsert_pt_curve(sku, request.extraction.pt_curve_points)
                applied.append(f"pt_curve({len(request.extraction.pt_curve_points)} pts)")
            except Exception as exc:
                errors.append(f"pt_curve: {exc}")
```

- [ ] **Step 4: Commit**

```bash
git add mt-pricing-backend/app/services/ficha_enrichment/extractor.py \
        mt-pricing-backend/app/services/ficha_enrichment/applier.py
git commit -m "feat(ficha-enrich): extracción curva P/T + subida assets PNG a Supabase Storage"
```

---

## Task 13: Frontend — Mostrar assets extraídos y curva P/T en la UI

**Files:**
- Modify: `mt-pricing-frontend/lib/api/endpoints/ficha-enrich.ts` — añadir tipos `PageClassification`, `ExtractedAsset`
- Modify: `mt-pricing-frontend/app/(app)/catalogo/[sku]/enriquecer/_client.tsx` — sección de preview de páginas clasificadas

- [ ] **Step 1: Añadir tipos en `ficha-enrich.ts`**

```typescript
export interface PageClassification {
  page_index: number;
  kind: "specs_text" | "dimension_drawing" | "section_drawing" | "pt_curve"
      | "certificate" | "exploded_view" | "materials_table" | "other";
  confidence: number;
  description: string;
}

export interface ExtractedAsset {
  page_index: number;
  asset_kind: string;
  description: string;
  mime_type: string;
}
```

Añadir en `FichaExtractionResult`:
```typescript
  page_classifications: PageClassification[];
  extracted_assets: ExtractedAsset[];
  pt_curve_points: Array<{ temperature_c: number; pressure_max_bar: number }>;
```

- [ ] **Step 2: Mostrar páginas clasificadas en `_client.tsx`**

Añadir sección después del `EnrichmentDiffTable` en step 1:

```typescript
{/* Páginas clasificadas */}
{preview.extraction.page_classifications.length > 0 && (
  <div className="space-y-2">
    <p className="text-[12.5px] font-medium" style={{ color: MT.ink }}>
      Páginas detectadas ({preview.extraction.page_classifications.length})
    </p>
    <div className="flex flex-wrap gap-2">
      {preview.extraction.page_classifications.map((clf) => (
        <div key={clf.page_index}
          className="flex items-center gap-1.5 rounded px-2 py-1 text-[11.5px]"
          style={{ background: MT.surface, border: `1px solid ${MT.border}` }}>
          <span className="mt-mono font-medium" style={{ color: MT.ink }}>
            p.{clf.page_index + 1}
          </span>
          <Pill tone={clf.kind === "specs_text" ? "neutral" : "brand"} size="sm">
            {clf.kind.replace(/_/g, " ")}
          </Pill>
          <span style={{ color: MT.ink3 }}>
            {(clf.confidence * 100).toFixed(0)}%
          </span>
        </div>
      ))}
    </div>
  </div>
)}

{/* Assets a subir */}
{preview.extraction.extracted_assets.length > 0 && (
  <div className="text-[12.5px] space-y-1">
    <p className="font-medium" style={{ color: MT.ink }}>
      Assets a crear ({preview.extraction.extracted_assets.length})
    </p>
    <ul className="pl-4 list-disc space-y-0.5" style={{ color: MT.ink3 }}>
      {preview.extraction.extracted_assets.map((a) => (
        <li key={`${a.page_index}-${a.asset_kind}`}>
          Pág. {a.page_index + 1} → <strong>{a.asset_kind}</strong>
          {a.description ? ` — ${a.description}` : ""}
        </li>
      ))}
    </ul>
  </div>
)}

{/* Curva P/T */}
{preview.extraction.pt_curve_points.length > 0 && (
  <div className="text-[12.5px]">
    <p className="font-medium" style={{ color: MT.ink }}>
      Curva P/T — {preview.extraction.pt_curve_points.length} puntos extraídos
    </p>
    <div className="mt-1 flex flex-wrap gap-2">
      {preview.extraction.pt_curve_points.slice(0, 6).map((pt, i) => (
        <span key={i} className="mt-mono text-[11px] px-1.5 py-0.5 rounded"
          style={{ background: MT.surface, color: MT.ink }}>
          {pt.temperature_c}°C → {pt.pressure_max_bar} bar
        </span>
      ))}
      {preview.extraction.pt_curve_points.length > 6 && (
        <span style={{ color: MT.ink3 }}>
          +{preview.extraction.pt_curve_points.length - 6} más
        </span>
      )}
    </div>
  </div>
)}
```

- [ ] **Step 3: Rebuild frontend y verificar UI**

```bash
docker restart mt-frontend
```

Navegar a `http://localhost:3000/catalogo/4097015/enriquecer`, subir `MTFT_4097.pdf` y verificar que aparecen:
- Lista de páginas clasificadas con kind y confianza
- Lista de assets detectados (planos, vistas)
- Curva P/T si la ficha la incluye

- [ ] **Step 4: Commit**

```bash
git add mt-pricing-frontend/lib/api/endpoints/ficha-enrich.ts \
        mt-pricing-frontend/app/\(app\)/catalogo/\[sku\]/enriquecer/_client.tsx
git commit -m "feat(ficha-enrich): UI — páginas clasificadas, assets extraídos, curva P/T"
```

---

## Self-Review — Spec coverage

| Requisito | Tarea |
|-----------|-------|
| Upload PDF ficha técnica | Task 5 (endpoint preview) |
| Extracción de todos los campos con Claude | Task 2 (extractor) |
| Mapeo a campos del modelo de datos | Task 2 + Task 3 |
| Diff interactivo campo-a-campo | Task 8 (component) |
| Apply selectivo por campo | Task 4 (applier) + Task 9 (UI) |
| Validar modelo: `model_gaps` | Task 2 (prompt) + Task 9 (UI) |
| Reutiliza infraestructura existente | Task 2 usa `pdf_extractor.py` existente |
| Sin migración DB | Confirmado — usa tablas existentes |
| Test con MTFT_4097.pdf → 4097015 | Task 10 |
| Materials como filas estructuradas | Task 4 applier + Task 2 extractor |
| Tabla dimensiones → tech_tables | Task 4 applier + Task 2 extractor |
| **Clasificación páginas** (planos, certificados, P/T) | Task 11 |
| **Extracción curva P/T** desde gráfico | Task 12 |
| **Subida de assets** (PNG) a Supabase Storage | Task 12 applier |
| **UI assets + P/T** en wizard | Task 13 |

**Posibles model_gaps esperados de MTFT_4097.pdf:**
- Tabla de par de apriete (torque table)
- Kv / Cv flow coefficient
- Número de ciclos garantizados
- Dimensiones de maneta específicas
- Hangtag/etiqueta personalizada

Estos son los gaps que validarán si el modelo necesita ampliarse.

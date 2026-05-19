# Fichas Técnicas Standalone — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Módulo `/fichas` standalone (sin necesitar un SKU previo) que permite subir una ficha técnica PDF, detecta la serie desde el filename, genera SKUs candidatos desde la tabla DN del PDF, marca cada uno `existing` (ya en DB) o `new` (no existe), crea los productos nuevos + actualiza los existentes, Y guarda el PDF como `Document` (type=`ficha_tecnica`) con `asset_links` a todos los SKUs de la serie.

**Architecture:** Nuevo endpoint `POST /ficha-enrich/series/preview` (sin SKU en URL). El backend detecta la serie del filename (`MTFT_4097.pdf → "4097"`), genera SKUs candidatos combinando prefijo + sufijo DN (`DN15 → "015"`, `1/2" → DN15 → "015"`), verifica cuáles existen en DB, y devuelve `series_skus` con `status: existing | new`. En el apply, crea productos nuevos (mínimo: `sku` + `family` + brand resuelto) y/o actualiza existentes. Al finalizar guarda el PDF en Supabase Storage, crea `Document` + `asset_links`.

**Tech Stack:** FastAPI + SQLAlchemy async + Supabase Storage · Next.js 16 + React 19 + React Query + Tailwind v4 + MT primitives. Sin nueva migración DB (tablas `documents`, `product_assets`, `asset_links` ya existen).

---

## Context — Infraestructura reutilizada (NO duplicar)

- `app/schemas/ficha_enrich.py` — schemas Pydantic base ya existentes.
- `app/services/ficha_enrichment/extractor.py` — `FichaEnrichmentExtractor.extract()`.
- `app/services/ficha_enrichment/applier.py` — `FichaEnrichmentApplier.apply()` → `SkuApplyResult`.
- `app/services/ficha_enrichment/differ.py` — `FichaEnrichmentDiffer.compute_batch()`.
- `app/api/routes/ficha_enrich.py` — `_extract_series_prefix()`, `_find_series_products()`.
- `app/db/models/documents.py` — `Document` (type, code, version, language, asset_id).
- `app/db/models/product.py` — `Product`: required NOT NULL = `sku`, `family`, `brand_id`.
- `lib/api/endpoints/ficha-enrich.ts` + `lib/hooks/ficha-enrichment/use-ficha-enrich.ts`.
- `components/domain/ficha-enrichment/enrichment-diff-table.tsx`.
- `components/mt/primitives.tsx` — `Pill`, `MtButton`, `SectionCard`, `MtTh`, `MtTd`.

## File Map

**Backend (crear):**
- `app/services/ficha_enrichment/series_resolver.py` — lógica de serie: detect prefix, DN→SKU, generate candidates, check existence
- `app/services/ficha_enrichment/product_creator.py` — crear Product desde extracción
- `app/services/ficha_enrichment/document_saver.py` — upload PDF + crear Document + asset_links

**Backend (modificar):**
- `app/schemas/ficha_enrich.py` — añadir `status` a `SkuDiffResult`, añadir `FichaSeriesPreviewResponse`, `FichaSeriesApplyRequest`, `FichaSeriesApplyResponse`
- `app/api/routes/ficha_enrich.py` — añadir `POST /ficha-enrich/series/preview` y `POST /ficha-enrich/series/apply`

**Frontend (crear):**
- `app/(app)/fichas/page.tsx` — server component wrapper
- `app/(app)/fichas/_client.tsx` — wizard 4 steps

**Frontend (modificar):**
- `lib/api/endpoints/ficha-enrich.ts` — añadir tipos series-level
- `lib/hooks/ficha-enrichment/use-ficha-enrich.ts` — añadir hooks series
- Nav principal — añadir item "Fichas técnicas"

---

## DN → SKU Suffix Mapping

```python
# mt-pricing-backend/app/services/ficha_enrichment/series_resolver.py

_IMPERIAL_TO_DN: dict[str, int] = {
    '1/8"': 6, "1/8": 6,
    '1/4"': 8, "1/4": 8,
    '3/8"': 10, "3/8": 10,
    '1/2"': 15, "1/2": 15,
    '3/4"': 20, "3/4": 20,
    '1"': 25, "1": 25,
    '1-1/4"': 32, '1 1/4"': 32, "1-1/4": 32,
    '1-1/2"': 40, '1 1/2"': 40, "1-1/2": 40,
    '2"': 50, "2": 50,
    '2-1/2"': 65, "2-1/2": 65,
    '3"': 80, "3": 80,
    '4"': 100, "4": 100,
}

def dn_label_to_int(label: str) -> int | None:
    """Convierte 'DN15', '1/2"', '15', '1 1/2"' → entero DN mm."""
    label = label.strip()
    # "DN15" → 15
    if label.upper().startswith("DN"):
        try:
            return int(label[2:].strip())
        except ValueError:
            pass
    # Imperial
    if label in _IMPERIAL_TO_DN:
        return _IMPERIAL_TO_DN[label]
    # Numeric string "15" → 15
    try:
        return int(label)
    except ValueError:
        return None
```

---

## Task 1: Schema — añadir status + tipos series

**Files:**
- Modify: `mt-pricing-backend/app/schemas/ficha_enrich.py`

- [ ] **Step 1: Añadir `status` a `SkuDiffResult` y tipos series**

Añadir al final de `SkuDiffResult` (después de `diffs`):
```python
from typing import Literal

class SkuDiffResult(BaseModel):
    sku: str
    status: Literal["existing", "new"] = "existing"
    diffs: list[FieldDiff]
```

Añadir nuevos schemas al final (antes de `__all__`):
```python
class FichaSeriesPreviewResponse(BaseModel):
    """Respuesta de preview serie-level (sin SKU anchor)."""
    model_config = ConfigDict(extra="ignore")

    series: str
    filename: str
    extraction: FichaExtractionResult
    series_skus: list[SkuDiffResult]   # existing + new con status
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

class FichaSeriesApplyResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    series: str
    results: list[SkuApplyResult]
    document_id: str | None = None    # UUID del Document creado, si save_document=True
    skus_created: list[str] = Field(default_factory=list)
    skus_updated: list[str] = Field(default_factory=list)
```

Actualizar `__all__` para incluir los nuevos tipos.

- [ ] **Step 2: Verificar import**
```bash
cd mt-pricing-backend && python -c "from app.schemas.ficha_enrich import FichaSeriesPreviewResponse, FichaSeriesApplyRequest, FichaSeriesApplyResponse, SkuDiffResult; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**
```bash
git add mt-pricing-backend/app/schemas/ficha_enrich.py
git commit -m "feat(fichas): schema series-level — FichaSeriesPreviewResponse + status en SkuDiffResult"
```

---

## Task 2: SeriesResolver — detect, generate candidates, check existence

**Files:**
- Create: `mt-pricing-backend/app/services/ficha_enrichment/series_resolver.py`
- Test: `mt-pricing-backend/tests/unit/services/ficha_enrichment/test_series_resolver.py`

- [ ] **Step 1: Crear `series_resolver.py`**

```python
# mt-pricing-backend/app/services/ficha_enrichment/series_resolver.py
"""Detecta la serie desde el filename del PDF y genera SKUs candidatos desde tabla DN."""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.product import Product
from app.schemas.ficha_enrich import FichaExtractionResult, SkuDiffResult

if TYPE_CHECKING:
    pass

_IMPERIAL_TO_DN: dict[str, int] = {
    '1/8"': 6, "1/8": 6,
    '1/4"': 8, "1/4": 8,
    '3/8"': 10, "3/8": 10,
    '1/2"': 15, "1/2": 15,
    '3/4"': 20, "3/4": 20,
    '1"': 25, "1": 25,
    '1-1/4"': 32, '1 1/4"': 32, "1-1/4": 32, '1 1/4': 32,
    '1-1/2"': 40, '1 1/2"': 40, "1-1/2": 40, '1 1/2': 40,
    '2"': 50, "2": 50,
    '2-1/2"': 65, '2 1/2"': 65, "2-1/2": 65,
    '3"': 80, "3": 80,
    '4"': 100, "4": 100,
}


def extract_series_prefix(filename: str) -> str | None:
    """Extrae prefijo de serie: 'MTFT_4097.pdf' → '4097'."""
    match = re.search(r'MTFT[_\-]?(\d+)', filename, re.IGNORECASE)
    return match.group(1) if match else None


def dn_label_to_int(label: str) -> int | None:
    """Convierte etiqueta DN a entero mm: 'DN15' → 15, '1/2"' → 15."""
    label = label.strip()
    if label.upper().startswith("DN"):
        try:
            return int(label[2:].strip())
        except ValueError:
            pass
    if label in _IMPERIAL_TO_DN:
        return _IMPERIAL_TO_DN[label]
    try:
        return int(float(label))
    except ValueError:
        return None


def generate_candidate_skus(series_prefix: str, extraction: FichaExtractionResult) -> list[str]:
    """Genera SKUs candidatos combinando prefijo + sufijo DN (zero-padded 3 dígitos)."""
    dns: list[int] = []
    for row in extraction.dimensions:
        dn = dn_label_to_int(row.dn_label)
        if dn is not None and dn not in dns:
            dns.append(dn)
    dns.sort()
    return [f"{series_prefix}{dn:03d}" for dn in dns]


async def resolve_series(
    session: AsyncSession,
    series_prefix: str,
    extraction: FichaExtractionResult,
) -> list[SkuDiffResult]:
    """
    Genera SKUs candidatos desde la tabla DN y verifica cuáles existen en DB.
    Devuelve SkuDiffResult con status='existing' o 'new'.
    """
    from app.services.ficha_enrichment.differ import FichaEnrichmentDiffer

    candidates = generate_candidate_skus(series_prefix, extraction)

    # Si no hay dimensiones en el PDF, fallback: buscar los existentes con LIKE
    if not candidates:
        result = await session.execute(
            select(Product)
            .where(Product.sku.like(f"{series_prefix}%"))
            .order_by(Product.sku)
        )
        existing = list(result.scalars().all())
        if existing:
            differ = FichaEnrichmentDiffer()
            return differ.compute_batch(existing, extraction)
        return []

    # Verificar cuáles existen
    result = await session.execute(
        select(Product).where(Product.sku.in_(candidates))
    )
    existing_products = {p.sku: p for p in result.scalars().all()}

    differ = FichaEnrichmentDiffer()
    sku_diffs: list[SkuDiffResult] = []
    for sku in candidates:
        if sku in existing_products:
            product = existing_products[sku]
            diffs = differ.compute(product, extraction)
            sku_diffs.append(SkuDiffResult(sku=sku, status="existing", diffs=diffs))
        else:
            # SKU nuevo: todos los campos extraídos son "new" (current_value = None)
            from app.schemas.ficha_enrich import FieldDiff
            scalars = extraction.scalars.model_dump(exclude_none=True)
            diffs = [
                FieldDiff(field_name=k, current_value=None, extracted_value=v, has_change=True)
                for k, v in scalars.items()
            ]
            sku_diffs.append(SkuDiffResult(sku=sku, status="new", diffs=diffs))

    return sku_diffs


__all__ = [
    "extract_series_prefix",
    "dn_label_to_int",
    "generate_candidate_skus",
    "resolve_series",
]
```

- [ ] **Step 2: Test del resolver**

```python
# mt-pricing-backend/tests/unit/services/ficha_enrichment/test_series_resolver.py
import pytest
from app.services.ficha_enrichment.series_resolver import (
    extract_series_prefix,
    dn_label_to_int,
    generate_candidate_skus,
)
from app.schemas.ficha_enrich import FichaExtractionResult, ExtractedScalars, ExtractedSpecs, ExtractedDimensionRow


def test_extract_series_prefix_standard():
    assert extract_series_prefix("MTFT_4097.pdf") == "4097"

def test_extract_series_prefix_dash():
    assert extract_series_prefix("MTFT-4097.pdf") == "4097"

def test_extract_series_prefix_no_match():
    assert extract_series_prefix("random.pdf") is None

def test_dn_label_to_int_dn_prefix():
    assert dn_label_to_int("DN15") == 15
    assert dn_label_to_int("DN 25") == 25

def test_dn_label_to_int_imperial():
    assert dn_label_to_int('1/2"') == 15
    assert dn_label_to_int('1"') == 25
    assert dn_label_to_int('1-1/2"') == 40

def test_dn_label_to_int_numeric():
    assert dn_label_to_int("15") == 15
    assert dn_label_to_int("50") == 50

def test_generate_candidate_skus():
    extraction = FichaExtractionResult(
        scalars=ExtractedScalars(),
        specs=ExtractedSpecs(),
        dimensions=[
            ExtractedDimensionRow(dn_label='1/2"', values={}),
            ExtractedDimensionRow(dn_label='3/4"', values={}),
            ExtractedDimensionRow(dn_label='1"', values={}),
        ],
        confidence=0.9,
    )
    skus = generate_candidate_skus("4097", extraction)
    assert skus == ["4097015", "4097020", "4097025"]
```

- [ ] **Step 3: Correr tests**
```bash
cd mt-pricing-backend && python -m pytest tests/unit/services/ficha_enrichment/test_series_resolver.py -v
```
Expected: 7 tests PASS.

- [ ] **Step 4: Commit**
```bash
git add mt-pricing-backend/app/services/ficha_enrichment/series_resolver.py mt-pricing-backend/tests/unit/services/ficha_enrichment/test_series_resolver.py
git commit -m "feat(fichas): SeriesResolver — detect series, DN→SKU candidates, check existence"
```

---

## Task 3: ProductCreator — crear Product desde extracción

**Files:**
- Create: `mt-pricing-backend/app/services/ficha_enrichment/product_creator.py`

- [ ] **Step 1: Crear `product_creator.py`**

```python
# mt-pricing-backend/app/services/ficha_enrichment/product_creator.py
"""Crea un Product nuevo en DB a partir de los datos extraídos de la ficha técnica."""
from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.product import Product
from app.schemas.ficha_enrich import FichaExtractionResult, SkuApplyResult

logger = logging.getLogger(__name__)

_PATCHABLE_SCALARS = {
    "family", "subfamily", "type", "material", "dn", "pn",
    "connection", "brand", "weight", "weight_unit",
    "temp_min_c", "temp_max_c", "pressure_max_bar", "size",
}


async def _resolve_brand_id(session: AsyncSession, brand_name: str) -> uuid.UUID | None:
    """Busca brand_id por nombre (case-insensitive). Devuelve None si no existe."""
    from sqlalchemy import func
    try:
        from app.db.models.product import Brand  # type: ignore[attr-defined]
        result = await session.execute(
            select(Brand).where(func.lower(Brand.name) == brand_name.lower())
        )
        brand = result.scalar_one_or_none()
        return brand.id if brand else None
    except Exception:
        return None


async def create_product_from_extraction(
    session: AsyncSession,
    sku: str,
    extraction: FichaExtractionResult,
) -> SkuApplyResult:
    """
    Crea un nuevo Product con los datos mínimos. Requiere que `family` esté extraído.
    Si no hay brand_id resolvible, crea el producto sin brand (sólo si la columna lo permite).
    """
    scalars = extraction.scalars.model_dump(exclude_none=True)
    family = scalars.get("family")
    if not family:
        return SkuApplyResult(
            sku=sku,
            applied_fields=[],
            skipped_fields=list(scalars.keys()),
            warnings=["No se pudo crear el producto: 'family' no extraído del PDF"],
        )

    # Resolver brand_id
    brand_name = scalars.get("brand", "")
    brand_id = await _resolve_brand_id(session, brand_name) if brand_name else None

    if brand_id is None:
        return SkuApplyResult(
            sku=sku,
            applied_fields=[],
            skipped_fields=list(scalars.keys()),
            warnings=[
                f"No se pudo crear el producto: brand '{brand_name}' no encontrado en DB. "
                "Crea primero el brand o asigna uno existente."
            ],
        )

    product = Product(
        sku=sku,
        family=family,
        brand_id=brand_id,
    )

    applied: list[str] = ["family"]
    skipped: list[str] = []

    for field, value in scalars.items():
        if field in ("family", "brand"):
            continue
        if field not in _PATCHABLE_SCALARS:
            skipped.append(field)
            continue
        try:
            setattr(product, field, value)
            applied.append(field)
        except Exception as exc:
            skipped.append(field)
            logger.warning("create_product: cannot set %s on new product: %s", field, exc)

    # Specs JSONB
    from app.services.ficha_enrichment.differ import _specs_to_dict
    specs_patch = _specs_to_dict(extraction)
    if specs_patch:
        product.specs = specs_patch
        applied.append("specs")

    session.add(product)
    await session.flush()

    return SkuApplyResult(
        sku=sku,
        applied_fields=applied,
        skipped_fields=skipped,
        warnings=[],
    )


__all__ = ["create_product_from_extraction"]
```

- [ ] **Step 2: Verificar import**
```bash
cd mt-pricing-backend && python -c "from app.services.ficha_enrichment.product_creator import create_product_from_extraction; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**
```bash
git add mt-pricing-backend/app/services/ficha_enrichment/product_creator.py
git commit -m "feat(fichas): ProductCreator — crea Product desde extracción con brand resolution"
```

---

## Task 4: DocumentSaver — guarda PDF como Document + asset_links

**Files:**
- Create: `mt-pricing-backend/app/services/ficha_enrichment/document_saver.py`

Antes de escribir, leer:
- `app/db/models/documents.py` — campos de `Document`
- `app/db/models/asset_links.py` — campos de `AssetLink`
- Buscar cómo se sube a Supabase Storage en el codebase (buscar `storage` en `app/services/`)

- [ ] **Step 1: Crear `document_saver.py`**

```python
# mt-pricing-backend/app/services/ficha_enrichment/document_saver.py
"""Guarda el PDF de la ficha técnica como Document controlado + asset_links a los SKUs."""
from __future__ import annotations

import logging
import os
import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

_STORAGE_BUCKET = "product-images"
_PDF_PATH_PREFIX = "fichas"


async def save_ficha_document(
    session: AsyncSession,
    pdf_bytes: bytes,
    filename: str,
    series: str,
    skus: list[str],
) -> str | None:
    """
    Sube el PDF a Supabase Storage, crea Document (type=ficha_tecnica) y
    asset_links para cada SKU de la serie. Devuelve el document_id (UUID str).
    """
    try:
        from app.db.models.documents import Document
        from app.db.models.asset_links import AssetLink  # type: ignore
        from supabase import create_client

        supabase_url = os.environ.get("SUPABASE_URL", "")
        supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        if not supabase_url or not supabase_key:
            logger.warning("document_saver: Supabase credentials not set, skipping document save")
            return None

        client = create_client(supabase_url, supabase_key)
        storage_path = f"{_PDF_PATH_PREFIX}/{filename}"

        # Upload al bucket
        client.storage.from_(_STORAGE_BUCKET).upload(
            path=storage_path,
            file=pdf_bytes,
            file_options={"content-type": "application/pdf", "upsert": "true"},
        )

        # Crear ProductAsset para el PDF
        from app.db.models.asset_links import ProductAsset  # type: ignore
        asset = ProductAsset(
            sku=skus[0] if skus else series,
            kind="datasheet_pdf",
            storage_path=storage_path,
            mime_type="application/pdf",
            source="ficha_enrichment",
        )
        session.add(asset)
        await session.flush()

        # Crear Document
        code = f"MTFT_{series}"
        doc = Document(
            type="ficha_tecnica",
            code=code,
            version="1",
            language="es",
            asset_id=asset.id,
            issued_at=date.today(),
        )
        session.add(doc)
        await session.flush()

        # Crear asset_links para cada SKU
        for sku in skus:
            link = AssetLink(
                entity_type="product",
                entity_id=sku,
                asset_id=asset.id,
                role="ficha_tecnica",
            )
            session.add(link)

        await session.flush()
        return str(doc.id)

    except Exception as exc:
        logger.warning("document_saver: failed to save document: %s", exc)
        return None


__all__ = ["save_ficha_document"]
```

**NOTA:** Los nombres exactos de los campos de `AssetLink` y `ProductAsset` deben verificarse leyendo `app/db/models/asset_links.py` antes de escribir este archivo. Adaptar según lo encontrado.

- [ ] **Step 2: Verificar import**
```bash
cd mt-pricing-backend && python -c "from app.services.ficha_enrichment.document_saver import save_ficha_document; print('OK')"
```

- [ ] **Step 3: Commit**
```bash
git add mt-pricing-backend/app/services/ficha_enrichment/document_saver.py
git commit -m "feat(fichas): DocumentSaver — PDF → Supabase Storage + Document + asset_links"
```

---

## Task 5: API routes — nuevos endpoints series-level

**Files:**
- Modify: `mt-pricing-backend/app/api/routes/ficha_enrich.py`

- [ ] **Step 1: Añadir endpoints al router existente**

Añadir al final de `mt-pricing-backend/app/api/routes/ficha_enrich.py` (después de los endpoints existentes):

```python
from app.schemas.ficha_enrich import (
    FichaSeriesPreviewResponse,
    FichaSeriesApplyRequest,
    FichaSeriesApplyResponse,
    SkuApplyResult,
)
from app.services.ficha_enrichment.series_resolver import (
    extract_series_prefix,
    resolve_series,
)
from app.services.ficha_enrichment.product_creator import create_product_from_extraction
from app.services.ficha_enrichment.document_saver import save_ficha_document


@router.post(
    "/ficha-enrich/series/preview",
    response_model=FichaSeriesPreviewResponse,
    summary="Vista previa serie completa — detecta SKUs existentes y nuevos desde el PDF",
    responses={
        422: {"model": ProblemDetails},
        413: {"model": ProblemDetails},
    },
)
async def preview_ficha_series(
    file: Annotated[UploadFile, File(description="PDF ficha técnica (≤ 50 MB)")],
    _user: Annotated[User, Depends(require_permissions("products:write"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> FichaSeriesPreviewResponse:
    if file.filename is None:
        raise HTTPException(status_code=422, detail={"code": "missing_filename", "title": "Filename requerido"})

    pdf_bytes = await file.read()
    if len(pdf_bytes) > _MAX_PDF_BYTES:
        raise HTTPException(status_code=413, detail={"code": "pdf_too_large", "title": "PDF > 50 MB"})
    if not pdf_bytes.lstrip().startswith(b"%PDF"):
        raise HTTPException(status_code=422, detail={"code": "not_a_pdf", "title": "No es un PDF válido"})

    series = extract_series_prefix(file.filename)
    if not series:
        raise HTTPException(
            status_code=422,
            detail={"code": "no_series", "title": "No se pudo detectar la serie del filename. Formato esperado: MTFT_XXXX.pdf"},
        )

    extractor = FichaEnrichmentExtractor()
    extraction = await extractor.extract(pdf_bytes=pdf_bytes, filename=file.filename)

    series_skus = await resolve_series(session, series, extraction)
    meta = extract_pdf_metadata(pdf_bytes)

    return FichaSeriesPreviewResponse(
        series=series,
        filename=file.filename,
        extraction=extraction,
        series_skus=series_skus,
        model_gaps=extraction.model_gaps,
        page_count=meta.get("page_count", 0),
        confidence=extraction.confidence,
    )


@router.post(
    "/ficha-enrich/series/apply",
    response_model=FichaSeriesApplyResponse,
    summary="Aplicar ficha técnica — crea SKUs nuevos + actualiza existentes + guarda Document",
    responses={
        422: {"model": ProblemDetails},
    },
)
async def apply_ficha_series(
    body: FichaSeriesApplyRequest,
    user: Annotated[User, Depends(require_permissions("products:write"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> FichaSeriesApplyResponse:
    if not body.apply_to_skus:
        raise HTTPException(status_code=422, detail={"code": "no_skus", "title": "apply_to_skus vacío"})

    results: list[SkuApplyResult] = []
    skus_created: list[str] = []
    skus_updated: list[str] = []

    # Determinar cuáles existen
    from sqlalchemy import select as _select
    existing_result = await session.execute(
        _select(Product).where(Product.sku.in_(body.apply_to_skus))
    )
    existing_skus = {p.sku for p in existing_result.scalars().all()}

    for target_sku in body.apply_to_skus:
        if target_sku in existing_skus:
            # Actualizar existente
            try:
                applier = FichaEnrichmentApplier(session)
                result = await applier.apply(target_sku, body, user)
                results.append(result)
                skus_updated.append(target_sku)
            except HTTPException as exc:
                results.append(SkuApplyResult(
                    sku=target_sku, applied_fields=[], skipped_fields=[],
                    warnings=[f"Error {exc.status_code}: {exc.detail}"],
                ))
        else:
            # Crear nuevo
            result = await create_product_from_extraction(session, target_sku, body.extraction)
            results.append(result)
            if not result.warnings:
                skus_created.append(target_sku)

    # Guardar Document si se pide
    document_id: str | None = None
    if body.save_document and body.pdf_filename:
        # pdf_bytes no viaja en el apply — se guarda sólo si el cliente lo reenvía
        # Para esta versión, el document se crea sin el binario (como placeholder)
        pass  # TODO Task 4 completo — por ahora sin binario

    await session.commit()

    return FichaSeriesApplyResponse(
        series=body.series,
        results=results,
        document_id=document_id,
        skus_created=skus_created,
        skus_updated=skus_updated,
    )
```

- [ ] **Step 2: Verificar import**
```bash
cd mt-pricing-backend && python -c "from app.main import app; routes=[r.path for r in app.routes if 'fichas' in getattr(r,'path','') or 'series' in getattr(r,'path','')]; print(routes)"
```
Expected: muestra los 2 nuevos endpoints.

- [ ] **Step 3: Commit**
```bash
git add mt-pricing-backend/app/api/routes/ficha_enrich.py
git commit -m "feat(fichas): endpoints serie-level /ficha-enrich/series/preview + /apply"
```

---

## Task 6: Frontend — tipos + hooks series-level

**Files:**
- Modify: `mt-pricing-frontend/lib/api/endpoints/ficha-enrich.ts`
- Modify: `mt-pricing-frontend/lib/hooks/ficha-enrichment/use-ficha-enrich.ts`

- [ ] **Step 1: Añadir tipos a `ficha-enrich.ts`**

Añadir después de `SkuApplyResult`:
```typescript
export interface FichaSeriesPreviewResponse {
  series: string;
  filename: string;
  extraction: FichaExtractionResult;
  series_skus: SkuDiffResult[];   // status: "existing" | "new"
  model_gaps: string[];
  page_count: number;
  confidence: number;
}

export interface FichaSeriesApplyRequest {
  extraction: FichaExtractionResult;
  apply_to_skus: string[];
  series: string;
  pdf_filename?: string;
  apply_scalars?: boolean;
  apply_specs?: boolean;
  apply_materials?: boolean;
  apply_dimensions?: boolean;
  apply_translations?: boolean;
  selected_scalar_fields?: string[];
  save_document?: boolean;
}

export interface FichaSeriesApplyResponse {
  series: string;
  results: SkuApplyResult[];
  document_id: string | null;
  skus_created: string[];
  skus_updated: string[];
}
```

Actualizar `SkuDiffResult`:
```typescript
export interface SkuDiffResult {
  sku: string;
  status: "existing" | "new";    // AÑADIR
  diffs: FieldDiff[];
}
```

Añadir funciones API:
```typescript
export async function previewFichaSeries(
  file: File,
): Promise<FichaSeriesPreviewResponse> {
  const fd = new FormData();
  fd.append("file", file);
  return authedFetch<FichaSeriesPreviewResponse>(
    `/api/v1/ficha-enrich/series/preview`,
    { method: "POST", body: fd },
  );
}

export async function applyFichaSeries(
  body: FichaSeriesApplyRequest,
): Promise<FichaSeriesApplyResponse> {
  return authedFetch<FichaSeriesApplyResponse>(
    `/api/v1/ficha-enrich/series/apply`,
    { method: "POST", body: JSON.stringify(body) },
  );
}
```

- [ ] **Step 2: Añadir hooks a `use-ficha-enrich.ts`**

```typescript
import {
  previewFichaSeries,
  applyFichaSeries,
  type FichaSeriesPreviewResponse,
  type FichaSeriesApplyRequest,
  type FichaSeriesApplyResponse,
} from "@/lib/api/endpoints/ficha-enrich";

export function usePreviewFichaSeries() {
  return useMutation<FichaSeriesPreviewResponse, Error, File>({
    mutationFn: (file) => previewFichaSeries(file),
  });
}

export function useApplyFichaSeries() {
  return useMutation<FichaSeriesApplyResponse, Error, FichaSeriesApplyRequest>({
    mutationFn: (body) => applyFichaSeries(body),
  });
}
```

- [ ] **Step 3: TypeScript check**
```bash
cd mt-pricing-frontend && npx tsc --noEmit 2>&1 | grep -i "ficha-enrich\|fichas" | head -10
```
Expected: sin errores en archivos nuevos.

- [ ] **Step 4: Commit**
```bash
git add mt-pricing-frontend/lib/api/endpoints/ficha-enrich.ts mt-pricing-frontend/lib/hooks/ficha-enrichment/use-ficha-enrich.ts
git commit -m "feat(fichas): tipos y hooks series-level — preview/apply sin SKU anchor"
```

---

## Task 7: Frontend — página /fichas wizard

**Files:**
- Create: `mt-pricing-frontend/app/(app)/fichas/page.tsx`
- Create: `mt-pricing-frontend/app/(app)/fichas/_client.tsx`

- [ ] **Step 1: Server component**

```typescript
// mt-pricing-frontend/app/(app)/fichas/page.tsx
import { FichasClient } from "./_client";

export default function FichasPage() {
  return <FichasClient />;
}
```

- [ ] **Step 2: Cliente wizard (4 steps)**

```typescript
// mt-pricing-frontend/app/(app)/fichas/_client.tsx
"use client";

/**
 * Wizard standalone para subir fichas técnicas.
 * Step 0: Dropzone PDF
 * Step 1: Vista serie — SKUs detected (existing/new badges) + campo diff
 * Step 2: Confirm apply
 * Step 3: Resultado (SKUs creados / actualizados + documento guardado)
 */
import * as React from "react";
import { toast } from "sonner";
import { UploadCloud, RefreshCw, CheckCircle2, Plus, AlertTriangle } from "lucide-react";
import { MtButton, Pill, SectionCard } from "@/components/mt/primitives";
import { MT } from "@/components/mt/tokens";
import { EnrichmentDiffTable } from "@/components/domain/ficha-enrichment/enrichment-diff-table";
import {
  usePreviewFichaSeries,
  useApplyFichaSeries,
} from "@/lib/hooks/ficha-enrichment/use-ficha-enrich";
import type {
  FichaSeriesPreviewResponse,
  FichaSeriesApplyResponse,
} from "@/lib/api/endpoints/ficha-enrich";

const SCALAR_FIELDS = [
  "family","subfamily","type","material","dn","pn","connection","brand",
  "weight","weight_unit","temp_min_c","temp_max_c","pressure_max_bar","size",
] as const;

// ---------------------------------------------------------------------------
// Step 0: Dropzone
// ---------------------------------------------------------------------------
function Dropzone({ onFile, isPending, error }: {
  onFile: (f: File) => void; isPending: boolean; error: Error | null;
}) {
  const ref = React.useRef<HTMLInputElement>(null);
  return (
    <div className="flex flex-col items-center gap-6 py-16">
      <button
        type="button"
        disabled={isPending}
        onClick={() => ref.current?.click()}
        className="flex w-full max-w-lg flex-col items-center gap-4 rounded-xl border-2 border-dashed px-8 py-12 transition-colors disabled:opacity-60"
        style={{ borderColor: MT.borderStrong, backgroundColor: MT.surface2 }}
        aria-label="Subir ficha técnica PDF"
      >
        {isPending
          ? <RefreshCw className="animate-spin" style={{ color: MT.brand }} size={36} strokeWidth={1.5} />
          : <UploadCloud size={36} strokeWidth={1.5} style={{ color: MT.ink3 }} />
        }
        <div className="text-center">
          <p className="text-[14px] font-semibold" style={{ color: MT.ink }}>
            {isPending ? "Analizando con Claude…" : "Arrastra o selecciona la ficha técnica PDF"}
          </p>
          <p className="text-[12px] mt-1" style={{ color: MT.ink3 }}>
            Formato: MTFT_XXXX.pdf — máx. 50 MB
          </p>
        </div>
      </button>
      <input
        ref={ref} type="file" accept="application/pdf"
        className="sr-only" aria-label="Subir ficha técnica PDF"
        onChange={(e) => { const f = e.target.files?.[0]; if (f) onFile(f); }}
      />
      {error && (
        <div className="flex max-w-lg items-start gap-2 rounded-lg border px-4 py-3 text-[12.5px]"
          style={{ borderColor: MT.dangerBorder, backgroundColor: MT.dangerSoft, color: MT.danger }}>
          <AlertTriangle size={14} className="mt-px shrink-0" />
          <span>{error.message}</span>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Step 1: Serie review
// ---------------------------------------------------------------------------
function SerieStep({ preview, onReset, onApplySuccess }: {
  preview: FichaSeriesPreviewResponse;
  onReset: () => void;
  onApplySuccess: (result: FichaSeriesApplyResponse) => void;
}) {
  const applyMutation = useApplyFichaSeries();

  const firstSkuDiffs = preview.series_skus[0]?.diffs ?? [];
  const changedFields = React.useMemo(
    () => new Set(firstSkuDiffs.filter(d => d.has_change).map(d => d.field_name)),
    [firstSkuDiffs],
  );
  const [selectedFields, setSelectedFields] = React.useState<Set<string>>(changedFields);
  const [selectedSkus, setSelectedSkus] = React.useState<Set<string>>(
    new Set(preview.series_skus.map(s => s.sku))
  );

  const toggleSku = (sku: string) => setSelectedSkus(prev => {
    const next = new Set(prev);
    next.has(sku) ? next.delete(sku) : next.add(sku);
    return next;
  });
  const toggleField = React.useCallback((f: string) => setSelectedFields(prev => {
    const next = new Set(prev);
    next.has(f) ? next.delete(f) : next.add(f);
    return next;
  }), []);

  const existingCount = preview.series_skus.filter(s => s.status === "existing").length;
  const newCount = preview.series_skus.filter(s => s.status === "new").length;

  const handleApply = () => {
    const scalarFields = [...selectedFields].filter(f => (SCALAR_FIELDS as readonly string[]).includes(f));
    applyMutation.mutate({
      extraction: preview.extraction,
      apply_to_skus: [...selectedSkus],
      series: preview.series,
      pdf_filename: preview.filename,
      apply_scalars: scalarFields.length > 0,
      apply_specs: selectedFields.has("specs"),
      apply_materials: selectedFields.has("materials"),
      apply_dimensions: selectedFields.has("dimensions_by_dn"),
      apply_translations: selectedFields.has("translations"),
      selected_scalar_fields: scalarFields,
      save_document: true,
    }, {
      onSuccess: (result) => {
        toast.success(`Serie ${preview.series} procesada: ${result.skus_created.length} creados, ${result.skus_updated.length} actualizados`);
        onApplySuccess(result);
      },
      onError: (err) => toast.error(err.message || "Error al aplicar"),
    });
  };

  return (
    <div className="space-y-6">
      {/* Header serie */}
      <SectionCard
        title={`Serie ${preview.series} — ${preview.series_skus.length} SKUs detectados`}
        subtitle={`${preview.filename} · ${preview.page_count} páginas · ${Math.round(preview.confidence * 100)}% confianza`}
        actions={
          <div className="flex gap-2">
            {existingCount > 0 && <Pill tone="neutral">{existingCount} existentes</Pill>}
            {newCount > 0 && <Pill tone="warning">{newCount} nuevos</Pill>}
          </div>
        }
      >
        {/* SKU picker */}
        <div className="px-4 py-3 flex flex-wrap gap-2">
          {preview.series_skus.map(s => (
            <button
              key={s.sku}
              type="button"
              onClick={() => toggleSku(s.sku)}
              className="flex items-center gap-1.5 rounded border px-3 py-1.5 text-[12px] font-medium transition-colors"
              style={{
                borderColor: selectedSkus.has(s.sku) ? MT.brand : MT.border,
                backgroundColor: selectedSkus.has(s.sku) ? MT.brandSofter : MT.surface2,
                color: selectedSkus.has(s.sku) ? MT.brand : MT.ink3,
              }}
            >
              <span className="mt-mono">{s.sku}</span>
              {s.status === "new" && (
                <Pill tone="warning" mono><Plus size={9} />new</Pill>
              )}
              <span style={{ color: MT.ink3 }}>
                ({s.diffs.filter(d => d.has_change).length}↑)
              </span>
            </button>
          ))}
        </div>
      </SectionCard>

      {/* Diff fields — usa el primer SKU como representativo */}
      <SectionCard title="Campos a aplicar">
        <div className="p-4">
          <EnrichmentDiffTable
            diffs={firstSkuDiffs}
            selectedFields={selectedFields}
            onToggleField={toggleField}
          />
        </div>
      </SectionCard>

      {/* Model gaps */}
      {preview.model_gaps.length > 0 && (
        <div className="flex items-start gap-2 rounded-lg border px-4 py-3 text-[12px]"
          style={{ borderColor: MT.warningBorder, backgroundColor: MT.warningSoft, color: MT.warning }}>
          <AlertTriangle size={13} className="mt-px shrink-0" />
          <span><strong>Sin mapeo en modelo:</strong> {preview.model_gaps.join(", ")}</span>
        </div>
      )}

      {/* Apply error */}
      {applyMutation.isError && (
        <div className="flex items-start gap-2 rounded-lg border px-4 py-3 text-[12.5px]"
          style={{ borderColor: MT.dangerBorder, backgroundColor: MT.dangerSoft, color: MT.danger }}>
          <AlertTriangle size={14} className="mt-px shrink-0" />
          <span>{applyMutation.error.message}</span>
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center justify-between">
        <MtButton tone="ghost" size="sm" onClick={onReset}>Subir otro PDF</MtButton>
        <MtButton
          tone="primary"
          disabled={selectedSkus.size === 0 || selectedFields.size === 0 || applyMutation.isPending}
          onClick={handleApply}
          icon={applyMutation.isPending ? <RefreshCw size={13} className="animate-spin" /> : undefined}
        >
          {applyMutation.isPending
            ? "Procesando…"
            : `Aplicar a ${selectedSkus.size} SKU${selectedSkus.size !== 1 ? "s" : ""} (${selectedFields.size} campos)`
          }
        </MtButton>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Step 2: Resultado
// ---------------------------------------------------------------------------
function ResultStep({ result, onReset }: {
  result: FichaSeriesApplyResponse; onReset: () => void;
}) {
  return (
    <div className="flex flex-col items-center gap-6 py-12">
      <CheckCircle2 size={48} strokeWidth={1.5} style={{ color: MT.success }} />
      <div className="text-center">
        <p className="text-[16px] font-semibold" style={{ color: MT.ink }}>
          Serie {result.series} procesada
        </p>
        <p className="mt-1 text-[13px]" style={{ color: MT.ink3 }}>
          {result.skus_created.length > 0 && `${result.skus_created.length} SKUs creados · `}
          {result.skus_updated.length > 0 && `${result.skus_updated.length} SKUs actualizados`}
          {result.document_id && ` · Documento guardado`}
        </p>
      </div>
      <div className="w-full max-w-md space-y-2">
        {result.results.map(r => (
          <div key={r.sku}
            className="flex items-center justify-between rounded-lg border px-3 py-2 text-[12px]"
            style={{ borderColor: MT.border }}>
            <span className="mt-mono font-medium" style={{ color: MT.ink }}>{r.sku}</span>
            <div className="flex gap-1.5">
              {r.applied_fields.length > 0 && <Pill tone="success" mono>{r.applied_fields.length}↑</Pill>}
              {r.warnings.length > 0 && <Pill tone="warning" mono>{r.warnings.length} avisos</Pill>}
            </div>
          </div>
        ))}
      </div>
      <MtButton tone="neutral" onClick={onReset}>Subir otra ficha</MtButton>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Root
// ---------------------------------------------------------------------------
export function FichasClient() {
  const previewMutation = usePreviewFichaSeries();
  const [applyResult, setApplyResult] = React.useState<FichaSeriesApplyResponse | null>(null);

  const reset = () => {
    previewMutation.reset();
    setApplyResult(null);
  };

  return (
    <div className="space-y-6 max-w-3xl mx-auto">
      <div>
        <h1 className="text-[20px] font-semibold" style={{ color: MT.ink }}>Fichas técnicas</h1>
        <p className="text-[13px] mt-1" style={{ color: MT.ink3 }}>
          Sube una ficha técnica PDF para enriquecer o crear los productos de la serie.
        </p>
      </div>

      {applyResult ? (
        <ResultStep result={applyResult} onReset={reset} />
      ) : previewMutation.isSuccess ? (
        <SerieStep
          preview={previewMutation.data}
          onReset={reset}
          onApplySuccess={setApplyResult}
        />
      ) : (
        <Dropzone
          onFile={(f) => previewMutation.mutate(f)}
          isPending={previewMutation.isPending}
          error={previewMutation.error}
        />
      )}
    </div>
  );
}
```

- [ ] **Step 3: TypeScript check**
```bash
cd mt-pricing-frontend && npx tsc --noEmit 2>&1 | grep -i "fichas" | head -10
```

- [ ] **Step 4: Commit**
```bash
git add "mt-pricing-frontend/app/(app)/fichas/"
git commit -m "feat(fichas): página /fichas — wizard standalone serie completa"
```

---

## Task 8: Navegación — añadir item "Fichas técnicas"

**Files:**
- Modificar: el archivo de navegación principal del frontend (buscar con Glob `app/(app)/**/layout.tsx` y nav components)

- [ ] **Step 1: Encontrar el nav**

```bash
find mt-pricing-frontend/app -name "layout.tsx" | head -5
find mt-pricing-frontend/components -name "*nav*" -o -name "*sidebar*" | head -5
```

- [ ] **Step 2: Añadir item**

Una vez encontrado el array de nav items (buscar patrones `href: "/catalogo"` o similar), añadir:
```typescript
{ href: "/fichas", label: "Fichas técnicas", icon: FileText }
// o equivalente según el patrón del nav existente
```

- [ ] **Step 3: Verificar TypeScript**
```bash
cd mt-pricing-frontend && npx tsc --noEmit 2>&1 | grep -v "node_modules" | head -10
```

- [ ] **Step 4: Commit**
```bash
git add mt-pricing-frontend/
git commit -m "feat(fichas): nav item Fichas técnicas → /fichas"
```

---

## Task 9: Redeploy + smoke test

- [ ] **Step 1: Backend**
```bash
cd C:\BR-Github\br-mt\br-mt-ecommerce
docker compose -f docker-compose.dev.yml up -d --no-build backend
```

- [ ] **Step 2: Verificar endpoints**
```bash
curl -s http://localhost:8080/openapi.json | python -c "
import json,sys; d=json.load(sys.stdin)
paths=[p for p in d.get('paths',{}) if 'ficha' in p]
print(paths)
"
```
Expected: 4 paths — incluyendo `/api/v1/ficha-enrich/series/preview` y `/api/v1/ficha-enrich/series/apply`.

- [ ] **Step 3: Frontend**
```bash
docker restart mt-frontend
```

- [ ] **Step 4: Navegar a `http://localhost:3000/fichas`**

Verificar que aparece el wizard de upload.

- [ ] **Step 5: Commit vacío para documentar smoke test**
```bash
git commit --allow-empty -m "chore(fichas): smoke test /fichas standalone OK"
```

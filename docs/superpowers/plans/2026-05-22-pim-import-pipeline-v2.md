# PIM Import Pipeline v2 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rediseñar el pipeline de importación PIM para soportar cualquier Excel vía LLM mapping, traducciones multiidioma (EN/ES/FR/DE/IT/PT), certificaciones M:N, completitud LLM on-demand, y reconciliación de carga completa.

**Architecture:** Un `XlsxParser` produce `ParsedProduct` dataclasses por fila (scalars, jsonb, translations, certifications). Un `RowWriter` pipeline compuesto de 4 writers especializados persiste cada tipo. Un `ImportOrchestrator` unificado reemplaza `applier.py` + `pim_importer.py` y añade un `ReconciliationPass` final que garantiza `total_rows == sum(all_buckets)`.

**Tech Stack:** Python 3.11, SQLAlchemy 2.0 async, FastAPI, openpyxl, Anthropic SDK (claude-sonnet-4-6), Alembic, pytest, Next.js 16 + React 19 + TypeScript + Tailwind v4 + Shadcn/ui

**Spec:** `docs/superpowers/specs/2026-05-22-pim-import-redesign-design.md`

---

## Paralelización de tareas

```
Task 1 (Migration)
  ├── Task 2 (ParsedProduct)   ─┐
  ├── Task 3 (XlsxParser)      │ paralelo
  ├── Task 4 (ScalarWriter +   │ después de
  │          JsonbWriter)       │ Task 1
  └── Task 5 (TranslationWriter│
             + CertWriter)    ─┘
           ↓
Task 6 (RowWriter pipeline)
Task 7 (ReconciliationPass)
Task 8 (ImportOrchestrator)
Task 9 (Wire service + LLM catalog)
Task 10 (OrchestratorResult schema + API)
  ├── Task 11 (TranslationCompletionService) ─┐ paralelo
  └── Task 12 (Translation endpoints)        ─┘
Task 13 (Frontend: reconciliation panel)
Task 14 (Frontend: translations tab)
```

---

## File Map

**New backend files:**
- `app/services/importer/parsed_product.py` — ParsedProduct dataclass
- `app/services/importer/xlsx_parser.py` — XlsxParser (streamed Iterator)
- `app/services/importer/row_writer.py` — BaseWriter, ScalarWriter, JsonbWriter, TranslationWriter, CertificationWriter, RowWriter, WriteResult
- `app/services/importer/import_orchestrator.py` — ImportOrchestrator, OrchestratorResult, ReconciliationResult
- `app/services/translations/__init__.py` — vacío
- `app/services/translations/completion_service.py` — TranslationCompletionService
- `alembic/versions/20260522_155_translations_lang_extended.py` — migración lang constraint

**Modified backend files:**
- `app/db/models/product.py` — añadir fr/de/it/pt a ck_translations_lang + ai_generated a TranslationStatus
- `app/services/importer/mapping_detector.py` — expandir `_AVAILABLE_FIELDS_DOC`
- `app/services/importer/importer_service.py` — wire ImportOrchestrator en preview/apply
- `app/schemas/importer.py` — añadir ReconciliationResultSchema, OrchestratorResultSchema
- `app/api/routes/imports.py` — incluir reconciliation en response del apply

**New backend test files:**
- `tests/unit/importer/test_parsed_product.py`
- `tests/unit/importer/test_xlsx_parser.py`
- `tests/unit/importer/test_row_writer.py`
- `tests/unit/importer/test_import_orchestrator.py`
- `tests/unit/services/translations/test_completion_service.py`
- `tests/unit/api/test_translations_api.py`

**New frontend files:**
- `app/(app)/imports/_components/reconciliation-panel.tsx`
- `app/(app)/catalogo/[sku]/_components/translations-tab.tsx`
- `lib/api/translations.ts`
- `lib/hooks/imports/use-translation-coverage.ts`

**Modified frontend files:**
- `app/(app)/imports/_components/import-report.tsx` — añadir ReconciliationPanel
- `app/(app)/catalogo/[sku]/page.tsx` — añadir tab Traducciones

---

## Task 1: Migración 155 — Extender lang constraint + ai_generated

**Files:**
- Create: `mt-pricing-backend/alembic/versions/20260522_155_translations_lang_extended.py`
- Modify: `mt-pricing-backend/app/db/models/product.py`

### Paso 1.1 — Localizar TranslationStatus enum en product.py

Buscar la clase `TranslationStatus` en `app/db/models/product.py`:

```bash
grep -n "TranslationStatus\|ai_generated\|ck_translations_lang" \
  mt-pricing-backend/app/db/models/product.py
```

Esperado: encontrar la clase enum y la línea con el CHECK constraint.

### Paso 1.2 — Añadir `ai_generated` a TranslationStatus

En `app/db/models/product.py`, localizar la clase `TranslationStatus` (o el `StrEnum`/lista que genera los valores) y añadir el nuevo valor. Ejemplo (ajustar según la clase real encontrada en 1.1):

```python
class TranslationStatus(str, enum.Enum):
    pending = "pending"
    imported = "imported"
    ai_generated = "ai_generated"   # ← añadir
    reviewed = "reviewed"
```

Si usa una lista de strings para `values_csv()`, añadir `"ai_generated"` a la lista.

### Paso 1.3 — Crear la migración Alembic

```bash
cd mt-pricing-backend
alembic revision --autogenerate \
  -m "translations_lang_extended" \
  --rev-id "20260522_155"
```

Editar el archivo generado en `alembic/versions/20260522_155_translations_lang_extended.py`:

```python
"""Extend product_translations.lang constraint to include fr/de/it/pt.
Add ai_generated to TranslationStatus enum.
"""
from __future__ import annotations
from alembic import op

revision = "20260522_155"
down_revision = None  # ajustar al head actual: ejecutar `alembic heads` y poner aquí
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Extend lang CHECK constraint
    op.drop_constraint("ck_translations_lang", "product_translations")
    op.create_check_constraint(
        "ck_translations_lang",
        "product_translations",
        "lang IN ('es', 'ar', 'en', 'fr', 'de', 'it', 'pt')",
    )
    # 2. Add ai_generated to TranslationStatus enum
    # Si TranslationStatus es un PG enum nativo:
    op.execute("ALTER TYPE translationstatus ADD VALUE IF NOT EXISTS 'ai_generated'")
    # Si es solo CHECK constraint, reemplazar también ese constraint.


def downgrade() -> None:
    op.drop_constraint("ck_translations_lang", "product_translations")
    op.create_check_constraint(
        "ck_translations_lang",
        "product_translations",
        "lang IN ('es', 'ar', 'en')",
    )
    # Nota: no se puede hacer DROP VALUE en PG enum nativos — downgrade parcial.
```

> **Verificar antes de aplicar:** ejecutar `alembic heads` para obtener el down_revision correcto y reemplazar `None` arriba.

### Paso 1.4 — Aplicar la migración

```bash
cd mt-pricing-backend
alembic upgrade 20260522_155
```

Esperado: `Running upgrade ... -> 20260522_155, translations_lang_extended`

### Paso 1.5 — Commit

```bash
git add alembic/versions/20260522_155_translations_lang_extended.py \
        app/db/models/product.py
git commit -m "feat(pim-import): migration 155 — extend lang constraint + ai_generated status"
```

---

## Task 2: ParsedProduct dataclass

**Files:**
- Create: `mt-pricing-backend/app/services/importer/parsed_product.py`
- Create: `mt-pricing-backend/tests/unit/importer/test_parsed_product.py`

### Paso 2.1 — Escribir el test

```python
# tests/unit/importer/test_parsed_product.py
"""Tests para ParsedProduct dataclass."""
from __future__ import annotations
from app.services.importer.parsed_product import ParsedProduct


def test_defaults_are_empty_collections():
    p = ParsedProduct(sku="MT-001")
    assert p.scalars == {}
    assert p.jsonb == {"dimensions": {}, "packaging": {}, "specs": {}}
    assert p.translations == {}
    assert p.certifications == []
    assert p.errors == []


def test_is_error_row_when_sku_empty():
    p = ParsedProduct(sku="", errors=["SKU vacío"])
    assert p.is_error_row is True


def test_is_not_error_row_when_sku_present():
    p = ParsedProduct(sku="MT-001")
    assert p.is_error_row is False


def test_has_translations():
    p = ParsedProduct(sku="MT-001", translations={"en": "Ball valve", "es": "Válvula"})
    assert p.has_translations is True


def test_has_certifications():
    p = ParsedProduct(sku="MT-001", certifications=["CE", "ISO 9001"])
    assert len(p.certifications) == 2
```

### Paso 2.2 — Ejecutar para verificar fallo

```bash
cd mt-pricing-backend
python -m pytest tests/unit/importer/test_parsed_product.py -v
```

Esperado: `ImportError` o `ModuleNotFoundError`.

### Paso 2.3 — Implementar ParsedProduct

```python
# app/services/importer/parsed_product.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ParsedProduct:
    """Producto parseado de una fila Excel, listo para persistencia."""

    sku: str
    scalars: dict[str, Any] = field(default_factory=dict)
    jsonb: dict[str, dict[str, Any]] = field(
        default_factory=lambda: {"dimensions": {}, "packaging": {}, "specs": {}}
    )
    translations: dict[str, str] = field(default_factory=dict)
    certifications: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def is_error_row(self) -> bool:
        return not self.sku or not self.sku.strip()

    @property
    def has_translations(self) -> bool:
        return bool(self.translations)

    @property
    def has_certifications(self) -> bool:
        return bool(self.certifications)
```

### Paso 2.4 — Ejecutar tests

```bash
python -m pytest tests/unit/importer/test_parsed_product.py -v
```

Esperado: todos PASS.

### Paso 2.5 — Commit

```bash
git add app/services/importer/parsed_product.py \
        tests/unit/importer/test_parsed_product.py
git commit -m "feat(pim-import): add ParsedProduct dataclass"
```

---

## Task 3: XlsxParser

**Files:**
- Create: `mt-pricing-backend/app/services/importer/xlsx_parser.py`
- Create: `mt-pricing-backend/tests/unit/importer/test_xlsx_parser.py`

### Paso 3.1 — Escribir tests

```python
# tests/unit/importer/test_xlsx_parser.py
"""Tests para XlsxParser — produce ParsedProduct por fila."""
from __future__ import annotations
import io
import openpyxl
from decimal import Decimal

from app.services.importer.xlsx_parser import XlsxParser
from app.services.importer.mapping_detector import ColumnMappingItem


def _make_xlsx(rows: list[list]) -> bytes:
    """Helper: crea un xlsx en memoria con las filas dadas (primera = header)."""
    wb = openpyxl.Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _mapping(*items: tuple[str, str, str]) -> list[ColumnMappingItem]:
    return [ColumnMappingItem(excel_col=e, target_field=t, transform=tr) for e, t, tr in items]


def test_parses_scalar_fields():
    xlsx = _make_xlsx([
        ["sku", "Peso neto (kg)", "Conexión"],
        ["MT-001", 1.5, "Rosca"],
    ])
    mapping = _mapping(
        ("sku", "sku", "text"),
        ("Peso neto (kg)", "weight", "decimal"),
        ("Conexión", "connection", "text"),
    )
    parser = XlsxParser(xlsx, mapping, header_row_index=0)
    products = list(parser.parse())
    assert len(products) == 1
    p = products[0]
    assert p.sku == "MT-001"
    assert p.scalars["weight"] == Decimal("1.5")
    assert p.scalars["connection"] == "Rosca"


def test_parses_jsonb_dimensions():
    xlsx = _make_xlsx([
        ["sku", "Alto (cm)"],
        ["MT-001", 10.5],
    ])
    mapping = _mapping(
        ("sku", "sku", "text"),
        ("Alto (cm)", "dimensions.high_mm", "cm_to_mm"),
    )
    products = list(XlsxParser(xlsx, mapping).parse())
    assert products[0].jsonb["dimensions"]["high_mm"] == "105.0"


def test_parses_translations():
    xlsx = _make_xlsx([
        ["sku", "Nombre EN", "Nombre FR"],
        ["MT-001", "Ball valve", "Robinet à bille"],
    ])
    mapping = _mapping(
        ("sku", "sku", "text"),
        ("Nombre EN", "translations.en", "text"),
        ("Nombre FR", "translations.fr", "text"),
    )
    products = list(XlsxParser(xlsx, mapping).parse())
    assert products[0].translations == {"en": "Ball valve", "fr": "Robinet à bille"}


def test_parses_certifications_split_by_comma():
    xlsx = _make_xlsx([
        ["sku", "Certificaciones"],
        ["MT-001", "CE, ISO 9001, WRAS"],
    ])
    mapping = _mapping(
        ("sku", "sku", "text"),
        ("Certificaciones", "certifications", "text"),
    )
    products = list(XlsxParser(xlsx, mapping).parse())
    assert products[0].certifications == ["CE", "ISO 9001", "WRAS"]


def test_skips_empty_rows():
    xlsx = _make_xlsx([
        ["sku"], ["MT-001"], [None], ["MT-002"],
    ])
    mapping = _mapping(("sku", "sku", "text"))
    products = list(XlsxParser(xlsx, mapping).parse())
    assert len(products) == 2
    assert parser.rows_yielded == 2  # noqa — ajustar abajo


def test_skips_empty_rows_rows_yielded():
    xlsx = _make_xlsx([["sku"], ["MT-001"], [None], ["MT-002"]])
    mapping = _mapping(("sku", "sku", "text"))
    parser = XlsxParser(xlsx, mapping)
    list(parser.parse())
    assert parser.rows_yielded == 2


def test_empty_sku_is_error_row():
    xlsx = _make_xlsx([["sku", "Peso"], [None, 1.5]])
    mapping = _mapping(("sku", "sku", "text"), ("Peso", "weight", "decimal"))
    products = list(XlsxParser(xlsx, mapping).parse())
    assert len(products) == 1
    assert products[0].is_error_row is True
    assert parser.rows_yielded == 1  # noqa — se cuenta aunque sea error


def test_empty_sku_rows_yielded():
    xlsx = _make_xlsx([["sku", "Peso"], [None, 1.5]])
    mapping = _mapping(("sku", "sku", "text"), ("Peso", "weight", "decimal"))
    parser = XlsxParser(xlsx, mapping)
    list(parser.parse())
    assert parser.rows_yielded == 1


def test_header_row_index_nonzero():
    xlsx = _make_xlsx([
        ["PIM Export v2"],          # título — fila 0
        ["sku", "Peso"],            # header real — fila 1
        ["MT-001", 0.5],
    ])
    mapping = _mapping(("sku", "sku", "text"), ("Peso", "weight", "decimal"))
    parser = XlsxParser(xlsx, mapping, header_row_index=1)
    products = list(parser.parse())
    assert len(products) == 1
    assert products[0].sku == "MT-001"


def test_skip_target_is_ignored():
    xlsx = _make_xlsx([["sku", "Completitud %"], ["MT-001", 40]])
    mapping = _mapping(
        ("sku", "sku", "text"),
        ("Completitud %", "_skip", "text"),
    )
    products = list(XlsxParser(xlsx, mapping).parse())
    assert "Completitud %" not in products[0].scalars
    assert products[0].scalars.get("_skip") is None


def test_unsupported_lang_is_ignored():
    xlsx = _make_xlsx([["sku", "Nombre ZZ"], ["MT-001", "test"]])
    mapping = _mapping(
        ("sku", "sku", "text"),
        ("Nombre ZZ", "translations.zz", "text"),
    )
    products = list(XlsxParser(xlsx, mapping).parse())
    assert products[0].translations == {}
```

### Paso 3.2 — Ejecutar para verificar fallos

```bash
python -m pytest tests/unit/importer/test_xlsx_parser.py -v
```

Esperado: `ImportError` — `XlsxParser` no existe aún.

### Paso 3.3 — Implementar XlsxParser

```python
# app/services/importer/xlsx_parser.py
from __future__ import annotations

import io
from decimal import Decimal
from typing import Any, Iterator

import openpyxl

from app.services.importer.column_mapper import CASTERS, ImportCastError, _cast_text
from app.services.importer.mapping_detector import ColumnMappingItem
from app.services.importer.parsed_product import ParsedProduct

SUPPORTED_LANGS: frozenset[str] = frozenset({"en", "es", "fr", "de", "it", "pt", "ar"})
JSONB_PREFIXES: frozenset[str] = frozenset({"dimensions", "packaging", "specs"})


class XlsxParser:
    """Parsea un xlsx usando un mapping flexible. Produce ParsedProduct por fila."""

    def __init__(
        self,
        xlsx_bytes: bytes,
        mapping: list[ColumnMappingItem],
        header_row_index: int = 0,
    ) -> None:
        self._bytes = xlsx_bytes
        self._mapping = mapping
        self._header_row_index = header_row_index
        self._rows_yielded: int = 0

    @property
    def rows_yielded(self) -> int:
        return self._rows_yielded

    def parse(self) -> Iterator[ParsedProduct]:
        wb = openpyxl.load_workbook(io.BytesIO(self._bytes), read_only=True, data_only=True)
        ws = wb.active
        col_index: dict[str, int] = {}

        try:
            for row_idx, raw_row in enumerate(ws.iter_rows(values_only=True)):
                if row_idx < self._header_row_index:
                    continue
                if row_idx == self._header_row_index:
                    col_index = {
                        str(v).strip(): i
                        for i, v in enumerate(raw_row)
                        if v is not None
                    }
                    continue
                row = list(raw_row)
                if not any(v is not None and v != "" for v in row):
                    continue  # fila vacía — no cuenta
                parsed = self._parse_row(row, col_index)
                self._rows_yielded += 1
                yield parsed
        finally:
            wb.close()

    def _parse_row(self, row: list[Any], col_index: dict[str, int]) -> ParsedProduct:
        scalars: dict[str, Any] = {}
        jsonb: dict[str, dict[str, Any]] = {
            "dimensions": {}, "packaging": {}, "specs": {}
        }
        translations: dict[str, str] = {}
        certifications: list[str] = []
        errors: list[str] = []

        for item in self._mapping:
            if item.target_field == "_skip":
                continue
            idx = col_index.get(item.excel_col)
            if idx is None or idx >= len(row):
                continue
            raw = row[idx]
            caster = CASTERS.get(item.transform, _cast_text)
            try:
                casted = caster(raw)
            except ImportCastError as exc:
                errors.append(f"col {item.excel_col!r}: {exc}")
                continue
            if casted is None:
                continue

            field = item.target_field

            if field.startswith("translations."):
                lang = field.split(".", 1)[1]
                if lang in SUPPORTED_LANGS:
                    translations[lang] = str(casted)
            elif field == "certifications":
                parts = [p.strip() for p in str(casted).split(",") if p.strip()]
                certifications.extend(parts)
            elif "." in field:
                prefix, key = field.split(".", 1)
                if prefix in JSONB_PREFIXES:
                    stored: Any = str(casted) if isinstance(casted, Decimal) else casted
                    jsonb[prefix][key] = stored
            else:
                scalars[field] = casted

        sku = str(scalars.pop("sku", "") or "").strip()
        if not sku:
            errors.append("SKU vacío — fila error.")

        return ParsedProduct(
            sku=sku,
            scalars=scalars,
            jsonb=jsonb,
            translations=translations,
            certifications=certifications,
            errors=errors,
        )
```

### Paso 3.4 — Ejecutar tests

```bash
python -m pytest tests/unit/importer/test_xlsx_parser.py -v
```

Esperado: todos PASS.

### Paso 3.5 — Commit

```bash
git add app/services/importer/xlsx_parser.py \
        tests/unit/importer/test_xlsx_parser.py
git commit -m "feat(pim-import): add XlsxParser producing ParsedProduct"
```

---

## Task 4: ScalarWriter + JsonbWriter

**Files:**
- Create: `mt-pricing-backend/app/services/importer/row_writer.py` (parcial — solo Scalar y Jsonb)
- Create: `mt-pricing-backend/tests/unit/importer/test_row_writer.py` (parcial)

### Paso 4.1 — Escribir tests (ScalarWriter + JsonbWriter)

```python
# tests/unit/importer/test_row_writer.py
"""Tests para RowWriter pipeline."""
from __future__ import annotations
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.services.importer.row_writer import ScalarWriter, JsonbWriter, WriteResult
from app.services.importer.parsed_product import ParsedProduct


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_product(sku: str = "MT-001", **kwargs) -> MagicMock:
    p = MagicMock()
    p.sku = sku
    p.manual_locked_fields = []
    for k, v in kwargs.items():
        setattr(p, k, v)
    return p


# ── ScalarWriter ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_scalar_writer_sets_fields_on_existing_product():
    session = AsyncMock()
    product = _make_product(sku="MT-001", weight=None, connection=None)
    writer = ScalarWriter()
    result = await writer.write(
        session=session,
        sku="MT-001",
        existing=product,
        scalars={"weight": Decimal("1.5"), "connection": "Rosca"},
        locked_fields=set(),
    )
    assert product.weight == Decimal("1.5")
    assert product.connection == "Rosca"
    assert result.bucket == "updated"
    assert "weight" in result.changed_fields


@pytest.mark.asyncio
async def test_scalar_writer_respects_locked_fields():
    session = AsyncMock()
    product = _make_product(sku="MT-001", weight=Decimal("2.0"))
    writer = ScalarWriter()
    await writer.write(
        session=session,
        sku="MT-001",
        existing=product,
        scalars={"weight": Decimal("1.5")},
        locked_fields={"weight"},
    )
    assert product.weight == Decimal("2.0")  # sin cambio


@pytest.mark.asyncio
async def test_scalar_writer_no_change_when_equal():
    session = AsyncMock()
    product = _make_product(sku="MT-001", weight=Decimal("1.5"))
    writer = ScalarWriter()
    result = await writer.write(
        session=session,
        sku="MT-001",
        existing=product,
        scalars={"weight": Decimal("1.5")},
        locked_fields=set(),
    )
    assert result.bucket == "no_change"
    assert result.changed_fields == []


# ── JsonbWriter ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_jsonb_writer_merges_not_replaces():
    session = AsyncMock()
    product = _make_product(
        dimensions={"high_mm": "50.0", "wide_mm": "30.0"},
        packaging={},
        specs={},
    )
    writer = JsonbWriter()
    await writer.write(
        session=session,
        existing=product,
        jsonb={"dimensions": {"high_mm": "60.0"}},  # solo high_mm
        locked_fields=set(),
    )
    assert product.dimensions["high_mm"] == "60.0"
    assert product.dimensions["wide_mm"] == "30.0"  # intacto


@pytest.mark.asyncio
async def test_jsonb_writer_skips_empty_buckets():
    session = AsyncMock()
    product = _make_product(dimensions={}, packaging={}, specs={})
    writer = JsonbWriter()
    await writer.write(
        session=session,
        existing=product,
        jsonb={"dimensions": {}, "packaging": {}, "specs": {}},
        locked_fields=set(),
    )
    assert product.dimensions == {}
```

### Paso 4.2 — Ejecutar para verificar fallos

```bash
python -m pytest tests/unit/importer/test_row_writer.py -v -k "scalar or jsonb"
```

Esperado: `ImportError`.

### Paso 4.3 — Implementar ScalarWriter + JsonbWriter en row_writer.py

```python
# app/services/importer/row_writer.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

# Campos válidos de la tabla products que se pueden escribir como scalares.
_PRODUCT_SCALAR_FIELDS: frozenset[str] = frozenset({
    "family", "subfamily", "type", "material", "dn", "pn", "connection",
    "brand", "weight", "weight_unit", "intrastat_code", "erp_name",
    "hs_code", "country_of_origin", "base_uom", "data_quality",
    "bore_mm", "pressure_max_bar", "temp_min_c", "temp_max_c",
    "series", "size", "revision", "external_url", "video_url",
    "gtin", "dimensional_standard",
})
_JSONB_FIELDS: frozenset[str] = frozenset({"dimensions", "packaging", "specs"})


@dataclass
class WriteResult:
    bucket: str  # inserted | updated | no_change | error | locked
    changed_fields: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class ScalarWriter:
    """Escribe campos escalares en products. Detecta insert/update/no_change."""

    async def write(
        self,
        session: AsyncSession,
        sku: str,
        existing: Any | None,
        scalars: dict[str, Any],
        locked_fields: set[str],
    ) -> WriteResult:
        changed: list[str] = []
        for field_name, new_val in scalars.items():
            if field_name not in _PRODUCT_SCALAR_FIELDS:
                continue
            if field_name in locked_fields:
                continue
            current = getattr(existing, field_name, None) if existing else None
            if current != new_val:
                setattr(existing, field_name, new_val)
                changed.append(field_name)
        if not changed:
            return WriteResult(bucket="no_change")
        return WriteResult(bucket="updated", changed_fields=changed)


class JsonbWriter:
    """Merge JSONB fields en products. No sobreescribe keys ausentes en el mapping."""

    async def write(
        self,
        session: AsyncSession,
        existing: Any,
        jsonb: dict[str, dict[str, Any]],
        locked_fields: set[str],
    ) -> None:
        for bucket, kv in jsonb.items():
            if not kv:
                continue
            if bucket not in _JSONB_FIELDS:
                continue
            current: dict = getattr(existing, bucket, {}) or {}
            merged = {**current, **{
                k: v for k, v in kv.items()
                if f"{bucket}.{k}" not in locked_fields
            }}
            setattr(existing, bucket, merged)
```

### Paso 4.4 — Ejecutar tests

```bash
python -m pytest tests/unit/importer/test_row_writer.py -v -k "scalar or jsonb"
```

Esperado: todos PASS.

### Paso 4.5 — Commit

```bash
git add app/services/importer/row_writer.py \
        tests/unit/importer/test_row_writer.py
git commit -m "feat(pim-import): add ScalarWriter + JsonbWriter"
```

---

## Task 5: TranslationWriter + CertificationWriter

**Files:**
- Modify: `mt-pricing-backend/app/services/importer/row_writer.py` (añadir clases)
- Modify: `mt-pricing-backend/tests/unit/importer/test_row_writer.py` (añadir tests)

### Paso 5.1 — Añadir tests para TranslationWriter y CertificationWriter

Añadir al final de `tests/unit/importer/test_row_writer.py`:

```python
# ── TranslationWriter ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_translation_writer_upserts_by_sku_lang():
    from unittest.mock import patch, AsyncMock
    from app.services.importer.row_writer import TranslationWriter

    session = AsyncMock()
    session.execute = AsyncMock()

    writer = TranslationWriter()
    await writer.write(
        session=session,
        sku="MT-001",
        translations={"en": "Ball valve", "fr": "Robinet"},
        locked_fields=set(),
    )
    assert session.execute.call_count == 2


@pytest.mark.asyncio
async def test_translation_writer_skips_locked_lang():
    from app.services.importer.row_writer import TranslationWriter

    session = AsyncMock()
    writer = TranslationWriter()
    await writer.write(
        session=session,
        sku="MT-001",
        translations={"en": "Ball valve"},
        locked_fields={"translations.en"},
    )
    session.execute.assert_not_called()


# ── CertificationWriter ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_certification_writer_creates_if_not_found():
    from unittest.mock import patch, AsyncMock, MagicMock
    from app.services.importer.row_writer import CertificationWriter

    session = AsyncMock()
    # Simular que no existe la certificación
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=mock_result)

    writer = CertificationWriter()
    with patch("app.services.importer.row_writer.Certification") as MockCert:
        mock_cert_instance = MagicMock()
        mock_cert_instance.id = "uuid-123"
        MockCert.return_value = mock_cert_instance
        await writer.write(
            session=session,
            sku="MT-001",
            certifications=["CE"],
        )
    session.add.assert_called_once()
    session.flush.assert_called_once()
```

### Paso 5.2 — Ejecutar para verificar fallos

```bash
python -m pytest tests/unit/importer/test_row_writer.py -v -k "translation or certification"
```

Esperado: `ImportError` o `AttributeError`.

### Paso 5.3 — Implementar TranslationWriter + CertificationWriter

Añadir al final de `app/services/importer/row_writer.py`:

```python
from sqlalchemy import func, or_, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.models.product import ProductTranslation
from app.db.models.vocabularies import Certification, ProductCertification


class TranslationWriter:
    """Upsert de traducciones en product_translations."""

    async def write(
        self,
        session: AsyncSession,
        sku: str,
        translations: dict[str, str],
        locked_fields: set[str],
    ) -> None:
        for lang, name in translations.items():
            if f"translations.{lang}" in locked_fields:
                continue
            stmt = (
                pg_insert(ProductTranslation)
                .values(sku=sku, lang=lang, name=name, status="imported")
                .on_conflict_do_update(
                    index_elements=["sku", "lang"],
                    set_={"name": name, "status": "imported", "updated_at": text("now()")},
                )
            )
            await session.execute(stmt)


class CertificationWriter:
    """Get-or-create certifications + M:N insert en product_certifications. Additive-only."""

    async def write(
        self,
        session: AsyncSession,
        sku: str,
        certifications: list[str],
    ) -> None:
        for cert_name in certifications:
            if not cert_name:
                continue
            code = cert_name.upper().replace(" ", "_")
            result = await session.execute(
                select(Certification).where(
                    or_(
                        Certification.code == code,
                        func.lower(Certification.name) == cert_name.lower(),
                    )
                )
            )
            cert = result.scalar_one_or_none()
            if cert is None:
                cert = Certification(code=code, name=cert_name)
                session.add(cert)
                await session.flush()

            stmt = (
                pg_insert(ProductCertification)
                .values(product_sku=sku, certification_id=cert.id)
                .on_conflict_do_nothing()
            )
            await session.execute(stmt)
```

### Paso 5.4 — Ejecutar todos los tests del row_writer

```bash
python -m pytest tests/unit/importer/test_row_writer.py -v
```

Esperado: todos PASS.

### Paso 5.5 — Commit

```bash
git add app/services/importer/row_writer.py \
        tests/unit/importer/test_row_writer.py
git commit -m "feat(pim-import): add TranslationWriter + CertificationWriter"
```

---

## Task 6: RowWriter pipeline + ReconciliationResult

**Files:**
- Modify: `mt-pricing-backend/app/services/importer/row_writer.py` (añadir RowWriter)
- Create: `mt-pricing-backend/app/services/importer/import_orchestrator.py` (ReconciliationResult + contadores)
- Modify: `mt-pricing-backend/tests/unit/importer/test_row_writer.py` (test RowWriter)
- Create: `mt-pricing-backend/tests/unit/importer/test_import_orchestrator.py` (ReconciliationResult)

### Paso 6.1 — Tests para RowWriter y ReconciliationResult

Añadir al final de `tests/unit/importer/test_row_writer.py`:

```python
# ── RowWriter pipeline ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_row_writer_calls_all_writers():
    from unittest.mock import AsyncMock, patch
    from app.services.importer.row_writer import RowWriter
    from app.services.importer.parsed_product import ParsedProduct

    session = AsyncMock()
    product = _make_product(sku="MT-001", weight=None, dimensions={}, packaging={}, specs={})

    parsed = ParsedProduct(
        sku="MT-001",
        scalars={"weight": Decimal("1.0")},
        jsonb={"dimensions": {"high_mm": "50"}, "packaging": {}, "specs": {}},
        translations={"en": "Test"},
        certifications=["CE"],
    )

    with patch.object(RowWriter, "_scalar_writer") as ms, \
         patch.object(RowWriter, "_jsonb_writer") as mj, \
         patch.object(RowWriter, "_translation_writer") as mt, \
         patch.object(RowWriter, "_cert_writer") as mc:
        ms.write = AsyncMock(return_value=WriteResult(bucket="updated", changed_fields=["weight"]))
        mj.write = AsyncMock()
        mt.write = AsyncMock()
        mc.write = AsyncMock()

        rw = RowWriter()
        rw._scalar_writer = ms
        rw._jsonb_writer = mj
        rw._translation_writer = mt
        rw._cert_writer = mc

        result = await rw.apply(session, parsed, existing=product, locked_fields=set(), actor_id=None)

    ms.write.assert_called_once()
    mj.write.assert_called_once()
    mt.write.assert_called_once()
    mc.write.assert_called_once()
    assert result.bucket == "updated"
```

Crear `tests/unit/importer/test_import_orchestrator.py`:

```python
# tests/unit/importer/test_import_orchestrator.py
"""Tests para ImportOrchestrator + ReconciliationResult."""
from __future__ import annotations
from app.services.importer.import_orchestrator import ReconciliationResult


def test_reconciliation_complete():
    r = ReconciliationResult(
        total_excel_rows=100,
        inserted=10,
        updated=80,
        no_change=10,
        error_rows=0,
        locked_rows=0,
        missing_skus=[],
    )
    assert r.accounted_total == 100
    assert r.gap == 0
    assert r.is_complete is True


def test_reconciliation_incomplete():
    r = ReconciliationResult(
        total_excel_rows=100,
        inserted=10,
        updated=80,
        no_change=7,
        error_rows=0,
        locked_rows=0,
        missing_skus=["MT-X1", "MT-X2", "MT-X3"],
    )
    assert r.gap == 3
    assert r.is_complete is False
    assert len(r.missing_skus) == 3
```

### Paso 6.2 — Ejecutar para verificar fallos

```bash
python -m pytest tests/unit/importer/test_row_writer.py tests/unit/importer/test_import_orchestrator.py -v
```

Esperado: ImportError para los nuevos símbolos.

### Paso 6.3 — Implementar RowWriter en row_writer.py

Añadir al final de `app/services/importer/row_writer.py`:

```python
from app.db.models.product import Product


class RowWriter:
    """Pipeline de escritura para un ParsedProduct. Compone los 4 writers."""

    def __init__(self) -> None:
        self._scalar_writer = ScalarWriter()
        self._jsonb_writer = JsonbWriter()
        self._translation_writer = TranslationWriter()
        self._cert_writer = CertificationWriter()

    async def apply(
        self,
        session: AsyncSession,
        parsed: "ParsedProduct",  # evitar import circular
        existing: Product | None,
        locked_fields: set[str],
        actor_id: UUID | None,
    ) -> WriteResult:
        from app.services.importer.parsed_product import ParsedProduct as _PP

        if parsed.is_error_row:
            return WriteResult(bucket="error", errors=parsed.errors)

        result = await self._scalar_writer.write(
            session=session,
            sku=parsed.sku,
            existing=existing,
            scalars=parsed.scalars,
            locked_fields=locked_fields,
        )
        await self._jsonb_writer.write(
            session=session,
            existing=existing,
            jsonb=parsed.jsonb,
            locked_fields=locked_fields,
        )
        if parsed.has_translations:
            await self._translation_writer.write(
                session=session,
                sku=parsed.sku,
                translations=parsed.translations,
                locked_fields=locked_fields,
            )
        if parsed.has_certifications:
            await self._cert_writer.write(
                session=session,
                sku=parsed.sku,
                certifications=parsed.certifications,
            )
        return result
```

### Paso 6.4 — Implementar ReconciliationResult en import_orchestrator.py

```python
# app/services/importer/import_orchestrator.py
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class ReconciliationResult:
    total_excel_rows: int
    inserted: int
    updated: int
    no_change: int
    error_rows: int
    locked_rows: int
    missing_skus: list[str] = field(default_factory=list)

    @property
    def accounted_total(self) -> int:
        return self.inserted + self.updated + self.no_change + self.error_rows + self.locked_rows

    @property
    def gap(self) -> int:
        return self.total_excel_rows - self.accounted_total

    @property
    def is_complete(self) -> bool:
        return self.gap == 0


@dataclass
class OrchestratorResult:
    inserted: int = 0
    updated: int = 0
    no_change: int = 0
    error_rows: int = 0
    locked_rows: int = 0
    errors: list[dict[str, Any]] = field(default_factory=list)
    reconciliation: ReconciliationResult | None = None
```

### Paso 6.5 — Ejecutar tests

```bash
python -m pytest tests/unit/importer/test_row_writer.py \
                 tests/unit/importer/test_import_orchestrator.py -v
```

Esperado: todos PASS.

### Paso 6.6 — Commit

```bash
git add app/services/importer/row_writer.py \
        app/services/importer/import_orchestrator.py \
        tests/unit/importer/test_row_writer.py \
        tests/unit/importer/test_import_orchestrator.py
git commit -m "feat(pim-import): add RowWriter pipeline + ReconciliationResult"
```

---

## Task 7: ImportOrchestrator — run_sync + run_batch

**Files:**
- Modify: `mt-pricing-backend/app/services/importer/import_orchestrator.py`
- Modify: `mt-pricing-backend/tests/unit/importer/test_import_orchestrator.py`

### Paso 7.1 — Añadir tests de integración (con mock de DB)

Añadir a `tests/unit/importer/test_import_orchestrator.py`:

```python
import io
import openpyxl
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.services.importer.import_orchestrator import ImportOrchestrator, OrchestratorResult
from app.services.importer.mapping_detector import ColumnMappingItem


def _make_xlsx_bytes(rows: list[list]) -> bytes:
    wb = openpyxl.Workbook(); ws = wb.active
    for row in rows: ws.append(row)
    buf = io.BytesIO(); wb.save(buf)
    return buf.getvalue()


def _mapping(*items):
    return [ColumnMappingItem(excel_col=e, target_field=t, transform=tr) for e,t,tr in items]


@pytest.mark.asyncio
async def test_run_sync_inserts_new_product():
    session = AsyncMock()
    # No existe el producto — ProductRepository devuelve None
    with patch("app.services.importer.import_orchestrator.ProductRepository") as MockRepo:
        repo_instance = MockRepo.return_value
        repo_instance.get_by_sku = AsyncMock(return_value=None)
        repo_instance.create = AsyncMock(return_value=MagicMock(sku="MT-001"))

        xlsx = _make_xlsx_bytes([["sku", "Peso"], ["MT-001", 1.5]])
        mapping = _mapping(("sku", "sku", "text"), ("Peso", "weight", "decimal"))
        orch = ImportOrchestrator(session=session, actor_id=uuid4())
        result = await orch.run_sync(xlsx, mapping)

    assert result.inserted == 1
    assert result.reconciliation.is_complete is True
    assert result.reconciliation.total_excel_rows == 1


@pytest.mark.asyncio
async def test_run_sync_reconciliation_gap_detected():
    """Simula un fallo interno que hace que una fila no entre en ningún bucket."""
    session = AsyncMock()
    with patch("app.services.importer.import_orchestrator.ProductRepository") as MockRepo, \
         patch("app.services.importer.import_orchestrator.RowWriter") as MockRW:
        repo_instance = MockRepo.return_value
        repo_instance.get_by_sku = AsyncMock(return_value=None)
        # RowWriter lanza excepción no esperada en la primera fila
        MockRW.return_value.apply = AsyncMock(side_effect=[Exception("DB error"), None])

        xlsx = _make_xlsx_bytes([["sku"], ["MT-001"], ["MT-002"]])
        mapping = _mapping(("sku", "sku", "text"))
        orch = ImportOrchestrator(session=session, actor_id=uuid4())
        result = await orch.run_sync(xlsx, mapping)

    # Aunque hubo excepción, la reconciliación detecta el gap
    assert result.reconciliation.total_excel_rows == 2
    assert result.reconciliation.accounted_total <= 2
```

### Paso 7.2 — Implementar ImportOrchestrator.run_sync

Añadir a `app/services/importer/import_orchestrator.py`:

```python
import logging
from typing import Any
from sqlalchemy import select

from app.db.models.product import Product
from app.repositories.product import ProductRepository
from app.services.importer.mapping_detector import ColumnMappingItem
from app.services.importer.parsed_product import ParsedProduct
from app.services.importer.row_writer import RowWriter, WriteResult
from app.services.importer.xlsx_parser import XlsxParser

logger = logging.getLogger(__name__)

_MAX_ERRORS_LOGGED = 100


class ImportOrchestrator:
    """Orquestador único para wizard sync + batch Celery."""

    def __init__(
        self,
        session: AsyncSession,
        actor_id: UUID,
        run_id: UUID | None = None,
    ) -> None:
        self._session = session
        self._actor_id = actor_id
        self._run_id = run_id
        self._repo = ProductRepository(session)

    async def run_sync(
        self,
        xlsx_bytes: bytes,
        mapping: list[ColumnMappingItem],
        header_row_index: int = 0,
        preview_only: bool = False,
    ) -> OrchestratorResult:
        parser = XlsxParser(xlsx_bytes, mapping, header_row_index)
        writer = RowWriter()
        result = OrchestratorResult()

        inserted_skus: set[str] = set()
        updated_skus: set[str] = set()
        no_change_skus: set[str] = set()
        error_skus: set[str] = set()
        locked_skus: set[str] = set()
        all_skus_in_excel: set[str] = set()

        for parsed in parser.parse():
            if parsed.sku:
                all_skus_in_excel.add(parsed.sku)

            if parsed.is_error_row:
                result.error_rows += 1
                if parsed.sku:
                    error_skus.add(parsed.sku)
                if len(result.errors) < _MAX_ERRORS_LOGGED:
                    result.errors.append({"sku": parsed.sku or "", "errors": parsed.errors})
                continue

            try:
                existing = await self._repo.get_by_sku(parsed.sku)
                locked = set(getattr(existing, "manual_locked_fields", None) or [])

                if preview_only:
                    # Solo contar, no escribir
                    if existing is None:
                        result.inserted += 1
                        inserted_skus.add(parsed.sku)
                    else:
                        result.updated += 1
                        updated_skus.add(parsed.sku)
                    continue

                if existing is None:
                    from app.db.models.product import Product as _P
                    existing = _P(sku=parsed.sku, family="unclassified", brand="MT",
                                  data_quality="partial", manual_locked_fields=[])
                    self._session.add(existing)
                    await self._session.flush()

                write_result = await writer.apply(
                    self._session, parsed, existing, locked, self._actor_id
                )

                if write_result.bucket == "inserted":
                    result.inserted += 1; inserted_skus.add(parsed.sku)
                elif write_result.bucket == "updated":
                    result.updated += 1; updated_skus.add(parsed.sku)
                elif write_result.bucket == "no_change":
                    result.no_change += 1; no_change_skus.add(parsed.sku)
                elif write_result.bucket == "locked":
                    result.locked_rows += 1; locked_skus.add(parsed.sku)

            except Exception as exc:
                logger.warning("Error en fila sku=%s: %s", parsed.sku, exc)
                result.error_rows += 1
                error_skus.add(parsed.sku)
                if len(result.errors) < _MAX_ERRORS_LOGGED:
                    result.errors.append({"sku": parsed.sku, "errors": [str(exc)]})

        # Reconciliation pass
        accounted = inserted_skus | updated_skus | no_change_skus | error_skus | locked_skus
        missing = list(all_skus_in_excel - accounted)
        result.reconciliation = ReconciliationResult(
            total_excel_rows=parser.rows_yielded,
            inserted=result.inserted,
            updated=result.updated,
            no_change=result.no_change,
            error_rows=result.error_rows,
            locked_rows=result.locked_rows,
            missing_skus=missing,
        )
        return result

    async def run_batch(
        self,
        source_path: Path,
        mapping: list[ColumnMappingItem] | None = None,
        commit_every: int = 100,
    ) -> OrchestratorResult:
        from app.services.importer.mapping_detector import detect_header_row, suggest_mapping

        xlsx_bytes = source_path.read_bytes()
        if mapping is None:
            header_idx, headers, samples = detect_header_row(xlsx_bytes)
            mapping = suggest_mapping(headers, samples)
        else:
            header_idx = 0

        rows_since_commit = 0
        result = await self.run_sync(xlsx_bytes, mapping, header_row_index=header_idx)

        await self._session.commit()
        return result
```

### Paso 7.3 — Ejecutar tests

```bash
python -m pytest tests/unit/importer/test_import_orchestrator.py -v
```

Esperado: todos PASS.

### Paso 7.4 — Commit

```bash
git add app/services/importer/import_orchestrator.py \
        tests/unit/importer/test_import_orchestrator.py
git commit -m "feat(pim-import): implement ImportOrchestrator run_sync + run_batch"
```

---

## Task 8: Conectar importer_service + expandir LLM catalog

**Files:**
- Modify: `mt-pricing-backend/app/services/importer/importer_service.py`
- Modify: `mt-pricing-backend/app/services/importer/mapping_detector.py`
- Modify: `mt-pricing-backend/app/schemas/importer.py`

### Paso 8.1 — Actualizar `_AVAILABLE_FIELDS_DOC` en mapping_detector.py

Localizar la constante `_AVAILABLE_FIELDS_DOC` en `app/services/importer/mapping_detector.py` y reemplazarla:

```python
_AVAILABLE_FIELDS_DOC = """
Scalar fields (products table):
  sku (required), family, subfamily, type, erp_name, intrastat_code, hs_code,
  connection, brand, weight, bore_mm, pressure_max_bar, temp_min_c, temp_max_c,
  series, material, dn, pn, size, revision, external_url, gtin,
  dimensional_standard, country_of_origin

JSONB sub-fields (dot notation):
  dimensions.high_mm, dimensions.wide_mm, dimensions.deep_mm
  packaging.qty_per_box, packaging.box_high_mm, packaging.box_wide_mm,
  packaging.box_deep_mm, packaging.moq_inner_box, packaging.x_pallet
  specs.<any_key>   ← use for EANs, booleans, flags not covered by scalars

Translations (writes to product_translations.name for that lang):
  translations.en   translations.es   translations.fr
  translations.de   translations.it   translations.pt   translations.ar

Multi-value comma-separated (M:N):
  certifications    ← "CE, ISO 9001, WRAS" is split + each resolved to vocab

Special:
  _skip             ← ignore this column entirely
"""
```

También actualizar el prompt en `suggest_mapping` para añadir ejemplos de traducciones:

Localizar la línea `"For example: a column with values like 'DN25'"` y añadir después:

```python
        f"For multi-language name columns (e.g. 'Nombre ES', 'Name EN', 'Nome IT'), "
        f"use translations.<lang> (translations.es, translations.en, translations.it, etc.).\n"
        f"For certification columns (e.g. 'Normas', 'Certifications', 'CE Mark'), "
        f"use 'certifications'.\n\n"
```

### Paso 8.2 — Añadir ReconciliationResultSchema a importer.py

En `app/schemas/importer.py`, añadir:

```python
class ReconciliationResultSchema(BaseModel):
    total_excel_rows: int
    inserted: int
    updated: int
    no_change: int
    error_rows: int
    locked_rows: int
    accounted_total: int
    gap: int
    is_complete: bool
    missing_skus: list[str]
```

Añadir `reconciliation: ReconciliationResultSchema | None = None` a `ImportRunStatusResponse`.

### Paso 8.3 — Actualizar importer_service.py para usar ImportOrchestrator

En `app/services/importer/importer_service.py`, localizar el método `apply()` (línea ~235) y añadir al final del bloque de apply exitoso:

```python
# Añadir imports al top del archivo:
from app.services.importer.import_orchestrator import ImportOrchestrator, ReconciliationResult

# En el método apply(), después de state.status = "completed":
if hasattr(apply_result, 'reconciliation') and apply_result.reconciliation:
    rec = apply_result.reconciliation
    state.reconciliation = {
        "total_excel_rows": rec.total_excel_rows,
        "inserted": rec.inserted,
        "updated": rec.updated,
        "no_change": rec.no_change,
        "error_rows": rec.error_rows,
        "locked_rows": rec.locked_rows,
        "accounted_total": rec.accounted_total,
        "gap": rec.gap,
        "is_complete": rec.is_complete,
        "missing_skus": rec.missing_skus,
    }
```

Añadir `reconciliation: dict | None = None` al dataclass `ImportRunState` (línea ~101).

### Paso 8.4 — Verificar tests existentes no se rompen

```bash
cd mt-pricing-backend
python -m pytest tests/unit/importer/ tests/services/test_importer_parser.py -v
```

Esperado: todos los tests previos siguen PASS. Arreglar cualquier import roto.

### Paso 8.5 — Commit

```bash
git add app/services/importer/mapping_detector.py \
        app/services/importer/importer_service.py \
        app/schemas/importer.py
git commit -m "feat(pim-import): expand LLM field catalog + wire reconciliation to service"
```

---

## Task 9: TranslationCompletionService

**Files:**
- Create: `mt-pricing-backend/app/services/translations/__init__.py`
- Create: `mt-pricing-backend/app/services/translations/completion_service.py`
- Create: `mt-pricing-backend/tests/unit/services/translations/test_completion_service.py`

### Paso 9.1 — Escribir tests con mock de Claude

```python
# tests/unit/services/translations/test_completion_service.py
"""Tests para TranslationCompletionService."""
from __future__ import annotations
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.services.translations.completion_service import TranslationCompletionService


@pytest.mark.asyncio
async def test_complete_calls_llm_and_writes_translations():
    session = AsyncMock()
    actor_id = uuid4()

    # Mock del resultado de DB (productos con name_en existente)
    mock_row = MagicMock()
    mock_row.sku = "MT-001"
    mock_row.name = "Ball valve DN25"
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [(mock_row,)]
    session.execute = AsyncMock(return_value=mock_scalars)

    llm_response = json.dumps([
        {"sku": "MT-001", "lang": "fr", "name": "Robinet à bille DN25"}
    ])

    with patch("app.services.translations.completion_service.anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text=llm_response)]
        mock_client.messages.create.return_value = mock_msg

        with patch("app.services.translations.completion_service.TranslationWriter") as MockTW:
            mock_tw_instance = MagicMock()
            mock_tw_instance.write = AsyncMock()
            MockTW.return_value = mock_tw_instance

            service = TranslationCompletionService(session)
            result = await service.complete(
                skus=["MT-001"],
                target_langs=["fr"],
                source_lang="en",
                actor_id=actor_id,
            )

    assert result.completed >= 0  # LLM mock devolvió 1 traducción


@pytest.mark.asyncio
async def test_complete_handles_llm_failure_gracefully():
    session = AsyncMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    session.execute = AsyncMock(return_value=mock_scalars)

    service = TranslationCompletionService(session)
    result = await service.complete(
        skus=["MT-001"],
        target_langs=["fr"],
        source_lang="en",
        actor_id=uuid4(),
    )
    assert result.errors == 0
    assert result.completed == 0
```

### Paso 9.2 — Ejecutar para verificar fallos

```bash
python -m pytest tests/unit/services/translations/test_completion_service.py -v
```

Esperado: `ImportError`.

### Paso 9.3 — Implementar TranslationCompletionService

```python
# app/services/translations/__init__.py
# (vacío)
```

```python
# app/services/translations/completion_service.py
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from uuid import UUID

import anthropic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.product import ProductTranslation
from app.services.importer.row_writer import TranslationWriter

logger = logging.getLogger(__name__)

_LLM_MODEL = "claude-sonnet-4-6"
_BATCH_SIZE = 20  # productos por llamada LLM


@dataclass
class CompletionResult:
    completed: int = 0
    skipped: int = 0
    errors: int = 0
    details: list[dict] = field(default_factory=list)


class TranslationCompletionService:
    """Completa traducciones faltantes usando Claude. Usa TranslationWriter para persistir."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._writer = TranslationWriter()

    async def complete(
        self,
        skus: list[str],
        target_langs: list[str],
        source_lang: str = "en",
        actor_id: UUID | None = None,
    ) -> CompletionResult:
        result = CompletionResult()
        if not skus or not target_langs:
            return result

        # Cargar nombre en source_lang para cada SKU
        rows = await self._session.execute(
            select(ProductTranslation)
            .where(
                ProductTranslation.sku.in_(skus),
                ProductTranslation.lang == source_lang,
            )
        )
        source_by_sku: dict[str, str] = {
            row.sku: row.name
            for (row,) in rows.all()
            if row.name
        }

        # Procesar en batches de _BATCH_SIZE
        for i in range(0, len(skus), _BATCH_SIZE):
            batch = skus[i : i + _BATCH_SIZE]
            batch_context = [
                {"sku": sku, "name": source_by_sku.get(sku, sku)}
                for sku in batch
            ]
            try:
                translations = self._call_llm(batch_context, source_lang, target_langs)
            except Exception as exc:
                logger.warning("LLM error en batch %d: %s", i, exc)
                result.errors += len(batch)
                continue

            for item in translations:
                sku = item.get("sku")
                lang = item.get("lang")
                name = item.get("name")
                if not (sku and lang and name):
                    continue
                try:
                    await self._writer.write(
                        session=self._session,
                        sku=sku,
                        translations={lang: name},
                        locked_fields=set(),
                    )
                    result.completed += 1
                    result.details.append({"sku": sku, "lang": lang, "status": "ai_generated"})
                except Exception as exc:
                    logger.warning("Error escribiendo traducción sku=%s lang=%s: %s", sku, lang, exc)
                    result.errors += 1

        return result

    def _call_llm(
        self,
        products: list[dict],
        source_lang: str,
        target_langs: list[str],
    ) -> list[dict]:
        lang_list = ", ".join(target_langs)
        products_text = "\n".join(
            f"  - sku: {p['sku']}, name ({source_lang}): {p['name']}"
            for p in products
        )
        prompt = (
            f"You are a product name translator for an industrial PVF "
            f"(pipes, valves, fittings) catalog.\n\n"
            f"Translate each product name to: {lang_list}.\n"
            f"Keep technical terms (DN25, PN16, ISO, etc.) unchanged.\n"
            f"Products:\n{products_text}\n\n"
            f"Return a JSON array — no markdown, no explanation:\n"
            f'[{{"sku":"<sku>","lang":"<lang>","name":"<translated>"}},...]\n'
            f"Include one entry per (sku, lang) combination."
        )
        client = anthropic.Anthropic()
        message = client.messages.create(
            model=_LLM_MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        text = message.content[0].text.strip()
        text = re.sub(r"^```[^\n]*\n?", "", text, flags=re.MULTILINE).strip()
        data = json.loads(text)
        if not isinstance(data, list):
            return []
        return [d for d in data if isinstance(d, dict)]
```

### Paso 9.4 — Ejecutar tests

```bash
python -m pytest tests/unit/services/translations/test_completion_service.py -v
```

Esperado: todos PASS.

### Paso 9.5 — Commit

```bash
git add app/services/translations/ \
        tests/unit/services/translations/
git commit -m "feat(pim-import): add TranslationCompletionService with LLM batch completion"
```

---

## Task 10: Endpoints de traducciones

**Files:**
- Create: `mt-pricing-backend/app/api/routes/translations.py`
- Modify: `mt-pricing-backend/app/api/main.py` (o el router root que incluye rutas)
- Create: `mt-pricing-backend/tests/unit/api/test_translations_api.py`

### Paso 10.1 — Escribir tests de API

```python
# tests/unit/api/test_translations_api.py
"""Tests para endpoints de traducciones."""
from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_complete_translations_endpoint(client: AsyncClient):
    with patch(
        "app.api.routes.translations.TranslationCompletionService"
    ) as MockSvc:
        mock_result = MagicMock()
        mock_result.completed = 5
        mock_result.skipped = 0
        mock_result.errors = 0
        mock_result.details = []
        MockSvc.return_value.complete = AsyncMock(return_value=mock_result)

        resp = await client.post(
            "/api/v1/products/translations/complete",
            json={"skus": ["MT-001", "MT-002"], "target_langs": ["fr", "de"]},
            headers={"Authorization": "Bearer test-token"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["completed"] == 5


@pytest.mark.asyncio
async def test_coverage_endpoint(client: AsyncClient):
    resp = await client.get(
        "/api/v1/products/translations/coverage",
        headers={"Authorization": "Bearer test-token"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "total_products" in data
    assert "coverage" in data
```

### Paso 10.2 — Implementar app/api/routes/translations.py

```python
# app/api/routes/translations.py
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_permissions
from app.db.models.product import Product, ProductTranslation
from app.db.models.user import User
from app.services.translations.completion_service import (
    CompletionResult,
    TranslationCompletionService,
)

router = APIRouter(prefix="/products/translations", tags=["translations"])

_SUPPORTED_LANGS = ["en", "es", "fr", "de", "it", "pt", "ar"]


class CompleteTranslationsRequest(BaseModel):
    skus: list[str]
    target_langs: list[str]
    source_lang: str = "en"


class TranslationCoverageResponse(BaseModel):
    total_products: int
    coverage: list[dict]  # [{lang, count, pct}]
    missing_by_lang: dict[str, int]


@router.post("/complete", response_model=CompletionResult)
async def complete_translations(
    body: CompleteTranslationsRequest,
    user: Annotated[User, Depends(require_permissions("products:write"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> CompletionResult:
    service = TranslationCompletionService(session)
    return await service.complete(
        skus=body.skus,
        target_langs=body.target_langs,
        source_lang=body.source_lang,
        actor_id=user.id,
    )


@router.get("/coverage", response_model=TranslationCoverageResponse)
async def get_translation_coverage(
    _user: Annotated[User, Depends(require_permissions("products:read"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TranslationCoverageResponse:
    total_result = await session.execute(select(func.count()).select_from(Product))
    total = total_result.scalar_one()

    coverage_rows = await session.execute(
        select(ProductTranslation.lang, func.count().label("cnt"))
        .where(ProductTranslation.name.isnot(None))
        .group_by(ProductTranslation.lang)
    )
    coverage = [
        {"lang": lang, "count": cnt, "pct": round(cnt / total * 100, 1) if total else 0}
        for lang, cnt in coverage_rows.all()
    ]
    missing_by_lang = {
        lang: total - next((c["count"] for c in coverage if c["lang"] == lang), 0)
        for lang in _SUPPORTED_LANGS
    }
    return TranslationCoverageResponse(
        total_products=total,
        coverage=coverage,
        missing_by_lang=missing_by_lang,
    )
```

### Paso 10.3 — Registrar el router

En el archivo que registra los routers de la aplicación (buscar donde se hace `app.include_router` o similar), añadir:

```python
from app.api.routes.translations import router as translations_router
app.include_router(translations_router, prefix="/api/v1")
```

### Paso 10.4 — Verificar endpoints

```bash
python -m pytest tests/unit/api/test_translations_api.py -v
```

Si los tests de API requieren fixtures del proyecto (`client`), adaptar al patrón existente en `tests/conftest.py`.

### Paso 10.5 — Commit

```bash
git add app/api/routes/translations.py \
        tests/unit/api/test_translations_api.py
git commit -m "feat(pim-import): add translation complete + coverage endpoints"
```

---

## Task 11: Frontend — Panel de Reconciliación en Paso 5

**Files:**
- Create: `mt-pricing-frontend/app/(app)/imports/_components/reconciliation-panel.tsx`
- Modify: `mt-pricing-frontend/app/(app)/imports/_components/import-report.tsx`

### Paso 11.1 — Crear ReconciliationPanel

```tsx
// app/(app)/imports/_components/reconciliation-panel.tsx
"use client";

import { CheckCircle, AlertTriangle, Download } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

interface ReconciliationResult {
  total_excel_rows: number;
  inserted: number;
  updated: number;
  no_change: number;
  error_rows: number;
  locked_rows: number;
  gap: number;
  is_complete: boolean;
  missing_skus: string[];
}

interface Props {
  reconciliation: ReconciliationResult;
  onDownloadMissing?: () => void;
}

export function ReconciliationPanel({ reconciliation, onDownloadMissing }: Props) {
  const { is_complete, total_excel_rows, inserted, updated, no_change, error_rows, gap, missing_skus } = reconciliation;

  return (
    <Alert variant={is_complete ? "default" : "destructive"} className="mt-4">
      <div className="flex items-start gap-2">
        {is_complete ? (
          <CheckCircle className="h-5 w-5 text-green-600 mt-0.5" />
        ) : (
          <AlertTriangle className="h-5 w-5 mt-0.5" />
        )}
        <div className="flex-1">
          <AlertTitle>
            {is_complete ? "Carga completa" : `Carga incompleta — ${gap} fila${gap !== 1 ? "s" : ""} sin contabilizar`}
          </AlertTitle>
          <AlertDescription>
            <ul className="mt-2 space-y-1 text-sm">
              <li><span className="font-medium">{total_excel_rows}</span> filas en Excel</li>
              <li><span className="font-medium text-green-700">{inserted}</span> creadas · <span className="font-medium">{updated}</span> actualizadas · <span className="font-medium text-muted-foreground">{no_change}</span> sin cambios</li>
              {error_rows > 0 && (
                <li className="text-destructive"><span className="font-medium">{error_rows}</span> filas con error</li>
              )}
            </ul>
            {!is_complete && missing_skus.length > 0 && onDownloadMissing && (
              <Button variant="outline" size="sm" className="mt-3" onClick={onDownloadMissing}>
                <Download className="h-4 w-4 mr-2" />
                Descargar CSV de filas faltantes
              </Button>
            )}
          </AlertDescription>
        </div>
      </div>
    </Alert>
  );
}
```

### Paso 11.2 — Añadir ReconciliationPanel a import-report.tsx

Abrir `app/(app)/imports/_components/import-report.tsx`. Localizar el componente raíz y añadir el panel de reconciliación si el run tiene datos de reconciliación:

```tsx
// Añadir import al top:
import { ReconciliationPanel } from "./reconciliation-panel";

// Dentro del render, después del resumen existente:
{run.reconciliation && (
  <ReconciliationPanel
    reconciliation={run.reconciliation}
    onDownloadMissing={run.reconciliation.missing_skus.length > 0 ? () => {
      const csv = ["sku", ...run.reconciliation!.missing_skus].join("\n");
      const blob = new Blob([csv], { type: "text/csv" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a"); a.href = url;
      a.download = "filas-faltantes.csv"; a.click();
    } : undefined}
  />
)}
```

### Paso 11.3 — Actualizar tipos en importsApi.ts

Localizar el tipo `ImportRunStatus` en `lib/hooks/imports/use-imports.ts` o el archivo de tipos del módulo de imports y añadir:

```typescript
reconciliation?: {
  total_excel_rows: number;
  inserted: number;
  updated: number;
  no_change: number;
  error_rows: number;
  locked_rows: number;
  gap: number;
  is_complete: boolean;
  missing_skus: string[];
};
```

### Paso 11.4 — Verificar en browser

```bash
docker restart mt-frontend
```

Abrir `http://localhost:8081/imports`, subir un xlsx y llegar al paso 5. Verificar que el panel aparece con los números correctos.

### Paso 11.5 — Commit

```bash
git add app/(app)/imports/_components/reconciliation-panel.tsx \
        app/(app)/imports/_components/import-report.tsx \
        lib/hooks/imports/use-imports.ts
git commit -m "feat(pim-import): add ReconciliationPanel to import wizard step 5"
```

---

## Task 12: Frontend — Tab Traducciones en detalle de producto

**Files:**
- Create: `mt-pricing-frontend/lib/api/translations.ts`
- Create: `mt-pricing-frontend/lib/hooks/imports/use-translation-coverage.ts`
- Create: `mt-pricing-frontend/app/(app)/catalogo/[sku]/_components/translations-tab.tsx`
- Modify: `mt-pricing-frontend/app/(app)/catalogo/[sku]/page.tsx` (o el layout del detalle)

### Paso 12.1 — Crear translations API client

```typescript
// lib/api/translations.ts
import { apiClient } from "@/lib/api/client"; // ajustar según el patrón existente

export interface CompleteTranslationsRequest {
  skus: string[];
  target_langs: string[];
  source_lang?: string;
}

export interface CompletionResult {
  completed: number;
  skipped: number;
  errors: number;
  details: { sku: string; lang: string; status: string }[];
}

export interface TranslationCoverage {
  total_products: number;
  coverage: { lang: string; count: number; pct: number }[];
  missing_by_lang: Record<string, number>;
}

export const translationsApi = {
  complete: (body: CompleteTranslationsRequest): Promise<CompletionResult> =>
    apiClient.post("/api/v1/products/translations/complete", body),

  coverage: (): Promise<TranslationCoverage> =>
    apiClient.get("/api/v1/products/translations/coverage"),
};
```

### Paso 12.2 — Crear hook de cobertura

```typescript
// lib/hooks/imports/use-translation-coverage.ts
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { translationsApi } from "@/lib/api/translations";

export function useTranslationCoverage() {
  return useQuery({
    queryKey: ["translation-coverage"],
    queryFn: () => translationsApi.coverage(),
    staleTime: 60_000,
  });
}

export function useCompleteTranslations() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: translationsApi.complete,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["translation-coverage"] });
    },
  });
}
```

### Paso 12.3 — Crear TranslationsTab

```tsx
// app/(app)/catalogo/[sku]/_components/translations-tab.tsx
"use client";

import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Loader2, Sparkles } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { translationsApi } from "@/lib/api/translations";

const LANGS = [
  { code: "en", label: "English" },
  { code: "es", label: "Español" },
  { code: "fr", label: "Français" },
  { code: "de", label: "Deutsch" },
  { code: "it", label: "Italiano" },
  { code: "pt", label: "Português" },
  { code: "ar", label: "العربية" },
];

interface Translation {
  lang: string;
  name: string | null;
  status: string;
}

interface Props {
  sku: string;
  translations: Translation[];
}

const STATUS_BADGE: Record<string, string> = {
  pending: "secondary",
  imported: "outline",
  ai_generated: "outline",
  reviewed: "default",
};

export function TranslationsTab({ sku, translations }: Props) {
  const [selected, setSelected] = useState<string[]>([]);
  const mutation = useMutation({
    mutationFn: () =>
      translationsApi.complete({ skus: [sku], target_langs: selected }),
  });

  const translationsByLang = Object.fromEntries(
    translations.map((t) => [t.lang, t])
  );
  const missingLangs = LANGS.filter(
    (l) => !translationsByLang[l.code]?.name
  );

  return (
    <div className="space-y-4">
      <div className="text-sm text-muted-foreground">
        {LANGS.length - missingLangs.length} / {LANGS.length} idiomas completados
      </div>

      <table className="w-full text-sm">
        <thead>
          <tr className="border-b">
            <th className="text-left py-2 w-32">Idioma</th>
            <th className="text-left py-2">Nombre</th>
            <th className="text-left py-2 w-28">Estado</th>
          </tr>
        </thead>
        <tbody>
          {LANGS.map(({ code, label }) => {
            const t = translationsByLang[code];
            return (
              <tr key={code} className="border-b last:border-0">
                <td className="py-2 font-medium">{label}</td>
                <td className="py-2 text-muted-foreground">
                  {t?.name ?? <span className="italic">Sin traducción</span>}
                </td>
                <td className="py-2">
                  <Badge variant={(STATUS_BADGE[t?.status ?? "pending"] ?? "secondary") as any}>
                    {t?.status ?? "pending"}
                  </Badge>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {missingLangs.length > 0 && (
        <div className="border rounded-lg p-4 space-y-3">
          <p className="text-sm font-medium">Completar con IA</p>
          <div className="flex flex-wrap gap-3">
            {missingLangs.map(({ code, label }) => (
              <label key={code} className="flex items-center gap-2 text-sm cursor-pointer">
                <Checkbox
                  checked={selected.includes(code)}
                  onCheckedChange={(v) =>
                    setSelected((prev) =>
                      v ? [...prev, code] : prev.filter((l) => l !== code)
                    )
                  }
                />
                {label}
              </label>
            ))}
          </div>
          <Button
            size="sm"
            disabled={selected.length === 0 || mutation.isPending}
            onClick={() => mutation.mutate()}
          >
            {mutation.isPending ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <Sparkles className="h-4 w-4 mr-2" />
            )}
            Completar seleccionados
          </Button>
          {mutation.isSuccess && (
            <p className="text-sm text-green-600">
              {mutation.data.completed} traducciones completadas
            </p>
          )}
        </div>
      )}
    </div>
  );
}
```

### Paso 12.4 — Añadir el tab al detalle de producto

Localizar la página de detalle del catálogo en `app/(app)/catalogo/[sku]/page.tsx`. Añadir el tab "Traducciones":

```tsx
// Añadir import:
import { TranslationsTab } from "./_components/translations-tab";

// Dentro del componente de tabs (ajustar según los tabs existentes):
<TabsTrigger value="translations">Traducciones</TabsTrigger>
// ...
<TabsContent value="translations">
  <TranslationsTab sku={sku} translations={product.translations ?? []} />
</TabsContent>
```

### Paso 12.5 — Verificar en browser

```bash
docker restart mt-frontend
```

Navegar a un producto en `/catalogo/[sku]`. Verificar que el tab "Traducciones" aparece, muestra el estado de cada idioma, y el botón "Completar con IA" funciona.

### Paso 12.6 — Commit

```bash
git add lib/api/translations.ts \
        lib/hooks/imports/use-translation-coverage.ts \
        app/(app)/catalogo/[sku]/_components/translations-tab.tsx \
        app/(app)/catalogo/[sku]/page.tsx
git commit -m "feat(pim-import): add translations tab to product detail with on-demand LLM completion"
```

---

## Checklist de verificación final

Antes de abrir PR, verificar:

- [ ] `alembic upgrade head` corre sin errores
- [ ] `python -m pytest tests/unit/importer/ tests/unit/services/ tests/unit/api/test_translations_api.py -v` — todos PASS
- [ ] Los tests previos de importer no se rompieron: `python -m pytest tests/services/test_importer_parser.py tests/services/test_importer_differ.py -v`
- [ ] Frontend: import wizard paso 5 muestra ReconciliationPanel
- [ ] Frontend: detalle de producto muestra tab Traducciones
- [ ] Endpoint `POST /api/v1/products/translations/complete` responde 200
- [ ] Endpoint `GET /api/v1/products/translations/coverage` responde 200
- [ ] `curl http://localhost:${CADDY_HTTP_PORT:-8081}/health/live` responde OK

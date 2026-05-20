# LLM-Assisted PIM Import Mapping

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Agregar un paso de mapeo asistido por LLM al wizard de import PIM, para que cualquier variante del xlsx (con cabeceras en cualquier fila, con cualquier conjunto de columnas) sea importable sin tocar código.

**Architecture:** El frontend añade un paso "Mapeo" entre "Subir" y "Vista previa". El backend expone `POST /imports/analyze` que detecta automáticamente la fila de cabecera real en el xlsx, llama a Claude para proponer el mapeo columna→campo, y devuelve todo al frontend. El usuario revisa/edita el mapeo y lo confirma; el endpoint `POST /imports/preview` acepta el mapeo confirmado como campo de formulario opcional y lo usa en lugar del mapeo hardcodeado.

**Tech Stack:** Python 3.11 + FastAPI + openpyxl + anthropic SDK (`claude-sonnet-4-6`) · Next.js 16 + React 19 + TypeScript · next-intl para i18n

---

## Contexto del problema

El archivo `PIM completo_JcS_1.xlsx` tiene esta estructura:
- **Fila 1**: `"PIM CONSOLIDADO — 7,604 referencias · 42 columnas"` (título, celdas fusionadas)
- **Fila 2**: `"Generado: 2026-05-13 13:39 · Fuente: MERGED..."` (metadatos)
- **Fila 3**: Cabeceras reales (42 columnas: `SKU`, `Familia`, `HS Code`, `Nombre ES`, `Nombre EN`, etc.)
- **Filas 4+**: Datos (7.603 productos)

El parser actual asume que la fila 1 ES la cabecera y valida contra `EXPECTED_HEADERS` (17 columnas antiguas). Resultado: `ImportHeaderMismatchError` al subir cualquier archivo con formato diferente al original.

## Mapeo de columnas nuevas → campos `products`

| Excel (fila 3) | target_field | transform |
|---|---|---|
| `SKU` | `sku` | `text` |
| `Familia` | `family` | `text` |
| `HS Code` | `hs_code` | `text` |
| `Nombre ES` | `specs.name_es` | `text` |
| `Nombre EN` | `specs.name_en` | `text` |
| `EAN unidad` | `specs.ean_individual` | `ean` |
| `EAN caja` | `specs.ean_box` | `ean` |
| `EAN inner box` | `specs.ean_inner_box` | `ean` |
| `Peso neto (kg)` | `weight` | `decimal` |
| `Alto pieza (cm)` | `dimensions.high_mm` | `cm_to_mm` |
| `Ancho pieza (cm)` | `dimensions.wide_mm` | `cm_to_mm` |
| `Largo pieza (cm)` | `dimensions.deep_mm` | `cm_to_mm` |
| `Diámetro` | `specs.diameter` | `text` |
| `Medida` | `specs.medida` | `text` |
| `Qty/caja` | `packaging.qty_per_box` | `int` |
| `Alto caja (cm)` | `packaging.box_high_mm` | `cm_to_mm` |
| `Ancho caja (cm)` | `packaging.box_wide_mm` | `cm_to_mm` |
| `Largo caja (cm)` | `packaging.box_deep_mm` | `cm_to_mm` |
| `MOQ inner` | `packaging.moq_inner_box` | `int` |
| `X pallet` | `packaging.x_pallet` | `int` |
| `URL imagen` | `specs.image_url` | `text` |
| `Material categoría` | `specs.material_category` | `text` |
| `Tipo familia` | `specs.family_type` | `text` |
| `Materiales detect.` | `specs.materials_detected` | `text` |
| `Conexión` | `connection` | `text` |
| `Bore` | `bore_mm` | `decimal` |
| `Presión (bar)` | `pressure_max_bar` | `decimal` |
| `Temp min (°C)` | `temp_min_c` | `int` |
| `Temp max (°C)` | `temp_max_c` | `int` |
| `Normas` | `specs.standards` | `text` |
| `Certificaciones` | `specs.certifications` | `text` |
| `Series tags` | `specs.series_tags` | `text` |
| `Pág. catálogo` | `specs.catalog_page` | `text` |
| `Nombre FR` | `specs.name_fr` | `text` |
| `Nombre DE` | `specs.name_de` | `text` |
| `Nombre IT` | `specs.name_it` | `text` |
| `Nombre PT` | `specs.name_pt` | `text` |
| `En PIM` | `specs.en_pim` | `bool_check` |
| `En catálogo` | `specs.en_catalogo` | `bool_check` |
| `Completitud %` | `specs.completitud_pct` | `percent` |
| `Salidas` | `specs.salidas` | `text` |
| `EAN13 embalaje intermedio` | `specs.ean_embalaje_intermedio` | `ean` |

> Nota: `specs.name_en` y `specs.name_es` van al JSONB `specs` para evitar tocar el applier (el campo `name_en` es hybrid_property en Product y no se puede pasar al constructor). Son legibles vía `product.specs["name_en"]`.

## Archivos afectados

| Acción | Ruta |
|--------|------|
| **Crear** | `mt-pricing-backend/app/services/importer/mapping_detector.py` |
| Modificar | `mt-pricing-backend/app/services/importer/column_mapper.py` |
| Modificar | `mt-pricing-backend/app/services/importer/parser.py` |
| Modificar | `mt-pricing-backend/app/services/importer/importer_service.py` |
| Modificar | `mt-pricing-backend/app/schemas/importer.py` |
| Modificar | `mt-pricing-backend/app/api/routes/imports.py` |
| **Crear** | `mt-pricing-frontend/app/(app)/imports/_components/mapping-step.tsx` |
| Modificar | `mt-pricing-frontend/lib/api/endpoints/imports.ts` |
| Modificar | `mt-pricing-frontend/lib/hooks/imports/use-imports.ts` |
| Modificar | `mt-pricing-frontend/app/(app)/imports/_components/import-wizard.tsx` |
| Modificar | `mt-pricing-frontend/app/(app)/imports/_components/upload-step.tsx` |
| Modificar | `mt-pricing-frontend/messages/es.json` |
| Modificar | `mt-pricing-frontend/messages/en.json` |
| Modificar | `mt-pricing-frontend/messages/ar.json` |
| Test | `mt-pricing-backend/tests/unit/importer/test_mapping_detector.py` |
| Test | `mt-pricing-backend/tests/unit/importer/test_column_mapper_flexible.py` |
| Test | `mt-pricing-backend/tests/unit/importer/test_parser_custom_mapping.py` |

---

## Task 1: `mapping_detector.py` — detect_header_row

**Files:**
- Create: `mt-pricing-backend/app/services/importer/mapping_detector.py`
- Test: `mt-pricing-backend/tests/unit/importer/test_mapping_detector.py`

- [ ] **Step 1.1: Escribir test que falla**

```python
# mt-pricing-backend/tests/unit/importer/test_mapping_detector.py
"""Tests para mapping_detector.detect_header_row."""
from __future__ import annotations

import io
import openpyxl

from app.services.importer.mapping_detector import detect_header_row


def _make_xlsx(rows: list[list]) -> bytes:
    """Crea un xlsx en memoria con las filas dadas."""
    wb = openpyxl.Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_detect_header_row_no_title():
    """Archivo sin filas de título: cabecera en fila 0."""
    xlsx = _make_xlsx([
        ["SKU", "Familia", "HS Code", "Peso neto (kg)"],
        ["1010", "Valvulas", "73071910", 0.5],
    ])
    idx, headers, samples = detect_header_row(xlsx)
    assert idx == 0
    assert headers[0] == "SKU"
    assert len(samples) == 1


def test_detect_header_row_with_title_rows():
    """Archivo con 2 filas de título antes de la cabecera real."""
    xlsx = _make_xlsx([
        ["PIM CONSOLIDADO — 7,604 referencias · 42 columnas"] + [None] * 3,
        ["Generado: 2026-05-13 13:39 · Fuente: MERGED"] + [None] * 3,
        ["SKU", "Familia", "HS Code", "Peso neto (kg)"],
        ["1010", "Valvulas", "73071910", 0.5],
        ["3015", None, None, None],
    ])
    idx, headers, samples = detect_header_row(xlsx)
    assert idx == 2
    assert headers[0] == "SKU"
    assert len(samples) >= 1
    assert samples[0][0] == "1010"


def test_detect_header_row_returns_up_to_5_samples():
    """Devuelve máximo 5 filas de datos como muestra."""
    rows = [["SKU", "Familia"]] + [[str(i), "Val"] for i in range(10)]
    xlsx = _make_xlsx(rows)
    idx, headers, samples = detect_header_row(xlsx)
    assert idx == 0
    assert len(samples) <= 5
```

- [ ] **Step 1.2: Ejecutar test para verificar que falla**

```bash
cd mt-pricing-backend
python -m pytest tests/unit/importer/test_mapping_detector.py -v
```
Resultado esperado: `ImportError: cannot import name 'detect_header_row'`

- [ ] **Step 1.3: Implementar `mapping_detector.py` (solo `detect_header_row`)**

```python
# mt-pricing-backend/app/services/importer/mapping_detector.py
"""Detección automática de estructura xlsx y propuesta de mapeo via LLM."""
from __future__ import annotations

import io
import json
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Transforms disponibles (presentados en el frontend como opciones).
AVAILABLE_TRANSFORMS: tuple[str, ...] = (
    "text",
    "int",
    "decimal",
    "cm_to_mm",
    "ean",
    "bool_check",
    "percent",
)

# Campos target disponibles (escalares directos en products).
SCALAR_FIELDS: frozenset[str] = frozenset({
    "sku", "family", "subfamily", "erp_name", "intrastat_code", "hs_code",
    "connection", "brand", "weight", "bore_mm", "pressure_max_bar",
    "temp_min_c", "temp_max_c", "series", "material", "dn", "pn",
    "size", "revision",
})

# Prefijos JSONB válidos (el sufijo es la clave dentro del bucket).
JSONB_PREFIXES: frozenset[str] = frozenset({"dimensions", "packaging", "specs"})


@dataclass(frozen=True, slots=True)
class ColumnMappingItem:
    """Mapeo de una columna Excel a un campo de `products`."""

    excel_col: str
    target_field: str  # 'sku' | 'family' | 'dimensions.high_mm' | 'specs.ean_box' | '_skip'
    transform: str     # uno de AVAILABLE_TRANSFORMS
    confidence: float = 1.0
    notes: str = ""


def _is_header_row(row: tuple[Any, ...]) -> bool:
    """Heurística: una fila ES cabecera si tiene ≥3 celdas no-vacías y cortas.

    Descarta filas de título típicas ('PIM CONSOLIDADO...', 'Generado: ...').
    """
    non_empty = [v for v in row if v is not None and str(v).strip()]
    if len(non_empty) < 3:
        return False
    first = str(non_empty[0]).strip()
    # Títulos típicos: una sola celda muy larga con "CONSOLIDADO", "Generado", etc.
    if len(non_empty) <= 2 and len(first) > 60:
        return False
    if first.upper().startswith(("PIM ", "GENERADO", "FUENTE")):
        return False
    # Si la primera celda es un número (fila de datos), no es cabecera.
    try:
        float(first)
        return False
    except ValueError:
        pass
    return True


def detect_header_row(
    xlsx_bytes: bytes,
    max_scan_rows: int = 10,
) -> tuple[int, list[str], list[list[Any]]]:
    """Detecta la fila de cabecera real en cualquier xlsx PIM.

    Itera las primeras `max_scan_rows` filas buscando la primera que tenga
    ≥3 celdas no-vacías y no parezca un título o metadato.

    Returns:
        (header_row_index, headers, sample_data_rows)
        - header_row_index: índice 0-based de la fila de cabecera.
        - headers: lista de nombres de columna (strings).
        - sample_data_rows: lista de hasta 5 filas de datos como listas.
    """
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(xlsx_bytes), read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]

    all_rows: list[tuple[Any, ...]] = []
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i >= max_scan_rows + 5:
            break
        all_rows.append(row)
    wb.close()

    header_idx = 0
    for i, row in enumerate(all_rows[:max_scan_rows]):
        if _is_header_row(row):
            header_idx = i
            break

    headers_raw = all_rows[header_idx]
    headers = [str(v).strip() if v is not None else "" for v in headers_raw]
    # Strip trailing empty headers.
    while headers and not headers[-1]:
        headers.pop()

    # Collect up to 5 non-empty data rows after the header.
    samples: list[list[Any]] = []
    for row in all_rows[header_idx + 1:]:
        if any(v is not None and v != "" for v in row):
            samples.append(list(row))
        if len(samples) >= 5:
            break

    return header_idx, headers, samples
```

- [ ] **Step 1.4: Ejecutar tests**

```bash
python -m pytest tests/unit/importer/test_mapping_detector.py -v
```
Resultado esperado: 3 PASSED

- [ ] **Step 1.5: Commit**

```bash
git add mt-pricing-backend/app/services/importer/mapping_detector.py mt-pricing-backend/tests/unit/importer/test_mapping_detector.py
git commit -m "feat(importer): add detect_header_row — auto-detects real header in xlsx with title rows"
```

---

## Task 2: `mapping_detector.py` — suggest_mapping via LLM

**Files:**
- Modify: `mt-pricing-backend/app/services/importer/mapping_detector.py`
- Test: `mt-pricing-backend/tests/unit/importer/test_mapping_detector.py` (añadir test con mock)

- [ ] **Step 2.1: Añadir test con mock del cliente Anthropic**

```python
# Añadir al final de tests/unit/importer/test_mapping_detector.py
from unittest.mock import MagicMock, patch


def test_suggest_mapping_parses_llm_response():
    """suggest_mapping parsea la respuesta JSON del LLM correctamente."""
    fake_json = json.dumps([
        {"excel_col": "SKU", "target_field": "sku", "transform": "text",
         "confidence": 0.99, "notes": "Código de referencia"},
        {"excel_col": "Familia", "target_field": "family", "transform": "text",
         "confidence": 0.95, "notes": "Familia del producto"},
        {"excel_col": "Peso neto (kg)", "target_field": "weight",
         "transform": "decimal", "confidence": 0.92, "notes": "Peso neto"},
    ])
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text=fake_json)]

    with patch("anthropic.Anthropic") as MockAnthropicCls:
        mock_client = MockAnthropicCls.return_value
        mock_client.messages.create.return_value = mock_message
        from app.services.importer.mapping_detector import suggest_mapping
        result = suggest_mapping(
            headers=["SKU", "Familia", "Peso neto (kg)"],
            sample_rows=[["1010", "Valvulas", 0.5]],
        )

    assert len(result) == 3
    assert result[0].excel_col == "SKU"
    assert result[0].target_field == "sku"
    assert result[0].transform == "text"
    assert result[0].confidence == 0.99


def test_suggest_mapping_falls_back_on_invalid_json():
    """Si el LLM devuelve JSON inválido, retorna mapeo vacío sin lanzar."""
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text="esto no es json")]

    with patch("anthropic.Anthropic") as MockAnthropicCls:
        mock_client = MockAnthropicCls.return_value
        mock_client.messages.create.return_value = mock_message
        from app.services.importer.mapping_detector import suggest_mapping
        result = suggest_mapping(
            headers=["SKU", "Familia"],
            sample_rows=[["1010", "Valvulas"]],
        )

    assert result == []
```

- [ ] **Step 2.2: Ejecutar test para verificar que falla**

```bash
python -m pytest tests/unit/importer/test_mapping_detector.py::test_suggest_mapping_parses_llm_response -v
```
Resultado esperado: `ImportError: cannot import name 'suggest_mapping'`

- [ ] **Step 2.3: Añadir `suggest_mapping` a `mapping_detector.py`**

Añadir al final de `mt-pricing-backend/app/services/importer/mapping_detector.py`:

```python
_LLM_MODEL = "claude-sonnet-4-6"

_AVAILABLE_FIELDS_DOC = """
Scalar fields (products table):
  sku (required), family, erp_name, intrastat_code, hs_code, connection,
  brand, weight, bore_mm, pressure_max_bar, temp_min_c, temp_max_c,
  series, material, dn, pn, size, revision

JSONB sub-fields (dot notation):
  dimensions.high_mm, dimensions.wide_mm, dimensions.deep_mm
  packaging.qty_per_box, packaging.box_high_mm, packaging.box_wide_mm,
  packaging.box_deep_mm, packaging.moq_inner_box, packaging.x_pallet
  specs.<any_key>   ← use for EANs, names, flags, percentages, etc.

Special:
  _skip   ← ignore this column

Available transforms:
  text        plain text / string
  int         integer number
  decimal     decimal / float
  cm_to_mm    multiply × 10 (centimeters → millimeters)
  ean         EAN barcode (digits only, valid lengths 8/12/13/14)
  bool_check  truthy check: "✓", "yes", "1", "true" → true; else false
  percent     numeric percentage stored as integer 0–100
"""


def suggest_mapping(
    headers: list[str],
    sample_rows: list[list[Any]],
) -> list[ColumnMappingItem]:
    """Llama a Claude para proponer el mapeo de columnas Excel → campos product.

    Devuelve lista vacía si el LLM falla o devuelve JSON inválido (tolerante).
    """
    import anthropic

    samples_text = "\n".join(
        f"  Row {i + 1}: " + ", ".join(
            f"{h}={repr(row[j]) if j < len(row) else None}"
            for j, h in enumerate(headers[:10])  # primeras 10 cols para no saturar
        )
        for i, row in enumerate(sample_rows[:3])
    )

    prompt = (
        f"You are a product data mapping assistant for an industrial PVF "
        f"(pipes, valves, fittings) manufacturer PIM system.\n\n"
        f"Given these Excel column headers and sample data, propose the best "
        f"mapping from each Excel column to a product database field.\n\n"
        f"{_AVAILABLE_FIELDS_DOC}\n\n"
        f"Excel headers: {headers}\n\n"
        f"Sample data (first 3 rows):\n{samples_text}\n\n"
        f"Return a JSON array — no markdown, no explanation, just JSON. "
        f"Each element:\n"
        f'  {{"excel_col": "<exact header>", "target_field": "<field>", '
        f'"transform": "<transform>", "confidence": 0.0-1.0, '
        f'"notes": "<1-sentence Spanish explanation>"}}\n\n'
        f"Include ALL {len(headers)} columns, even those mapped to _skip."
    )

    try:
        client = anthropic.Anthropic()
        message = client.messages.create(
            model=_LLM_MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        text = message.content[0].text.strip()
        # Strip possible markdown code fence.
        if text.startswith("```"):
            text = "\n".join(
                line for line in text.splitlines()
                if not line.startswith("```")
            ).strip()
        data = json.loads(text)
        return [
            ColumnMappingItem(
                excel_col=item["excel_col"],
                target_field=item.get("target_field", "_skip"),
                transform=item.get("transform", "text"),
                confidence=float(item.get("confidence", 0.5)),
                notes=item.get("notes", ""),
            )
            for item in data
            if isinstance(item, dict) and "excel_col" in item
        ]
    except Exception:  # noqa: BLE001
        logger.exception("suggest_mapping LLM call failed — returning empty mapping")
        return []
```

- [ ] **Step 2.4: Ejecutar todos los tests del módulo**

```bash
python -m pytest tests/unit/importer/test_mapping_detector.py -v
```
Resultado esperado: 5 PASSED

- [ ] **Step 2.5: Commit**

```bash
git add mt-pricing-backend/app/services/importer/mapping_detector.py mt-pricing-backend/tests/unit/importer/test_mapping_detector.py
git commit -m "feat(importer): add suggest_mapping — LLM-based column→field proposal via Claude"
```

---

## Task 3: `column_mapper.py` — map_row_with_mapping (flexible)

**Files:**
- Modify: `mt-pricing-backend/app/services/importer/column_mapper.py`
- Test: `mt-pricing-backend/tests/unit/importer/test_column_mapper_flexible.py`

- [ ] **Step 3.1: Escribir test que falla**

```python
# mt-pricing-backend/tests/unit/importer/test_column_mapper_flexible.py
"""Tests para map_row_with_mapping (mapeo flexible)."""
from __future__ import annotations

from decimal import Decimal

from app.services.importer.column_mapper import map_row_with_mapping
from app.services.importer.mapping_detector import ColumnMappingItem


def _mapping(*items: tuple[str, str, str]) -> list[ColumnMappingItem]:
    return [ColumnMappingItem(excel_col=e, target_field=t, transform=tr)
            for e, t, tr in items]


def test_maps_scalar_fields():
    headers = ["SKU", "Familia", "Peso neto (kg)"]
    row = ("1010", "Valvulas", 0.5)
    mapping = _mapping(
        ("SKU", "sku", "text"),
        ("Familia", "family", "text"),
        ("Peso neto (kg)", "weight", "decimal"),
    )
    payload, errors = map_row_with_mapping(row, headers, mapping)
    assert payload["sku"] == "1010"
    assert payload["family"] == "Valvulas"
    assert payload["weight"] == Decimal("0.5")
    assert errors == []


def test_maps_jsonb_dimensions_with_cm_to_mm():
    headers = ["SKU", "Alto pieza (cm)", "Ancho pieza (cm)"]
    row = ("1010", 10.5, 5.0)
    mapping = _mapping(
        ("SKU", "sku", "text"),
        ("Alto pieza (cm)", "dimensions.high_mm", "cm_to_mm"),
        ("Ancho pieza (cm)", "dimensions.wide_mm", "cm_to_mm"),
    )
    payload, errors = map_row_with_mapping(row, headers, mapping)
    assert payload["dimensions"]["high_mm"] == Decimal("105.0")
    assert payload["dimensions"]["wide_mm"] == Decimal("50.0")


def test_maps_specs_arbitrary_key():
    headers = ["SKU", "EAN unidad"]
    row = ("1010", "1234567890123")
    mapping = _mapping(
        ("SKU", "sku", "text"),
        ("EAN unidad", "specs.ean_individual", "ean"),
    )
    payload, errors = map_row_with_mapping(row, headers, mapping)
    assert payload["specs"]["ean_individual"] == "1234567890123"


def test_skip_columns_are_ignored():
    headers = ["SKU", "Completitud %", "En PIM"]
    row = ("1010", 40, "✓")
    mapping = _mapping(
        ("SKU", "sku", "text"),
        ("Completitud %", "_skip", "text"),
        ("En PIM", "specs.en_pim", "bool_check"),
    )
    payload, errors = map_row_with_mapping(row, headers, mapping)
    assert "Completitud %" not in str(payload)
    assert payload["specs"]["en_pim"] is True


def test_bool_check_transform():
    headers = ["SKU", "En PIM"]
    mapping = _mapping(
        ("SKU", "sku", "text"),
        ("En PIM", "specs.en_pim", "bool_check"),
    )
    for val, expected in [("✓", True), ("yes", True), ("1", True), (None, False), ("", False)]:
        row = ("1010", val)
        payload, _ = map_row_with_mapping(row, headers, mapping)
        assert payload["specs"]["en_pim"] is expected, f"val={val!r}"


def test_percent_transform():
    headers = ["SKU", "Completitud %"]
    row = ("1010", 40)
    mapping = _mapping(
        ("SKU", "sku", "text"),
        ("Completitud %", "specs.completitud_pct", "percent"),
    )
    payload, errors = map_row_with_mapping(row, headers, mapping)
    assert payload["specs"]["completitud_pct"] == 40
    assert errors == []
```

- [ ] **Step 3.2: Ejecutar test para verificar que falla**

```bash
python -m pytest tests/unit/importer/test_column_mapper_flexible.py -v
```
Resultado esperado: `ImportError: cannot import name 'map_row_with_mapping'`

- [ ] **Step 3.3: Añadir `map_row_with_mapping` a `column_mapper.py`**

Añadir al final de `mt-pricing-backend/app/services/importer/column_mapper.py` (después de la función `map_row` existente):

```python
def _cast_bool_check(v: Any) -> bool:
    """'✓', 'yes', '1', 'true' → True. Todo lo demás → False."""
    if v is None or v == "":
        return False
    s = str(v).strip().lower()
    return s in ("✓", "yes", "si", "sí", "1", "true", "x")


def _cast_percent(v: Any) -> int | None:
    """Porcentaje numérico → int 0-100."""
    if v is None or v == "":
        return None
    try:
        n = int(float(str(v).strip()))
        return max(0, min(100, n))
    except (ValueError, TypeError):
        raise ImportCastError(f"Valor no convertible a porcentaje: {v!r}")


# Registrar los nuevos casters.
CASTERS["bool_check"] = _cast_bool_check
CASTERS["percent"] = _cast_percent


def map_row_with_mapping(
    excel_row: tuple[Any, ...] | list[Any],
    headers: list[str],
    mapping: "list[Any]",  # list[ColumnMappingItem] — import lazy para evitar ciclos
) -> tuple[dict[str, Any], list[str]]:
    """Mapea una fila usando un mapping flexible (lista de ColumnMappingItem).

    A diferencia de `map_row`, no valida contra EXPECTED_HEADERS — usa la lista
    de ColumnMappingItem que el usuario confirmó tras el paso de análisis LLM.

    target_field conventions:
    - ``sku``, ``family``, ``weight``, etc. → campo escalar directo en products.
    - ``dimensions.high_mm``, ``packaging.qty_per_box``, ``specs.ean_box`` →
      clave dentro del bucket JSONB correspondiente.
    - ``_skip`` → ignorar columna.

    Returns: (payload_dict, errors_list).
    """
    col_index: dict[str, int] = {h: i for i, h in enumerate(headers)}
    payload: dict[str, Any] = dict(ROW_DEFAULTS)
    errors: list[str] = []
    jsonb_buckets: dict[str, dict[str, Any]] = {
        "dimensions": {},
        "packaging": {},
        "specs": {},
    }

    for item in mapping:
        if item.target_field == "_skip":
            continue

        idx = col_index.get(item.excel_col)
        if idx is None or idx >= len(excel_row):
            continue

        raw = excel_row[idx]
        caster = CASTERS.get(item.transform, _cast_text)
        try:
            casted = caster(raw)
        except ImportCastError as exc:
            errors.append(f"col {item.excel_col!r}: {exc}")
            continue

        if casted is None:
            continue

        field = item.target_field

        if "." in field:
            prefix, key = field.split(".", 1)
            if prefix in jsonb_buckets:
                value: Any = str(casted) if isinstance(casted, Decimal) else casted
                jsonb_buckets[prefix][key] = value
            # Si el prefijo no es un bucket conocido, se ignora silenciosamente.
        else:
            payload[field] = casted

    for k, v in jsonb_buckets.items():
        if v:
            payload[k] = v

    return payload, errors
```

También añadir al `__all__` del módulo (al final o en los imports de `column_mapper.py`):
```python
__all__ = [
    "ColumnSpec", "ImportCastError", "EXCEL_COL_TO_FIELD", "EXPECTED_HEADERS",
    "ROW_DEFAULTS", "CASTERS", "map_row", "map_row_with_mapping",
]
```

- [ ] **Step 3.4: Ejecutar tests**

```bash
python -m pytest tests/unit/importer/test_column_mapper_flexible.py -v
```
Resultado esperado: todos PASSED

- [ ] **Step 3.5: Commit**

```bash
git add mt-pricing-backend/app/services/importer/column_mapper.py mt-pricing-backend/tests/unit/importer/test_column_mapper_flexible.py
git commit -m "feat(importer): add map_row_with_mapping — flexible column mapping with bool_check + percent transforms"
```

---

## Task 4: `parser.py` — soporte `header_row_index` + `custom_mapping`

**Files:**
- Modify: `mt-pricing-backend/app/services/importer/parser.py`
- Test: `mt-pricing-backend/tests/unit/importer/test_parser_custom_mapping.py`

- [ ] **Step 4.1: Escribir tests que fallan**

```python
# mt-pricing-backend/tests/unit/importer/test_parser_custom_mapping.py
"""Tests: parse_xlsx_stream con header_row_index y custom_mapping."""
from __future__ import annotations

import io
import openpyxl

from app.services.importer.column_mapper import map_row_with_mapping
from app.services.importer.mapping_detector import ColumnMappingItem
from app.services.importer.parser import parse_xlsx_stream


def _make_xlsx(rows: list[list]) -> io.BytesIO:
    wb = openpyxl.Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def test_parse_with_header_row_index_skips_title_rows():
    """header_row_index=2 salta 2 filas de título."""
    xlsx = _make_xlsx([
        ["PIM CONSOLIDADO"] + [None] * 2,
        ["Generado: 2026-05-13"] + [None] * 2,
        ["SKU", "Familia", "Peso neto (kg)"],
        ["1010", "Valvulas", 0.5],
        ["3015", "Accesorios", 1.2],
    ])
    mapping = [
        ColumnMappingItem("SKU", "sku", "text"),
        ColumnMappingItem("Familia", "family", "text"),
        ColumnMappingItem("Peso neto (kg)", "weight", "decimal"),
    ]
    result = parse_xlsx_stream(xlsx, header_row_index=2, custom_mapping=mapping)
    assert result.header_ok
    assert result.total_data_rows == 2
    assert result.rows[0].sku == "1010"
    assert result.rows[1].sku == "3015"


def test_parse_with_custom_mapping_no_header_validation():
    """Con custom_mapping, no valida contra EXPECTED_HEADERS."""
    xlsx = _make_xlsx([
        ["SKU", "Nueva Columna Inventada", "Familia"],
        ["1010", "valor_x", "Valvulas"],
    ])
    mapping = [
        ColumnMappingItem("SKU", "sku", "text"),
        ColumnMappingItem("Nueva Columna Inventada", "specs.nueva_col", "text"),
        ColumnMappingItem("Familia", "family", "text"),
    ]
    result = parse_xlsx_stream(xlsx, custom_mapping=mapping)
    assert result.header_ok
    assert result.rows[0].sku == "1010"
    assert result.rows[0].payload["specs"]["nueva_col"] == "valor_x"


def test_parse_without_custom_mapping_uses_old_validation():
    """Sin custom_mapping, sigue usando EXPECTED_HEADERS (backward compat)."""
    xlsx = _make_xlsx([
        ["SKU_DESCONOCIDO", "Otra Columna"],
        ["1010", "valor"],
    ])
    result = parse_xlsx_stream(xlsx)  # sin custom_mapping
    # Debe fallar la validación del header (no coincide con EXPECTED_HEADERS).
    assert not result.header_ok
    assert len(result.header_errors) > 0
```

- [ ] **Step 4.2: Ejecutar tests para verificar que fallan**

```bash
python -m pytest tests/unit/importer/test_parser_custom_mapping.py -v
```
Resultado esperado: fallo por `TypeError` (parámetros no existen aún).

- [ ] **Step 4.3: Modificar `parse_xlsx_stream` en `parser.py`**

Reemplazar la firma y el cuerpo de `parse_xlsx_stream` con la versión extendida. El archivo completo queda así:

```python
"""Parser openpyxl streaming para PIM completo.xlsx (US-1A-06-01).

Diseño:
- ``read_only=True`` + ``data_only=True`` → no carga las 5k filas en RAM.
- Sin custom_mapping: verifica header exacto contra :data:`EXPECTED_HEADERS`.
- Con custom_mapping: salta header_row_index filas, usa map_row_with_mapping.
- Detecta SKUs duplicados dentro del archivo (BR-1a-PIM-DUP).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, BinaryIO

from app.services.importer.column_mapper import EXPECTED_HEADERS, map_row, map_row_with_mapping

if TYPE_CHECKING:
    from app.services.importer.mapping_detector import ColumnMappingItem


@dataclass(slots=True)
class ParsedRow:
    """Una fila parseada del PIM."""

    row_index: int
    sku: str | None
    payload: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors and self.sku is not None


@dataclass(slots=True)
class ParseResult:
    """Resultado completo del parse."""

    rows: list[ParsedRow]
    header_errors: list[str]
    total_data_rows: int
    duplicate_skus: list[str]

    @property
    def header_ok(self) -> bool:
        return not self.header_errors


class HeaderMismatchError(ValueError):
    """El header del archivo no coincide con :data:`EXPECTED_HEADERS`."""


def _validate_header(header: tuple[Any, ...]) -> list[str]:
    errors: list[str] = []
    if len(header) < len(EXPECTED_HEADERS):
        errors.append(
            f"Archivo con {len(header)} columnas; esperadas {len(EXPECTED_HEADERS)}."
        )
        return errors
    for i, expected in enumerate(EXPECTED_HEADERS):
        actual = header[i]
        actual_str = (str(actual) if actual is not None else "").strip()
        if actual_str != expected:
            errors.append(
                f"col {i}: header esperado {expected!r}, recibido {actual_str!r}."
            )
    return errors


def parse_xlsx_stream(
    source: str | Path | BinaryIO,
    *,
    sheet_name: str | None = None,
    max_rows: int | None = None,
    header_row_index: int | None = None,
    custom_mapping: "list[ColumnMappingItem] | None" = None,
) -> ParseResult:
    """Parsea un xlsx PIM completo con openpyxl streaming.

    Args:
        source: path o file-like binario.
        sheet_name: nombre de sheet (default: la primera).
        max_rows: límite de filas de datos a procesar (None = todas).
        header_row_index: si se provee, salta esas filas antes de leer
            el header. Útil cuando el xlsx tiene filas de título/metadatos.
        custom_mapping: lista de ColumnMappingItem. Si se provee, salta la
            validación de EXPECTED_HEADERS y usa map_row_with_mapping en
            lugar de map_row. header_row_index debe también proveerse si
            el xlsx tiene filas de título.
    """
    from openpyxl import load_workbook

    wb = load_workbook(source, read_only=True, data_only=True)
    try:
        sh = wb[sheet_name] if sheet_name else wb[wb.sheetnames[0]]
        rows_iter: Iterator[tuple[Any, ...]] = sh.iter_rows(values_only=True)

        # Saltar filas de título/metadatos si se especifica.
        if header_row_index:
            for _ in range(header_row_index):
                try:
                    next(rows_iter)
                except StopIteration:
                    return ParseResult(
                        rows=[],
                        header_errors=[f"header_row_index={header_row_index} excede las filas del archivo."],
                        total_data_rows=0,
                        duplicate_skus=[],
                    )

        # Leer fila de cabecera.
        try:
            header = next(rows_iter)
        except StopIteration:
            return ParseResult(
                rows=[],
                header_errors=["Archivo vacío (sin header)."],
                total_data_rows=0,
                duplicate_skus=[],
            )

        # Validación de header (sólo si no hay custom_mapping).
        if custom_mapping is None:
            header_errors = _validate_header(header)
            if header_errors:
                return ParseResult(
                    rows=[], header_errors=header_errors,
                    total_data_rows=0, duplicate_skus=[]
                )

        headers_list = [str(v).strip() if v is not None else "" for v in header]

        rows: list[ParsedRow] = []
        seen: dict[str, int] = {}
        duplicates: list[str] = []

        for i, row in enumerate(rows_iter, start=1):
            if max_rows is not None and i > max_rows:
                break
            if all(v is None or v == "" for v in row):
                continue

            if custom_mapping is not None:
                payload, errors = map_row_with_mapping(row, headers_list, custom_mapping)
            else:
                payload, errors = map_row(row, EXPECTED_HEADERS)

            sku = payload.get("sku")
            if sku is not None:
                if sku in seen:
                    duplicates.append(sku)
                    errors.append(
                        f"SKU duplicado en archivo (primera ocurrencia row {seen[sku]})."
                    )
                else:
                    seen[sku] = i

            rows.append(ParsedRow(row_index=i, sku=sku, payload=payload, errors=errors))

        return ParseResult(
            rows=rows,
            header_errors=[],
            total_data_rows=len(rows),
            duplicate_skus=duplicates,
        )
    finally:
        wb.close()
```

- [ ] **Step 4.4: Ejecutar todos los tests del parser**

```bash
python -m pytest tests/unit/importer/test_parser_custom_mapping.py tests/integration/test_pim_importer.py -v
```
Resultado esperado: todos PASSED (los tests de integración no deben romperse).

- [ ] **Step 4.5: Commit**

```bash
git add mt-pricing-backend/app/services/importer/parser.py mt-pricing-backend/tests/unit/importer/test_parser_custom_mapping.py
git commit -m "feat(importer): parser.parse_xlsx_stream accepts header_row_index + custom_mapping"
```

---

## Task 5: Schemas + endpoint `POST /imports/analyze`

**Files:**
- Modify: `mt-pricing-backend/app/schemas/importer.py`
- Modify: `mt-pricing-backend/app/api/routes/imports.py`
- Modify: `mt-pricing-backend/app/services/importer/importer_service.py`

- [ ] **Step 5.1: Añadir schemas a `app/schemas/importer.py`**

Añadir al final del archivo (después de `ImportRunStatusResponse`):

```python
class ColumnMappingItemSchema(BaseModel):
    """Un ítem del mapeo columna Excel → campo product."""

    model_config = ConfigDict(extra="ignore")

    excel_col: str
    target_field: str
    transform: str = "text"
    confidence: float = 1.0
    notes: str = ""


class AnalyzeImportResponse(BaseModel):
    """Respuesta del endpoint POST /imports/analyze."""

    model_config = ConfigDict(extra="ignore")

    filename: str
    detected_header_row: int
    headers: list[str]
    sample_rows: list[list[str | None]]
    proposed_mapping: list[ColumnMappingItemSchema]
```

- [ ] **Step 5.2: Añadir `POST /imports/analyze` a `routes/imports.py`**

Añadir ANTES del endpoint `/preview` existente (línea ~90 del archivo):

```python
@router.post(
    "/analyze",
    response_model=AnalyzeImportResponse,
    summary="Detectar estructura del xlsx y proponer mapeo via LLM",
    responses={
        413: {"model": ProblemDetails, "description": "Archivo demasiado grande"},
        422: {"model": ProblemDetails, "description": "No se pudo detectar cabecera"},
    },
)
async def analyze_import(
    file: Annotated[UploadFile, File(description="xlsx PIM (≤ 50 MB)")],
    _user: Annotated[User, Depends(require_permissions("imports:write"))],
) -> AnalyzeImportResponse:
    """Detecta la fila de cabecera real del xlsx y propone el mapeo de columnas
    via Claude. El frontend usa esta respuesta para mostrar el paso 'Mapeo'.
    """
    if file.filename is None:
        raise HTTPException(
            status_code=422,
            detail={"code": "import_missing_filename", "title": "filename requerido"},
        )
    file_bytes = await file.read()
    if len(file_bytes) > 50 * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail={"code": "import_file_too_large", "title": "Archivo excede 50 MB"},
        )

    from app.services.importer.mapping_detector import detect_header_row, suggest_mapping
    from app.schemas.importer import ColumnMappingItemSchema

    try:
        header_idx, headers, samples = detect_header_row(file_bytes)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=422,
            detail={"code": "import_header_detection_failed", "title": str(exc)},
        ) from exc

    proposed = suggest_mapping(headers, samples)
    sample_rows_safe = [
        [str(v) if v is not None else None for v in row]
        for row in samples
    ]

    return AnalyzeImportResponse(
        filename=file.filename,
        detected_header_row=header_idx,
        headers=headers,
        sample_rows=sample_rows_safe,
        proposed_mapping=[
            ColumnMappingItemSchema(
                excel_col=m.excel_col,
                target_field=m.target_field,
                transform=m.transform,
                confidence=m.confidence,
                notes=m.notes,
            )
            for m in proposed
        ],
    )
```

Añadir también a los imports del archivo:
```python
from app.schemas.importer import (
    AnalyzeImportResponse,
    ColumnMappingItemSchema,
    ImportApplyRequest,
    ImportPreviewResponse,
    ImportRunStatusResponse,
    ImportRunSummary,
)
```

- [ ] **Step 5.3: Modificar `preview_import` para aceptar mapping opcional**

En `routes/imports.py`, modificar la firma del endpoint `preview_import` añadiendo el parámetro `mapping_json`:

```python
@router.post("/preview", ...)
async def preview_import(
    file: Annotated[UploadFile, File(description="xlsx PIM (≤ 50 MB)")],
    user: Annotated[User, Depends(require_permissions("imports:write"))],
    service: Annotated[ImporterService, Depends(get_importer_service)],
    type_: Annotated[str, Query(alias="type", pattern=r"^(pim)$")] = "pim",
    mapping_json: Annotated[str | None, Form()] = None,  # ← NUEVO
) -> ImportPreviewResponse:
```

Y en el cuerpo del endpoint, antes de llamar a `service.preview`, añadir:

```python
    # Parsear mapping confirmado (si viene del paso de mapeo LLM).
    custom_mapping = None
    if mapping_json:
        import json as _json
        from app.services.importer.mapping_detector import ColumnMappingItem as _CMI
        try:
            raw_mapping = _json.loads(mapping_json)
            custom_mapping = [
                _CMI(
                    excel_col=m["excel_col"],
                    target_field=m["target_field"],
                    transform=m.get("transform", "text"),
                    confidence=float(m.get("confidence", 1.0)),
                    notes=m.get("notes", ""),
                )
                for m in raw_mapping
                if isinstance(m, dict) and "excel_col" in m
            ]
        except Exception:  # noqa: BLE001
            raise HTTPException(
                status_code=422,
                detail={"code": "import_invalid_mapping", "title": "mapping_json inválido"},
            )
```

Y cambiar la llamada a `service.preview`:
```python
        state = await service.preview(
            file_bytes=file_bytes,
            filename=file.filename,
            actor=user,
            type_=type_,
            custom_mapping=custom_mapping,  # ← NUEVO
        )
```

- [ ] **Step 5.4: Modificar `ImporterService.preview` para aceptar `custom_mapping`**

En `mt-pricing-backend/app/services/importer/importer_service.py`, cambiar la firma y el cuerpo de `preview`:

```python
    async def preview(
        self,
        *,
        file_bytes: bytes,
        filename: str,
        actor: User,
        type_: str = "pim",
        custom_mapping: "list[Any] | None" = None,  # ← NUEVO (list[ColumnMappingItem])
    ) -> ImportRunState:
        if len(file_bytes) > MAX_FILE_SIZE_BYTES:
            raise ImportFileTooLargeError(len(file_bytes), MAX_FILE_SIZE_BYTES)

        bio: BinaryIO = io.BytesIO(file_bytes)
        try:
            if custom_mapping is not None:
                # Con mapping LLM: detectar fila de cabecera y usar mapeo flexible.
                from app.services.importer.mapping_detector import detect_header_row
                header_idx, _headers, _samples = detect_header_row(file_bytes)
                bio.seek(0)
                parse_result = parse_xlsx_stream(
                    bio,
                    header_row_index=header_idx,
                    custom_mapping=custom_mapping,
                )
            else:
                parse_result = parse_xlsx_stream(bio)
        except Exception as exc:  # noqa: BLE001
            raise ImporterDomainError(
                code="import_parse_failed",
                message=f"Error parseando archivo: {exc}",
                status_code=422,
            ) from exc

        if not parse_result.header_ok:
            raise ImportHeaderMismatchError(parse_result.header_errors)

        # ... resto del método sin cambios ...
```

- [ ] **Step 5.5: Verificar que el backend arranca**

```bash
docker restart mt-backend
sleep 3
curl -s http://localhost:8081/health/live | python -c "import sys,json; d=json.load(sys.stdin); print('OK' if d.get('status')=='ok' else 'FAIL')"
```
Resultado esperado: `OK`

- [ ] **Step 5.6: Commit**

```bash
git add mt-pricing-backend/app/schemas/importer.py mt-pricing-backend/app/api/routes/imports.py mt-pricing-backend/app/services/importer/importer_service.py
git commit -m "feat(imports): add POST /imports/analyze endpoint + wire custom_mapping through preview"
```

---

## Task 6: Frontend — tipos + API analyze

**Files:**
- Modify: `mt-pricing-frontend/lib/api/endpoints/imports.ts`
- Modify: `mt-pricing-frontend/lib/hooks/imports/use-imports.ts`

- [ ] **Step 6.1: Añadir tipos y función `analyze` a `imports.ts`**

Añadir después de la interfaz `ImportReport` (línea ~88):

```typescript
// ---- Analyze / mapping types -----------------------------------------------

export interface ColumnMappingItem {
  excel_col: string;
  target_field: string;
  transform: string;
  confidence: number;
  notes?: string;
}

export interface AnalyzeImportResponse {
  filename: string;
  detected_header_row: number;
  headers: string[];
  /** Hasta 5 filas de datos de muestra (valores como string|null). */
  sample_rows: (string | null)[][];
  proposed_mapping: ColumnMappingItem[];
}
```

Añadir `analyze` al objeto `importsApi` (dentro del bloque, después de `getPreview`):

```typescript
  /** Detecta estructura del xlsx y propone mapeo de columnas via LLM. */
  analyze: (file: File): Promise<AnalyzeImportResponse> => {
    const fd = new FormData();
    fd.append("file", file);
    return authedFetch<AnalyzeImportResponse>(`/api/v1/imports/analyze`, {
      method: "POST",
      body: fd,
    });
  },
```

Modificar `preview` para aceptar mapping opcional:

```typescript
  preview: (
    file: File,
    type: "pim" = "pim",
    mapping?: ColumnMappingItem[],
  ): Promise<ImportPreview> => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("type", type);
    if (mapping) fd.append("mapping", JSON.stringify(mapping));
    return authedFetch<ImportPreview>(`/api/v1/imports/preview`, {
      method: "POST",
      body: fd,
    });
  },
```

- [ ] **Step 6.2: Añadir `useAnalyzeImport` a `use-imports.ts`**

Añadir después de `useUploadImport`:

```typescript
/** Mutación: analizar xlsx — detecta estructura + propone mapeo via LLM. */
export function useAnalyzeImport() {
  return useMutation<AnalyzeImportResponse, Error, { file: File }>({
    mutationFn: ({ file }) => importsApi.analyze(file),
  });
}
```

Asegurarse de importar el tipo:
```typescript
import {
  NON_TERMINAL_STATUSES,
  importsApi,
  type AnalyzeImportResponse,
  type ImportPreview,
  type ImportReport,
  type ImportRun,
} from "@/lib/api/endpoints/imports";
```

- [ ] **Step 6.3: Verificar TypeScript compila**

```bash
cd mt-pricing-frontend && npx tsc --noEmit 2>&1 | head -20
```
Resultado esperado: sin errores.

- [ ] **Step 6.4: Commit**

```bash
git add mt-pricing-frontend/lib/api/endpoints/imports.ts mt-pricing-frontend/lib/hooks/imports/use-imports.ts
git commit -m "feat(frontend/imports): add AnalyzeImportResponse types + importsApi.analyze + useAnalyzeImport"
```

---

## Task 7: Frontend — componente `MappingStep`

**Files:**
- Create: `mt-pricing-frontend/app/(app)/imports/_components/mapping-step.tsx`

- [ ] **Step 7.1: Crear el componente**

```tsx
// mt-pricing-frontend/app/(app)/imports/_components/mapping-step.tsx
"use client";

import * as React from "react";
import { useTranslations } from "next-intl";
import { Check, ChevronDown, AlertCircle } from "lucide-react";
import {
  type AnalyzeImportResponse,
  type ColumnMappingItem,
} from "@/lib/api/endpoints/imports";
import { cn } from "@/lib/utils/cn";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

// Campos target disponibles (ordenados por frecuencia de uso).
const TARGET_FIELDS = [
  { value: "_skip", label: "— Ignorar columna —" },
  { value: "sku", label: "sku (clave primaria)" },
  { value: "family", label: "family" },
  { value: "erp_name", label: "erp_name" },
  { value: "hs_code", label: "hs_code" },
  { value: "intrastat_code", label: "intrastat_code" },
  { value: "connection", label: "connection" },
  { value: "brand", label: "brand" },
  { value: "weight", label: "weight (kg)" },
  { value: "bore_mm", label: "bore_mm" },
  { value: "pressure_max_bar", label: "pressure_max_bar" },
  { value: "temp_min_c", label: "temp_min_c" },
  { value: "temp_max_c", label: "temp_max_c" },
  { value: "dimensions.high_mm", label: "dimensions.high_mm" },
  { value: "dimensions.wide_mm", label: "dimensions.wide_mm" },
  { value: "dimensions.deep_mm", label: "dimensions.deep_mm" },
  { value: "packaging.qty_per_box", label: "packaging.qty_per_box" },
  { value: "packaging.box_high_mm", label: "packaging.box_high_mm" },
  { value: "packaging.box_wide_mm", label: "packaging.box_wide_mm" },
  { value: "packaging.box_deep_mm", label: "packaging.box_deep_mm" },
  { value: "packaging.moq_inner_box", label: "packaging.moq_inner_box" },
  { value: "packaging.x_pallet", label: "packaging.x_pallet" },
  { value: "specs.ean_individual", label: "specs.ean_individual" },
  { value: "specs.ean_box", label: "specs.ean_box" },
  { value: "specs.ean_inner_box", label: "specs.ean_inner_box" },
  { value: "specs.name_en", label: "specs.name_en" },
  { value: "specs.name_es", label: "specs.name_es" },
  { value: "specs.name_fr", label: "specs.name_fr" },
  { value: "specs.name_de", label: "specs.name_de" },
  { value: "specs.image_url", label: "specs.image_url" },
  { value: "specs.standards", label: "specs.standards" },
  { value: "specs.certifications", label: "specs.certifications" },
  { value: "specs.series_tags", label: "specs.series_tags" },
  { value: "specs.material_category", label: "specs.material_category" },
  { value: "specs.family_type", label: "specs.family_type" },
  { value: "specs.en_pim", label: "specs.en_pim" },
  { value: "specs.en_catalogo", label: "specs.en_catalogo" },
  { value: "specs.completitud_pct", label: "specs.completitud_pct" },
  { value: "specs.salidas", label: "specs.salidas" },
  { value: "specs.catalog_page", label: "specs.catalog_page" },
];

const TRANSFORMS = [
  { value: "text", label: "text" },
  { value: "int", label: "int" },
  { value: "decimal", label: "decimal" },
  { value: "cm_to_mm", label: "cm → mm (×10)" },
  { value: "ean", label: "ean (barcode)" },
  { value: "bool_check", label: "bool (✓/yes)" },
  { value: "percent", label: "percent (0–100)" },
];

interface Props {
  analysis: AnalyzeImportResponse;
  onBack: () => void;
  onConfirm: (mapping: ColumnMappingItem[]) => void;
  isLoading?: boolean;
}

export function MappingStep({ analysis, onBack, onConfirm, isLoading }: Props) {
  const t = useTranslations("imports.mapping");
  const [mapping, setMapping] = React.useState<ColumnMappingItem[]>(
    () => [...analysis.proposed_mapping],
  );

  const updateItem = (idx: number, patch: Partial<ColumnMappingItem>) => {
    setMapping((prev) =>
      prev.map((item, i) => (i === idx ? { ...item, ...patch } : item)),
    );
  };

  const skuMapped = mapping.some(
    (m) => m.target_field === "sku" && m.excel_col,
  );

  const firstSampleRow = analysis.sample_rows[0] ?? [];
  const headerIndex: Record<string, number> = {};
  analysis.headers.forEach((h, i) => {
    headerIndex[h] = i;
  });

  return (
    <div className="space-y-4" data-testid="mapping-step">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-muted-foreground">
            {t("subtitle", { cols: analysis.headers.length, row: analysis.detected_header_row + 1 })}
          </p>
        </div>
        {!skuMapped && (
          <div className="flex items-center gap-1 text-xs text-destructive">
            <AlertCircle className="h-3 w-3" />
            {t("skuRequired")}
          </div>
        )}
      </div>

      <div className="rounded-md border overflow-auto max-h-[60vh]">
        <table className="w-full text-xs">
          <thead className="sticky top-0 bg-muted/80 backdrop-blur">
            <tr>
              <th className="px-3 py-2 text-left font-medium">{t("colExcel")}</th>
              <th className="px-3 py-2 text-left font-medium">{t("colSample")}</th>
              <th className="px-3 py-2 text-left font-medium">{t("colTarget")}</th>
              <th className="px-3 py-2 text-left font-medium">{t("colTransform")}</th>
              <th className="px-3 py-2 text-left font-medium">{t("colConfidence")}</th>
            </tr>
          </thead>
          <tbody>
            {mapping.map((item, idx) => {
              const sampleVal = firstSampleRow[headerIndex[item.excel_col] ?? -1];
              const isSkip = item.target_field === "_skip";
              return (
                <tr
                  key={item.excel_col}
                  className={cn(
                    "border-t transition-colors",
                    isSkip ? "opacity-50" : "hover:bg-muted/30",
                  )}
                >
                  <td className="px-3 py-1.5 font-mono">{item.excel_col}</td>
                  <td className="px-3 py-1.5 text-muted-foreground max-w-[120px] truncate">
                    {sampleVal ?? "—"}
                  </td>
                  <td className="px-3 py-1.5 min-w-[200px]">
                    <Select
                      value={item.target_field}
                      onValueChange={(v) => updateItem(idx, { target_field: v })}
                    >
                      <SelectTrigger className="h-7 text-xs">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {TARGET_FIELDS.map((f) => (
                          <SelectItem key={f.value} value={f.value} className="text-xs">
                            {f.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </td>
                  <td className="px-3 py-1.5 min-w-[140px]">
                    <Select
                      value={item.transform}
                      onValueChange={(v) => updateItem(idx, { transform: v })}
                      disabled={isSkip}
                    >
                      <SelectTrigger className="h-7 text-xs">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {TRANSFORMS.map((tr) => (
                          <SelectItem key={tr.value} value={tr.value} className="text-xs">
                            {tr.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </td>
                  <td className="px-3 py-1.5">
                    <Badge
                      variant={item.confidence >= 0.85 ? "default" : "secondary"}
                      className="text-[10px]"
                    >
                      {Math.round(item.confidence * 100)}%
                    </Badge>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="flex justify-between">
        <Button variant="outline" onClick={onBack} disabled={isLoading}>
          {t("back")}
        </Button>
        <Button
          onClick={() => onConfirm(mapping)}
          disabled={!skuMapped || isLoading}
        >
          {isLoading ? t("loading") : t("confirm")}
        </Button>
      </div>
    </div>
  );
}
```

- [ ] **Step 7.2: Commit**

```bash
git add "mt-pricing-frontend/app/(app)/imports/_components/mapping-step.tsx"
git commit -m "feat(frontend/imports): add MappingStep component for LLM mapping review"
```

---

## Task 8: Frontend — integrar MappingStep en el wizard

**Files:**
- Modify: `mt-pricing-frontend/app/(app)/imports/_components/import-wizard.tsx`
- Modify: `mt-pricing-frontend/app/(app)/imports/_components/upload-step.tsx`

- [ ] **Step 8.1: Modificar `upload-step.tsx` para llamar a analyze en lugar de preview directamente**

El `UploadStep` actualmente llama `useUploadImport` (que hace preview). Ahora debe llamar `useAnalyzeImport`.

En `upload-step.tsx`, cambiar:
```typescript
import { useUploadImport } from "@/lib/hooks/imports/use-imports";
import type { ImportPreview } from "@/lib/api/endpoints/imports";

interface Props {
  onUploaded: (preview: ImportPreview) => void;
}
```
por:
```typescript
import { useAnalyzeImport } from "@/lib/hooks/imports/use-imports";
import type { AnalyzeImportResponse } from "@/lib/api/endpoints/imports";

interface Props {
  onAnalyzed: (analysis: AnalyzeImportResponse) => void;
}
```

Y en el cuerpo, cambiar `useUploadImport()` → `useAnalyzeImport()`:
```typescript
  const analyze = useAnalyzeImport();

  const handleSubmit = async () => {
    if (!file) return;
    try {
      const analysis = await analyze.mutateAsync({ file });
      onAnalyzed(analysis);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : tCommon("error"));
    }
  };
```

También cambiar el botón de submit para mostrar estado correcto:
```typescript
  // Donde estaba upload.isPending, usar analyze.isPending
  const isPending = analyze.isPending;
```

- [ ] **Step 8.2: Actualizar `import-wizard.tsx` para el nuevo flujo de 5 pasos**

Reemplazar el archivo completo:

```tsx
"use client";

import * as React from "react";
import { useTranslations } from "next-intl";
import { useQuery } from "@tanstack/react-query";
import { Check } from "lucide-react";
import { toast } from "sonner";

import { cn } from "@/lib/utils/cn";
import {
  useUploadImport,
  useApplyImport,
  useImportStatus,
} from "@/lib/hooks/imports/use-imports";
import type {
  AnalyzeImportResponse,
  ColumnMappingItem,
  ImportPreview,
} from "@/lib/api/endpoints/imports";
import { divisionsApi, type Division } from "@/lib/api/endpoints/divisions";
import { UploadStep } from "./upload-step";
import { MappingStep } from "./mapping-step";
import { PreviewDiff } from "./preview-diff";
import { ApplyProgress } from "./apply-progress";
import { ImportReportPanel } from "./import-report";

type Step = 0 | 1 | 2 | 3 | 4;

/**
 * Wizard 5 pasos del importer PIM:
 * upload(0) → mapping(1) → preview(2) → confirm+divisions(3) → report(4)
 */
export function ImportWizard() {
  const t = useTranslations("imports.wizard");
  const tCommon = useTranslations("common");

  const [step, setStep] = React.useState<Step>(0);
  const [analysis, setAnalysis] = React.useState<AnalyzeImportResponse | null>(null);
  const [confirmedMapping, setConfirmedMapping] = React.useState<ColumnMappingItem[] | null>(null);
  const [file, setFile] = React.useState<File | null>(null);
  const [preview, setPreview] = React.useState<ImportPreview | null>(null);
  const [applyTriggered, setApplyTriggered] = React.useState(false);
  const [divisionCodes, setDivisionCodes] = React.useState<string[]>([]);

  const uploadPreview = useUploadImport();
  const apply = useApplyImport();
  const status = useImportStatus(preview?.id, step === 4 && !!preview);

  const isTerminal =
    status.data?.status === "completed" ||
    status.data?.status === "failed" ||
    status.data?.status === "cancelled";

  const handleAnalyzed = (a: AnalyzeImportResponse, f: File) => {
    setAnalysis(a);
    setFile(f);
    setStep(1);
  };

  const handleMappingConfirmed = async (mapping: ColumnMappingItem[]) => {
    if (!file) return;
    setConfirmedMapping(mapping);
    try {
      const p = await uploadPreview.mutateAsync({ file, mapping });
      setPreview(p);
      setStep(2);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : tCommon("error"));
    }
  };

  const handleConfirm = async () => {
    if (!preview) return;
    try {
      await apply.mutateAsync({
        runId: preview.id,
        division_codes: divisionCodes.length > 0 ? divisionCodes : null,
      });
      setApplyTriggered(true);
      setStep(4);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : tCommon("error"));
    }
  };

  const handleReset = () => {
    setAnalysis(null);
    setConfirmedMapping(null);
    setFile(null);
    setPreview(null);
    setApplyTriggered(false);
    setStep(0);
  };

  const stepTitles = [
    t("step1"), t("stepMapping"), t("step2"), t("step3"), t("step4"),
  ];

  return (
    <div className="space-y-6" data-testid="import-wizard">
      <Stepper currentStep={step} stepTitles={stepTitles} />

      {step === 0 ? (
        <UploadStep onAnalyzed={handleAnalyzed} />
      ) : null}

      {step === 1 && analysis ? (
        <MappingStep
          analysis={analysis}
          onBack={handleReset}
          onConfirm={handleMappingConfirmed}
          isLoading={uploadPreview.isPending}
        />
      ) : null}

      {step === 2 && preview ? (
        <PreviewDiff
          preview={preview}
          onBack={() => setStep(1)}
          onConfirm={() => setStep(3)}
        />
      ) : null}

      {step === 3 && preview ? (
        <div className="space-y-4">
          <DivisionPicker selected={divisionCodes} onChange={setDivisionCodes} />
          <PreviewDiff
            preview={preview}
            onBack={() => setStep(2)}
            onConfirm={handleConfirm}
            isApplying={apply.isPending}
          />
        </div>
      ) : null}

      {step === 4 && preview ? (
        <div className="space-y-4">
          <ApplyProgress run={status.data} isLoading={!status.data || !applyTriggered} />
          {isTerminal && status.data ? (
            <ImportReportPanel run={status.data} onReset={handleReset} />
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

// ... (Stepper y DivisionPicker sin cambios — copiar del archivo original)
```

> **Nota:** copiar las funciones `Stepper` y `DivisionPicker` del archivo original al final del nuevo archivo sin modificarlas.

También actualizar `useUploadImport` en `use-imports.ts` para aceptar mapping opcional:

```typescript
export function useUploadImport() {
  return useMutation<ImportPreview, Error, { file: File; mapping?: ColumnMappingItem[] }>({
    mutationFn: ({ file, mapping }) => importsApi.preview(file, "pim", mapping),
  });
}
```

- [ ] **Step 8.3: Verificar TypeScript compila**

```bash
cd mt-pricing-frontend && npx tsc --noEmit 2>&1 | head -30
```
Resultado esperado: sin errores.

- [ ] **Step 8.4: Commit**

```bash
git add "mt-pricing-frontend/app/(app)/imports/_components/import-wizard.tsx" \
        "mt-pricing-frontend/app/(app)/imports/_components/upload-step.tsx" \
        "mt-pricing-frontend/lib/hooks/imports/use-imports.ts"
git commit -m "feat(frontend/imports): wire MappingStep into 5-step wizard (upload→mapping→preview→confirm→report)"
```

---

## Task 9: i18n — strings del paso de mapeo

**Files:**
- Modify: `mt-pricing-frontend/messages/es.json`
- Modify: `mt-pricing-frontend/messages/en.json`
- Modify: `mt-pricing-frontend/messages/ar.json`

- [ ] **Step 9.1: Añadir a `es.json`**

Dentro del objeto `"imports"`, añadir la clave `"mapping"` y actualizar `"wizard"`:

```json
"wizard": {
  "step1": "Subir archivo",
  "stepMapping": "Mapeo de columnas",
  "step2": "Vista previa",
  "step3": "Confirmar",
  "step4": "Aplicar y reporte"
},
"mapping": {
  "subtitle": "{cols} columnas detectadas (cabecera en fila {row}). Revisa y ajusta el mapeo si es necesario.",
  "skuRequired": "La columna SKU es obligatoria.",
  "colExcel": "Columna Excel",
  "colSample": "Muestra",
  "colTarget": "Campo destino",
  "colTransform": "Transformación",
  "colConfidence": "Confianza",
  "back": "Volver",
  "confirm": "Confirmar mapeo y generar vista previa",
  "loading": "Generando vista previa…"
}
```

- [ ] **Step 9.2: Añadir a `en.json`**

```json
"wizard": {
  "step1": "Upload file",
  "stepMapping": "Column mapping",
  "step2": "Preview",
  "step3": "Confirm",
  "step4": "Apply & report"
},
"mapping": {
  "subtitle": "{cols} columns detected (header on row {row}). Review and adjust the mapping if needed.",
  "skuRequired": "The SKU column is required.",
  "colExcel": "Excel column",
  "colSample": "Sample",
  "colTarget": "Target field",
  "colTransform": "Transform",
  "colConfidence": "Confidence",
  "back": "Back",
  "confirm": "Confirm mapping & generate preview",
  "loading": "Generating preview…"
}
```

- [ ] **Step 9.3: Añadir a `ar.json`**

```json
"wizard": {
  "step1": "رفع الملف",
  "stepMapping": "تعيين الأعمدة",
  "step2": "معاينة",
  "step3": "تأكيد",
  "step4": "تطبيق والتقرير"
},
"mapping": {
  "subtitle": "تم اكتشاف {cols} عمود (الرأس في الصف {row}). راجع التعيين وعدّله إذا لزم الأمر.",
  "skuRequired": "عمود SKU مطلوب.",
  "colExcel": "عمود Excel",
  "colSample": "عينة",
  "colTarget": "الحقل المستهدف",
  "colTransform": "التحويل",
  "colConfidence": "الثقة",
  "back": "رجوع",
  "confirm": "تأكيد التعيين وإنشاء المعاينة",
  "loading": "جارٍ إنشاء المعاينة…"
}
```

- [ ] **Step 9.4: Commit**

```bash
git add mt-pricing-frontend/messages/es.json mt-pricing-frontend/messages/en.json mt-pricing-frontend/messages/ar.json
git commit -m "feat(i18n): add mapping step strings (es/en/ar)"
```

---

## Task 10: Rebuild frontend y smoke test

- [ ] **Step 10.1: Rebuild frontend con las nuevas dependencias**

```bash
docker compose -f docker-compose.dev.yml up -d --build frontend
```

- [ ] **Step 10.2: Verificar que arranca sin errores**

```bash
sleep 15
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/imports
```
Resultado esperado: `200`

- [ ] **Step 10.3: Test manual del flujo completo**

1. Abrir `http://localhost:3000/imports`
2. Subir `Documentos referencia de articulos/PIM completo_JcS_1.xlsx`
3. El wizard avanza a paso "Mapeo de columnas" — verificar que:
   - Se muestran 42 columnas
   - La columna `SKU` tiene `target_field=sku`
   - `Nombre EN` tiene `target_field=specs.name_en`
   - `Alto pieza (cm)` tiene `transform=cm_to_mm`
4. Hacer clic en "Confirmar mapeo" — el wizard avanza a "Vista previa"
5. Verificar que el diff muestra productos correctamente

- [ ] **Step 10.4: Commit final de verificación**

```bash
git add -A
git commit -m "fix(imports): support PIM xlsx with title rows + 42 columns via LLM-assisted mapping wizard"
```

---

## Self-Review

### Spec coverage
- ✅ Auto-detección de fila de cabecera (Task 1)
- ✅ LLM propone mapeo (Task 2)
- ✅ Flexible mapper acepta cualquier set de columnas (Task 3)
- ✅ Parser acepta header_row_index + custom_mapping (Task 4)
- ✅ Endpoint `POST /imports/analyze` (Task 5)
- ✅ Preview acepta mapping confirmado (Task 5)
- ✅ Frontend tipos + hook (Task 6)
- ✅ UI para revisar/editar el mapeo (Task 7)
- ✅ Wizard de 5 pasos integrado (Task 8)
- ✅ i18n (Task 9)
- ✅ Test de integración manual (Task 10)

### Known limitations (out of scope)
- Las traducciones (`Nombre FR/DE/IT/PT`) se guardan en `specs.name_fr` etc., no en `product_translations` (constraint solo permite 'es','ar','en').
- El differ (`COMPARED_FIELDS`) no incluye campos como `connection`, `bore_mm`, `pressure_max_bar` para comparaciones UPDATE — se persisten solo en CREATE. Actualizar `COMPARED_FIELDS` es un task separado.
- El pipeline batch async (Celery / `PimImporter`) no usa el nuevo mapping LLM — sigue usando `EXPECTED_HEADERS`. Update pending para Sprint siguiente.

# PIM Importer — Soporte de importación XML · Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir que el importador PIM acepte el archivo XML de la plantilla
estándar (`docs/templates/articulos/articulos.xsd`) en ambos flujos (wizard
preview y carga async Celery), persistiendo todos los datos del artículo.

**Architecture:** Un parser XML compartido produce el mismo `ParseResult` que el
parser xlsx, enchufado antes del differ (agnóstico al formato). Un helper
compartido `apply_related_entities` persiste los bloques ricos
(traducciones/releases/uom/bore) y es invocado tanto por el applier del wizard
como por `PimImporter` del flujo async. Validación tolerante por fila reutilizando
`ProductCreate`.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0 async, `defusedxml`
(parseo XML seguro — evita XXE/billion-laughs; no lxml), Pydantic v2, pytest async.

**Spec:** `docs/superpowers/specs/2026-05-29-pim-importer-xml-support-design.md`

---

## Notas de contexto para el implementador

- Hay **tres** pipelines de import preexistentes; este plan toca dos:
  - **Wizard** (`ImporterService.preview` → `parser.parse_xlsx_stream` →
    `differ.compute_diff` → `applier.apply_diffs_chunked`).
  - **Async** (`run_pim_import_task` → `services/imports/pim_importer.py:PimImporter`,
    lector openpyxl fila-a-fila).
  - (El tercero, `import_orchestrator.py`, NO se toca.)
- `ParsedRow` (en `app/services/importer/parser.py`) tiene:
  `row_index:int`, `sku:str|None`, `payload:dict`, `errors:list[str]`.
- `RowDiff` (en `differ.py`) **conserva `payload`** en todas las acciones,
  incluido UPDATE. El differ solo compara `COMPARED_FIELDS`; cualquier clave extra
  del payload (las reservadas `_*`) pasa intacta.
- Namespace del XML: `https://mtme-api/schemas/articulos/v1`. Los tags de
  ElementTree llegan como `{https://mtme-api/schemas/articulos/v1}article`.
- Modelos y unicidad (en `app/db/models/product.py`):
  - `ProductTranslation` PK `(sku, lang)`; status check `pending|draft|approved`.
  - `ProductRelease` único `(product_sku, market_code)`.
  - `ProductUomConversion` único `(product_sku, uom_from, uom_to)`; factor `>0`.
  - `ProductBoreDimension` **sin** índice único → usar select-or-insert.

### Contrato de claves reservadas en `payload`

El parser XML añade al payload (además de escalares + `dimensions/packaging/specs`):

| Clave | Forma |
|-------|-------|
| `_translations` | `list[dict]` con `lang, status, name, description, marketing_copy, meta_title, meta_description, applications_text, technical_limits, notes, marketing_features` |
| `_releases` | `list[dict]` con `market_code, local_name, local_description, local_sku, local_uom, list_price, price_currency, tax_class` |
| `_uom_conversions` | `list[dict]` con `uom_from, uom_to, factor` |
| `_bore_dimensions` | `list[dict]` con `standard_system, standard_code, is_primary, dn_nominal_ref, pressure_class, bore_mm, face_to_face_mm, end_to_end_mm, flange_od_mm, bolt_circle_mm, bolt_count, bolt_size, notes` |

`name_en`, `description_en`, `marketing_copy_en` siguen siendo escalares (los
consume el applier/PimImporter existente). `_translations` es la fuente de los
campos extendidos por idioma (en/es/ar).

---

## Task 1: Parser XML — escalares + JSONB + validación por fila

**Files:**
- Modify: `mt-pricing-backend/pyproject.toml` (añadir dependencia `defusedxml`)
- Create: `mt-pricing-backend/app/services/importer/xml_parser.py`
- Test: `mt-pricing-backend/tests/unit/importer/test_xml_parser_core.py`

- [ ] **Step 0: Añadir la dependencia segura de XML**

Añadir `defusedxml` a las dependencias del backend y sincronizar el lock:

Run: `cd mt-pricing-backend && uv add "defusedxml>=0.7.1"`
Expected: `pyproject.toml` lista `defusedxml` y `uv.lock` se actualiza.
(Si `uv add` no está disponible, añadir `"defusedxml>=0.7.1"` a
`[project].dependencies` en `pyproject.toml` y correr `uv lock`.)

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/importer/test_xml_parser_core.py
from __future__ import annotations

from app.services.importer.xml_parser import parse_xml_stream

_NS = "https://mtme-api/schemas/articulos/v1"

_MINIMAL = f"""<?xml version="1.0" encoding="UTF-8"?>
<catalog xmlns="{_NS}">
  <article>
    <sku>MT-V-038</sku>
    <name_en>Brass Ball Valve DN25</name_en>
    <family>ball_valve</family>
    <material>brass</material>
    <dn>25</dn>
    <pn>40</pn>
    <weight>0.42</weight>
    <weight_unit>kg</weight_unit>
    <dimensions><high_mm>62.5</high_mm><wide_mm>48.0</wide_mm></dimensions>
    <packaging><qty_per_box>20</qty_per_box></packaging>
    <specs><materials_body>brass CW617N</materials_body></specs>
  </article>
</catalog>"""


def test_parse_scalars_and_jsonb() -> None:
    result = parse_xml_stream(_MINIMAL.encode("utf-8"))
    assert result.header_ok is True
    assert result.total_data_rows == 1
    row = result.rows[0]
    assert row.sku == "MT-V-038"
    assert row.errors == []
    p = row.payload
    assert p["name_en"] == "Brass Ball Valve DN25"
    assert p["family"] == "ball_valve"
    assert p["dn"] == "25"
    assert p["pn"] == "40"
    assert p["weight"] == "0.42"            # decimales viajan como str (JSONB-safe)
    assert p["dimensions"] == {"high_mm": "62.5", "wide_mm": "48.0"}
    assert p["packaging"] == {"qty_per_box": 20}
    assert p["specs"]["materials_body"] == "brass CW617N"


def test_invalid_dn_marks_row_error_not_file() -> None:
    bad = _MINIMAL.replace("<dn>25</dn>", "<dn>99</dn>")
    result = parse_xml_stream(bad.encode("utf-8"))
    assert result.header_ok is True          # archivo no se rechaza
    assert result.rows[0].errors            # la fila tiene error
    assert any("dn" in e.lower() for e in result.rows[0].errors)


def test_entity_expansion_attack_is_rejected() -> None:
    """defusedxml debe rechazar DTD/entidades (XXE / billion-laughs)."""
    import pytest

    from app.services.importer.xml_parser import XmlParseError

    evil = (
        '<?xml version="1.0"?>'
        '<!DOCTYPE lolz [<!ENTITY lol "lol">'
        '<!ENTITY lol2 "&lol;&lol;&lol;">]>'
        f'<catalog xmlns="{_NS}"><article><sku>&lol2;</sku>'
        "<name_en>x</name_en><family>f</family></article></catalog>"
    )
    with pytest.raises(XmlParseError):
        parse_xml_stream(evil.encode("utf-8"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd mt-pricing-backend && uv run pytest tests/unit/importer/test_xml_parser_core.py -v`
Expected: FAIL — `ModuleNotFoundError: app.services.importer.xml_parser`.

- [ ] **Step 3: Write minimal implementation**

```python
# app/services/importer/xml_parser.py
"""Parser XML de la plantilla estándar de artículos → ParseResult.

Produce el mismo ParseResult/ParsedRow que el parser xlsx para enchufarse antes
del differ. Validación tolerante por fila: errores por <article> van a
ParsedRow.errors (no abortan el archivo). Errores de archivo (XML malformado,
raíz != catalog) se lanzan como XmlParseError.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, BinaryIO
from xml.etree.ElementTree import Element, ParseError  # solo tipos + excepción

import defusedxml.ElementTree as DET  # parseo seguro (XXE/billion-laughs)
from defusedxml.common import DefusedXmlException
from pydantic import ValidationError

from app.schemas.products import ProductCreate
from app.services.importer.parser import ParsedRow, ParseResult

NS = "https://mtme-api/schemas/articulos/v1"

# Campos escalares de texto que se copian tal cual al payload.
_TEXT_FIELDS: tuple[str, ...] = (
    "name_en", "description_en", "marketing_copy_en",
    "family", "subfamily", "type", "series", "brand",
    "material", "dn", "pn", "connection", "size", "manufacturing_method",
    "gtin", "intrastat_code", "erp_name", "weight_unit",
    "lifecycle_status", "revision", "data_quality",
    "parent_sku", "display_pair_sku", "video_url", "external_url",
)
_INT_FIELDS: tuple[str, ...] = ("temp_min_c", "temp_max_c")
_DECIMAL_FIELDS: tuple[str, ...] = ("weight", "pressure_max_bar")
_BOOL_FIELDS: tuple[str, ...] = ("is_parent", "is_variant")

# Subconjunto escalar que valida ProductCreate (excluye JSONB/relacionales).
_VALIDATABLE = set(_TEXT_FIELDS) | set(_INT_FIELDS) | set(_DECIMAL_FIELDS) | {"sku"}


class XmlParseError(ValueError):
    """Error de archivo (malformado / raíz incorrecta) — aborta el parse."""


def _tag(elem: Element) -> str:
    """Nombre de tag sin namespace."""
    t = elem.tag
    return t.split("}", 1)[1] if "}" in t else t


def _text(parent: Element, name: str) -> str | None:
    child = parent.find(f"{{{NS}}}{name}")
    if child is None or child.text is None:
        return None
    s = child.text.strip()
    return s or None


def _jsonb_block(parent: Element, name: str, int_keys: frozenset[str]) -> dict[str, Any]:
    """Lee un bloque (dimensions/packaging) como dict; decimales→str, int_keys→int."""
    block = parent.find(f"{{{NS}}}{name}")
    out: dict[str, Any] = {}
    if block is None:
        return out
    for child in block:
        key = _tag(child)
        if child.text is None:
            continue
        val = child.text.strip()
        if not val:
            continue
        out[key] = int(float(val)) if key in int_keys else val
    return out


_DIM_INT: frozenset[str] = frozenset()
_PKG_INT: frozenset[str] = frozenset({"qty_per_box", "moq_inner_box", "x_pallet"})


def _build_scalars(article: Element) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    sku = _text(article, "sku")
    if sku is not None:
        payload["sku"] = sku
    for f in _TEXT_FIELDS:
        v = _text(article, f)
        if v is not None:
            payload[f] = v
    for f in _INT_FIELDS:
        v = _text(article, f)
        if v is not None:
            payload[f] = int(float(v))
    for f in _DECIMAL_FIELDS:
        v = _text(article, f)
        if v is not None:
            payload[f] = str(Decimal(v))
    for f in _BOOL_FIELDS:
        v = _text(article, f)
        if v is not None:
            payload[f] = v.lower() == "true"
    # division_codes
    dc = article.find(f"{{{NS}}}division_codes")
    if dc is not None:
        codes = [c.text.strip() for c in dc if c.text and c.text.strip()]
        if codes:
            payload["division_codes"] = codes
    return payload


def _validate_row(payload: dict[str, Any]) -> list[str]:
    """Valida el subconjunto escalar con ProductCreate. Devuelve errores."""
    scalars = {k: v for k, v in payload.items() if k in _VALIDATABLE}
    try:
        ProductCreate(**scalars)  # type: ignore[arg-type]
    except ValidationError as exc:
        return [f"{e['loc'][0] if e['loc'] else '?'}: {e['msg']}" for e in exc.errors()]
    return []


def parse_xml_stream(source: bytes | BinaryIO) -> ParseResult:
    data = source if isinstance(source, bytes) else source.read()
    try:
        root = DET.fromstring(data)
    except (ParseError, DefusedXmlException) as exc:
        raise XmlParseError(f"XML inválido o inseguro: {exc}") from exc
    if _tag(root) != "catalog":
        raise XmlParseError(f"Raíz esperada 'catalog', recibida '{_tag(root)}'.")

    rows: list[ParsedRow] = []
    seen: dict[str, int] = {}
    duplicates: list[str] = []

    for i, article in enumerate(root.findall(f"{{{NS}}}article"), start=1):
        payload = _build_scalars(article)
        payload["dimensions"] = _jsonb_block(article, "dimensions", _DIM_INT)
        payload["packaging"] = _jsonb_block(article, "packaging", _PKG_INT)
        payload["specs"] = {}  # se completa en Task 2
        errors = _validate_row(payload)
        sku = payload.get("sku")
        if sku is not None:
            if sku in seen:
                duplicates.append(sku)
                errors.append(f"SKU duplicado en archivo (primera ocurrencia row {seen[sku]}).")
            else:
                seen[sku] = i
        rows.append(ParsedRow(row_index=i, sku=sku, payload=payload, errors=errors))

    return ParseResult(
        rows=rows, header_errors=[], total_data_rows=len(rows), duplicate_skus=duplicates
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd mt-pricing-backend && uv run pytest tests/unit/importer/test_xml_parser_core.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add mt-pricing-backend/app/services/importer/xml_parser.py \
        mt-pricing-backend/tests/unit/importer/test_xml_parser_core.py
git commit -m "feat(importer): xml_parser core — escalares + jsonb + validación por fila"
```

---

## Task 2: Parser XML — specs (extra/connections) + bloques ricos

**Files:**
- Modify: `mt-pricing-backend/app/services/importer/xml_parser.py`
- Test: `mt-pricing-backend/tests/unit/importer/test_xml_parser_rich.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/importer/test_xml_parser_rich.py
from __future__ import annotations

from app.services.importer.xml_parser import parse_xml_stream

_NS = "https://mtme-api/schemas/articulos/v1"

_RICH = f"""<?xml version="1.0" encoding="UTF-8"?>
<catalog xmlns="{_NS}">
  <article>
    <sku>MT-V-038</sku>
    <name_en>Brass Ball Valve DN25</name_en>
    <family>ball_valve</family>
    <specs>
      <materials_body>brass</materials_body>
      <kv>32.5</kv>
      <connections>
        <connection><position>1</position><type>threaded</type><dn>25</dn></connection>
        <connection><position>2</position><type>threaded</type><dn>25</dn></connection>
      </connections>
      <extra>
        <field key="surface_treatment">nickel_plated</field>
        <field key="mesh_microns">500</field>
      </extra>
    </specs>
    <translations>
      <translation lang="es" status="approved">
        <name>Válvula de bola</name>
        <description>Desc ES</description>
      </translation>
      <translation lang="ar"><name>صمام</name></translation>
    </translations>
    <releases>
      <release market_code="UAE">
        <local_name>Ball Valve</local_name>
        <list_price>45.00</list_price>
        <price_currency>AED</price_currency>
      </release>
    </releases>
    <uom_conversions>
      <uom_conversion uom_from="BOX" uom_to="EA" factor="20"/>
    </uom_conversions>
    <bore_dimensions>
      <bore_dimension standard_system="EN" standard_code="EN 1092-1" is_primary="true">
        <bore_mm>25</bore_mm>
      </bore_dimension>
    </bore_dimensions>
  </article>
</catalog>"""


def test_specs_extra_and_connections() -> None:
    row = parse_xml_stream(_RICH.encode("utf-8")).rows[0]
    specs = row.payload["specs"]
    assert specs["materials_body"] == "brass"
    assert specs["kv"] == "32.5"
    assert specs["surface_treatment"] == "nickel_plated"
    assert specs["mesh_microns"] == "500"
    assert specs["connections"] == [
        {"position": 1, "type": "threaded", "dn": "25"},
        {"position": 2, "type": "threaded", "dn": "25"},
    ]


def test_rich_blocks() -> None:
    p = parse_xml_stream(_RICH.encode("utf-8")).rows[0].payload
    assert {"lang": "es", "status": "approved", "name": "Válvula de bola",
            "description": "Desc ES"}.items() <= p["_translations"][0].items()
    assert p["_translations"][1]["lang"] == "ar"
    assert p["_releases"][0] == {
        "market_code": "UAE", "local_name": "Ball Valve",
        "list_price": "45.00", "price_currency": "AED",
    }
    assert p["_uom_conversions"][0] == {"uom_from": "BOX", "uom_to": "EA", "factor": "20"}
    bore = p["_bore_dimensions"][0]
    assert bore["standard_system"] == "EN"
    assert bore["standard_code"] == "EN 1092-1"
    assert bore["is_primary"] is True
    assert bore["bore_mm"] == "25"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd mt-pricing-backend && uv run pytest tests/unit/importer/test_xml_parser_rich.py -v`
Expected: FAIL — `KeyError: 'kv'` / `_translations` ausente.

- [ ] **Step 3: Write the implementation**

Add these helpers and wire them into `parse_xml_stream` (in `xml_parser.py`).
Replace the line `payload["specs"] = {}  # se completa en Task 2` with
`payload["specs"] = _build_specs(article)` and, right after, add the four rich
blocks before `errors = _validate_row(payload)`:

```python
        payload["specs"] = _build_specs(article)
        _tr = _build_translations(article)
        if _tr:
            payload["_translations"] = _tr
        _rel = _build_releases(article)
        if _rel:
            payload["_releases"] = _rel
        _uom = _build_uom(article)
        if _uom:
            payload["_uom_conversions"] = _uom
        _bore = _build_bore(article)
        if _bore:
            payload["_bore_dimensions"] = _bore
```

Add the helper functions:

```python
_SPECS_DECIMAL: frozenset[str] = frozenset(
    {"kv", "torque_nm", "dim_L", "dim_H", "dim_H1", "dim_W", "dim_T1",
     "dim_T2", "dim_T3", "dim_S", "dim_h", "dim_D", "dim_K", "weight_gross_kg"}
)


def _build_specs(article: Element) -> dict[str, Any]:
    block = article.find(f"{{{NS}}}specs")
    out: dict[str, Any] = {}
    if block is None:
        return out
    for child in block:
        key = _tag(child)
        if key == "connections":
            conns: list[dict[str, Any]] = []
            for conn in child:
                c: dict[str, Any] = {}
                for f in conn:
                    fk = _tag(f)
                    if f.text is None or not f.text.strip():
                        continue
                    val = f.text.strip()
                    c[fk] = int(val) if fk == "position" else val
                if c:
                    conns.append(c)
            if conns:
                out["connections"] = conns
        elif key == "extra":
            for fld in child:
                k = fld.get("key")
                if k and fld.text and fld.text.strip():
                    out[k] = fld.text.strip()
        else:
            if child.text and child.text.strip():
                out[key] = child.text.strip()
    return out


def _children_to_dict(elem: Element) -> dict[str, str]:
    out: dict[str, str] = {}
    for child in elem:
        if child.text and child.text.strip():
            out[_tag(child)] = child.text.strip()
    return out


def _build_translations(article: Element) -> list[dict[str, Any]]:
    block = article.find(f"{{{NS}}}translations")
    if block is None:
        return []
    out: list[dict[str, Any]] = []
    for tr in block.findall(f"{{{NS}}}translation"):
        entry: dict[str, Any] = {"lang": tr.get("lang"), "status": tr.get("status", "draft")}
        entry.update(_children_to_dict(tr))
        out.append(entry)
    return out


def _build_releases(article: Element) -> list[dict[str, Any]]:
    block = article.find(f"{{{NS}}}releases")
    if block is None:
        return []
    out: list[dict[str, Any]] = []
    for rel in block.findall(f"{{{NS}}}release"):
        entry: dict[str, Any] = {"market_code": rel.get("market_code")}
        entry.update(_children_to_dict(rel))
        out.append(entry)
    return out


def _build_uom(article: Element) -> list[dict[str, Any]]:
    block = article.find(f"{{{NS}}}uom_conversions")
    if block is None:
        return []
    return [
        {"uom_from": u.get("uom_from"), "uom_to": u.get("uom_to"), "factor": u.get("factor")}
        for u in block.findall(f"{{{NS}}}uom_conversion")
    ]


def _build_bore(article: Element) -> list[dict[str, Any]]:
    block = article.find(f"{{{NS}}}bore_dimensions")
    if block is None:
        return []
    out: list[dict[str, Any]] = []
    for b in block.findall(f"{{{NS}}}bore_dimension"):
        entry: dict[str, Any] = {
            "standard_system": b.get("standard_system"),
            "standard_code": b.get("standard_code"),
            "is_primary": (b.get("is_primary", "false").lower() == "true"),
        }
        entry.update(_children_to_dict(b))
        out.append(entry)
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd mt-pricing-backend && uv run pytest tests/unit/importer/test_xml_parser_rich.py tests/unit/importer/test_xml_parser_core.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add mt-pricing-backend/app/services/importer/xml_parser.py \
        mt-pricing-backend/tests/unit/importer/test_xml_parser_rich.py
git commit -m "feat(importer): xml_parser — specs extra/connections + bloques ricos"
```

---

## Task 3: Dispatcher de formato `parse_source`

**Files:**
- Create: `mt-pricing-backend/app/services/importer/source_dispatch.py`
- Test: `mt-pricing-backend/tests/unit/importer/test_source_dispatch.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/importer/test_source_dispatch.py
from __future__ import annotations

import pytest

from app.services.importer.source_dispatch import is_xml_filename, parse_source

_NS = "https://mtme-api/schemas/articulos/v1"
_XML = f'<catalog xmlns="{_NS}"><article><sku>MT-V-1</sku>' \
       f"<name_en>X</name_en><family>ball_valve</family></article></catalog>"


@pytest.mark.parametrize("name,expected", [
    ("articulos.xml", True), ("ART.XML", True),
    ("PIM completo.xlsx", False), ("data.csv", False),
])
def test_is_xml_filename(name: str, expected: bool) -> None:
    assert is_xml_filename(name) is expected


def test_parse_source_routes_xml() -> None:
    result = parse_source(_XML.encode("utf-8"), "articulos.xml")
    assert result.total_data_rows == 1
    assert result.rows[0].sku == "MT-V-1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd mt-pricing-backend && uv run pytest tests/unit/importer/test_source_dispatch.py -v`
Expected: FAIL — `ModuleNotFoundError: app.services.importer.source_dispatch`.

- [ ] **Step 3: Write the implementation**

```python
# app/services/importer/source_dispatch.py
"""Dispatcher de formato para el importador PIM: xlsx vs XML.

Punto único de detección de formato. El wizard y el worker async llaman aquí
en vez de a un parser concreto.
"""
from __future__ import annotations

from typing import Any

from app.services.importer.parser import ParseResult, parse_xlsx_stream
from app.services.importer.xml_parser import parse_xml_stream


def is_xml_filename(filename: str | None) -> bool:
    return bool(filename) and filename.lower().endswith(".xml")


def parse_source(
    file_bytes: bytes,
    filename: str | None,
    *,
    custom_mapping: list[Any] | None = None,
    header_row_index: int | None = None,
) -> ParseResult:
    """Parsea el archivo eligiendo el parser por extensión.

    - `.xml` → parse_xml_stream (ignora custom_mapping/header_row_index).
    - resto → parse_xlsx_stream con los argumentos del wizard.
    """
    if is_xml_filename(filename):
        return parse_xml_stream(file_bytes)
    import io

    bio = io.BytesIO(file_bytes)
    if custom_mapping is not None:
        return parse_xlsx_stream(
            bio, header_row_index=header_row_index or 0, custom_mapping=custom_mapping
        )
    return parse_xlsx_stream(bio)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd mt-pricing-backend && uv run pytest tests/unit/importer/test_source_dispatch.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add mt-pricing-backend/app/services/importer/source_dispatch.py \
        mt-pricing-backend/tests/unit/importer/test_source_dispatch.py
git commit -m "feat(importer): source_dispatch — ruteo xlsx/xml por extensión"
```

---

## Task 4: Helper compartido `apply_related_entities`

**Files:**
- Create: `mt-pricing-backend/app/services/importer/related_writer.py`
- Test: `mt-pricing-backend/tests/unit/importer/test_related_writer.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/importer/test_related_writer.py
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.db.models.product import (
    Product, ProductBoreDimension, ProductRelease,
    ProductTranslation, ProductUomConversion,
)
from app.services.importer.related_writer import apply_related_entities

pytestmark = pytest.mark.asyncio


async def _seed_product(session) -> None:
    session.add(Product(sku="MT-V-1", family="ball_valve", brand="MT",
                         data_quality="partial", manual_locked_fields=[]))
    await session.flush()


async def test_apply_all_blocks(db_session) -> None:
    await _seed_product(db_session)
    related = {
        "_translations": [
            {"lang": "es", "status": "approved", "name": "Válvula", "description": "d"},
        ],
        "_releases": [
            {"market_code": "UAE", "local_name": "BV", "list_price": "45.00",
             "price_currency": "AED"},
        ],
        "_uom_conversions": [{"uom_from": "BOX", "uom_to": "EA", "factor": "20"}],
        "_bore_dimensions": [
            {"standard_system": "EN", "standard_code": "EN 1092-1",
             "is_primary": True, "bore_mm": "25"},
        ],
    }
    await apply_related_entities(db_session, "MT-V-1", related, actor_id=None)
    await db_session.flush()

    tr = (await db_session.execute(
        select(ProductTranslation).where(ProductTranslation.sku == "MT-V-1"))).scalars().all()
    assert {t.lang for t in tr} == {"es"}
    rel = (await db_session.execute(
        select(ProductRelease).where(ProductRelease.product_sku == "MT-V-1"))).scalars().all()
    assert rel[0].market_code == "UAE"
    uom = (await db_session.execute(
        select(ProductUomConversion).where(
            ProductUomConversion.product_sku == "MT-V-1"))).scalars().all()
    assert uom[0].uom_from == "BOX"
    bore = (await db_session.execute(
        select(ProductBoreDimension).where(
            ProductBoreDimension.product_sku == "MT-V-1"))).scalars().all()
    assert bore[0].standard_code == "EN 1092-1"


async def test_idempotent_reapply(db_session) -> None:
    await _seed_product(db_session)
    related = {
        "_releases": [{"market_code": "UAE", "local_name": "BV"}],
        "_uom_conversions": [{"uom_from": "BOX", "uom_to": "EA", "factor": "12"}],
        "_bore_dimensions": [{"standard_system": "EN", "standard_code": "EN 1092-1"}],
    }
    await apply_related_entities(db_session, "MT-V-1", related, actor_id=None)
    await apply_related_entities(db_session, "MT-V-1", related, actor_id=None)
    await db_session.flush()
    for model, col in [
        (ProductRelease, ProductRelease.product_sku),
        (ProductUomConversion, ProductUomConversion.product_sku),
        (ProductBoreDimension, ProductBoreDimension.product_sku),
    ]:
        rows = (await db_session.execute(select(model).where(col == "MT-V-1"))).scalars().all()
        assert len(rows) == 1  # no duplica
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd mt-pricing-backend && uv run pytest tests/unit/importer/test_related_writer.py -v`
Expected: FAIL — `ModuleNotFoundError: app.services.importer.related_writer`.

- [ ] **Step 3: Write the implementation**

```python
# app/services/importer/related_writer.py
"""Upsert idempotente de bloques relacionales de un artículo.

Consumido por el applier del wizard y por PimImporter (async). Lee las claves
reservadas `_translations`/`_releases`/`_uom_conversions`/`_bore_dimensions` y
hace upsert por su clave natural.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.product import (
    ProductBoreDimension,
    ProductRelease,
    ProductTranslation,
    ProductUomConversion,
)

_TR_FIELDS = (
    "name", "description", "marketing_copy", "meta_title", "meta_description",
    "applications_text", "technical_limits", "notes", "marketing_features",
)
_REL_FIELDS = (
    "local_name", "local_description", "local_sku", "local_uom",
    "list_price", "price_currency", "tax_class",
)
_BORE_FIELDS = (
    "dn_nominal_ref", "pressure_class", "bore_mm", "face_to_face_mm",
    "end_to_end_mm", "flange_od_mm", "bolt_circle_mm", "bolt_count",
    "bolt_size", "notes",
)
_BORE_DECIMAL = {"bore_mm", "face_to_face_mm", "end_to_end_mm",
                 "flange_od_mm", "bolt_circle_mm"}


def _dec(v: Any) -> Decimal | None:
    return Decimal(str(v)) if v not in (None, "") else None


async def _upsert_translations(session: AsyncSession, sku: str, items: list[dict]) -> None:
    for it in items:
        lang = it.get("lang")
        if lang not in ("en", "es", "ar"):
            continue
        values: dict[str, Any] = {"sku": sku, "lang": lang,
                                  "status": it.get("status") or "draft"}
        for f in _TR_FIELDS:
            if it.get(f) is not None:
                values[f] = it[f]
        update_set = {k: v for k, v in values.items() if k not in ("sku", "lang")}
        update_set["updated_at"] = text("now()")
        stmt = pg_insert(ProductTranslation).values(**values).on_conflict_do_update(
            index_elements=["sku", "lang"], set_=update_set
        )
        await session.execute(stmt)


async def _upsert_releases(session: AsyncSession, sku: str, items: list[dict]) -> None:
    for it in items:
        if not it.get("market_code"):
            continue
        values: dict[str, Any] = {"product_sku": sku, "market_code": it["market_code"]}
        for f in _REL_FIELDS:
            if it.get(f) is not None:
                values[f] = _dec(it[f]) if f == "list_price" else it[f]
        update_set = {k: v for k, v in values.items()
                      if k not in ("product_sku", "market_code")}
        update_set["updated_at"] = text("now()")
        stmt = pg_insert(ProductRelease).values(**values).on_conflict_do_update(
            index_elements=["product_sku", "market_code"], set_=update_set
        )
        await session.execute(stmt)


async def _upsert_uom(session: AsyncSession, sku: str, items: list[dict]) -> None:
    for it in items:
        if not (it.get("uom_from") and it.get("uom_to") and it.get("factor")):
            continue
        values = {"product_sku": sku, "uom_from": it["uom_from"],
                  "uom_to": it["uom_to"], "factor": _dec(it["factor"])}
        stmt = pg_insert(ProductUomConversion).values(**values).on_conflict_do_update(
            index_elements=["product_sku", "uom_from", "uom_to"],
            set_={"factor": values["factor"]},
        )
        await session.execute(stmt)


async def _upsert_bore(session: AsyncSession, sku: str, items: list[dict]) -> None:
    # product_bore_dimensions NO tiene índice único → select-or-insert/update.
    for it in items:
        system, code = it.get("standard_system"), it.get("standard_code")
        if not (system and code):
            continue
        existing = (await session.execute(
            select(ProductBoreDimension).where(
                ProductBoreDimension.product_sku == sku,
                ProductBoreDimension.standard_system == system,
                ProductBoreDimension.standard_code == code,
            )
        )).scalar_one_or_none()
        fields = {}
        for f in _BORE_FIELDS:
            if it.get(f) is not None:
                fields[f] = _dec(it[f]) if f in _BORE_DECIMAL else it[f]
        fields["is_primary"] = bool(it.get("is_primary", False))
        if existing is None:
            session.add(ProductBoreDimension(
                product_sku=sku, standard_system=system, standard_code=code, **fields
            ))
        else:
            for k, v in fields.items():
                setattr(existing, k, v)


async def apply_related_entities(
    session: AsyncSession,
    sku: str,
    payload: dict[str, Any],
    *,
    actor_id: UUID | None,
) -> None:
    """Upsert de todos los bloques relacionales presentes en `payload`."""
    if payload.get("_translations"):
        await _upsert_translations(session, sku, payload["_translations"])
    if payload.get("_releases"):
        await _upsert_releases(session, sku, payload["_releases"])
    if payload.get("_uom_conversions"):
        await _upsert_uom(session, sku, payload["_uom_conversions"])
    if payload.get("_bore_dimensions"):
        await _upsert_bore(session, sku, payload["_bore_dimensions"])


def pop_related_keys(payload: dict[str, Any]) -> dict[str, Any]:
    """Extrae (mutando) las claves reservadas del payload y las devuelve."""
    return {k: payload.pop(k) for k in (
        "_translations", "_releases", "_uom_conversions", "_bore_dimensions"
    ) if k in payload}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd mt-pricing-backend && uv run pytest tests/unit/importer/test_related_writer.py -v`
Expected: PASS (2 passed).

> If `db_session` fixture name differs, check `tests/conftest.py` for the async
> session fixture and use that name.

- [ ] **Step 5: Commit**

```bash
git add mt-pricing-backend/app/services/importer/related_writer.py \
        mt-pricing-backend/tests/unit/importer/test_related_writer.py
git commit -m "feat(importer): related_writer — upsert idempotente translations/releases/uom/bore"
```

---

## Task 5: Wire `parse_source` en el wizard (`ImporterService.preview`)

**Files:**
- Modify: `mt-pricing-backend/app/services/importer/importer_service.py:186-205`
- Test: `mt-pricing-backend/tests/unit/importer/test_preview_xml.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/importer/test_preview_xml.py
from __future__ import annotations

import pytest

from app.services.importer.importer_service import ImporterService

pytestmark = pytest.mark.asyncio

_NS = "https://mtme-api/schemas/articulos/v1"
_XML = (f'<catalog xmlns="{_NS}"><article><sku>MT-XML-1</sku>'
        f"<name_en>XML Valve</name_en><family>ball_valve</family>"
        f"<dn>25</dn></article></catalog>")


async def test_preview_accepts_xml(db_session, make_user) -> None:
    svc = ImporterService(db_session)
    state = await svc.preview(
        file_bytes=_XML.encode("utf-8"),
        filename="articulos.xml",
        actor=make_user(),
        type_="pim",
    )
    assert state.status == "preview_ready"
    assert state.summary["total"] == 1
    assert state.summary["creates"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd mt-pricing-backend && uv run pytest tests/unit/importer/test_preview_xml.py -v`
Expected: FAIL — el parser xlsx revienta con bytes XML (`InvalidFileException`).

- [ ] **Step 3: Write the implementation**

In `importer_service.py`, replace the parse block inside `preview()` (the
`try: ... parse_result = parse_xlsx_stream(...)` section, lines ~189-205) with a
call to `parse_source`:

```python
        # Parse según formato (xlsx o xml de la plantilla).
        from app.services.importer.source_dispatch import is_xml_filename, parse_source

        try:
            if is_xml_filename(filename):
                parse_result = parse_source(file_bytes, filename)
            elif custom_mapping is not None:
                header_idx, _headers, _samples = detect_header_row(file_bytes)
                parse_result = parse_source(
                    file_bytes, filename,
                    custom_mapping=custom_mapping, header_row_index=header_idx,
                )
            else:
                parse_result = parse_source(file_bytes, filename)
        except Exception as exc:
            raise ImporterDomainError(
                code="import_parse_failed",
                message=f"Error parseando archivo: {exc}",
                status_code=422,
            ) from exc
```

Leave the rest of `preview()` (header_ok check, compute_diff, summary) unchanged.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd mt-pricing-backend && uv run pytest tests/unit/importer/test_preview_xml.py -v`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add mt-pricing-backend/app/services/importer/importer_service.py \
        mt-pricing-backend/tests/unit/importer/test_preview_xml.py
git commit -m "feat(importer): wizard preview acepta xml via parse_source"
```

---

## Task 6: Extender el applier del wizard con bloques ricos

**Files:**
- Modify: `mt-pricing-backend/app/services/importer/applier.py:104-211`
- Test: `mt-pricing-backend/tests/integration/test_apply_xml_related.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_apply_xml_related.py
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.db.models.product import Product, ProductRelease
from app.services.importer.differ import RowAction, RowDiff
from app.services.importer.applier import apply_diffs_chunked

pytestmark = pytest.mark.asyncio


async def test_apply_create_persists_releases(db_session, make_user) -> None:
    user = make_user()
    diff = RowDiff(
        row_index=1, sku="MT-REL-1", action=RowAction.CREATE,
        payload={
            "sku": "MT-REL-1", "name_en": "Rel Valve", "family": "ball_valve",
            "_releases": [{"market_code": "UAE", "local_name": "Rel Valve",
                           "list_price": "45.00", "price_currency": "AED"}],
        },
    )
    await apply_diffs_chunked(db_session, [diff], user, run_id="t1")
    await db_session.flush()
    prod = (await db_session.execute(
        select(Product).where(Product.sku == "MT-REL-1"))).scalar_one()
    assert prod.sku == "MT-REL-1"
    rel = (await db_session.execute(
        select(ProductRelease).where(ProductRelease.product_sku == "MT-REL-1"))).scalars().all()
    assert rel[0].market_code == "UAE"
    assert str(rel[0].list_price) == "45.0000"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd mt-pricing-backend && uv run pytest tests/integration/test_apply_xml_related.py -v`
Expected: FAIL — `repo.create(**payload)` recibe `_releases` (kw inválido) → error.

- [ ] **Step 3: Write the implementation**

In `applier.py`, edit `_apply_one`. In the **CREATE** branch, right after
`payload = dict(diff.payload)` and before `prod = await repo.create(**payload)`,
extract the reserved keys:

```python
        from app.services.importer.related_writer import (
            apply_related_entities, pop_related_keys,
        )
        related = pop_related_keys(payload)
```

Then after the product + existing translations are created (after the
`if trans_names or description_en or marketing_copy_en:` block), add:

```python
        if related:
            await apply_related_entities(session, prod.sku, related, actor_id=actor.id)
```

In the **UPDATE** branch, after the `for f, change in diff.diff.items(): ...`
loop and `await session.flush()`, add:

```python
        related = pop_related_keys(dict(diff.payload))
        if related:
            await apply_related_entities(session, diff.sku, related, actor_id=actor.id)  # type: ignore[arg-type]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd mt-pricing-backend && uv run pytest tests/integration/test_apply_xml_related.py -v`
Expected: PASS (1 passed).

- [ ] **Step 5: Run the full importer unit + integration suite (regression)**

Run: `cd mt-pricing-backend && uv run pytest tests/unit/importer tests/integration -k import -v`
Expected: PASS (incluye los tests xlsx preexistentes).

- [ ] **Step 6: Commit**

```bash
git add mt-pricing-backend/app/services/importer/applier.py \
        mt-pricing-backend/tests/integration/test_apply_xml_related.py
git commit -m "feat(importer): applier persiste bloques ricos del xml (create/update)"
```

---

## Task 7: Soporte XML en el flujo async (`PimImporter`)

**Files:**
- Modify: `mt-pricing-backend/app/services/imports/pim_importer.py`
- Test: `mt-pricing-backend/tests/integration/test_pim_importer_xml.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_pim_importer_xml.py
from __future__ import annotations

import os
import tempfile
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db.models.import_run import ImportRun
from app.db.models.product import Product, ProductRelease
from app.services.imports.pim_importer import PimImporter

pytestmark = pytest.mark.asyncio

_NS = "https://mtme-api/schemas/articulos/v1"
_XML = (f'<catalog xmlns="{_NS}"><article><sku>MT-ASYNC-1</sku>'
        f"<name_en>Async Valve</name_en><family>ball_valve</family><dn>25</dn>"
        f'<releases><release market_code="UAE"><local_name>AV</local_name>'
        f"<list_price>50.00</list_price><price_currency>AED</price_currency>"
        f"</release></releases></article></catalog>")


async def test_pim_importer_xml_source(db_session) -> None:
    run = ImportRun(import_type="pim", source_filename="articulos.xml",
                    source_storage_path="x", status="queued")
    db_session.add(run)
    await db_session.flush()

    fd, path = tempfile.mkstemp(suffix=".xml")
    with os.fdopen(fd, "wb") as fh:
        fh.write(_XML.encode("utf-8"))
    try:
        importer = PimImporter(session=db_session, source_path=path,
                               run_id=run.id, actor_id=None)
        result = await importer.run()
    finally:
        os.unlink(path)

    assert result.status in ("completed", "completed_with_errors")
    assert result.inserted_rows == 1
    prod = (await db_session.execute(
        select(Product).where(Product.sku == "MT-ASYNC-1"))).scalar_one()
    assert prod.family == "ball_valve"
    rel = (await db_session.execute(
        select(ProductRelease).where(
            ProductRelease.product_sku == "MT-ASYNC-1"))).scalars().all()
    assert rel[0].market_code == "UAE"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd mt-pricing-backend && uv run pytest tests/integration/test_pim_importer_xml.py -v`
Expected: FAIL — `PimImporter.run()` intenta `load_workbook` sobre XML → marca run failed.

- [ ] **Step 3: Write the implementation**

In `pim_importer.py`, add an XML branch at the top of `run()`. Right after the
`self._run` is loaded and division codes resolved (after line ~111, before the
`if not self.source_path.exists()` block), add:

```python
        if str(self.source_path).lower().endswith(".xml"):
            return await self._run_xml()
```

Then add the new method (uses the shared parser + related_writer):

```python
    async def _run_xml(self) -> ImportRun:
        """Import branch para la plantilla XML de artículos."""
        assert self._run is not None
        from app.services.importer.related_writer import (
            apply_related_entities, pop_related_keys,
        )
        from app.services.importer.xml_parser import XmlParseError, parse_xml_stream

        if not self.source_path.exists():
            if self._storage_bucket:
                await self._download_from_storage()
            else:
                await self._mark_failed(f"Archivo no encontrado: {self.source_path}")
                raise FileNotFoundError(self.source_path)

        try:
            data = self.source_path.read_bytes()
            parse_result = parse_xml_stream(data)
        except XmlParseError as exc:
            await self._mark_failed(f"XML inválido: {exc}")
            return self._run

        self._run.status = "running"
        self._run.started_at = datetime.now(tz=UTC)
        await self.session.commit()

        inserted = updated = skipped = error_rows = 0
        errors: list[dict[str, Any]] = []

        for row in parse_result.rows:
            if row.errors or row.sku is None:
                error_rows += 1
                if len(errors) < MAX_ERRORS_LOGGED:
                    errors.append({"row": row.row_index, "error": "; ".join(row.errors)})
                continue
            try:
                async with self.session.begin_nested():
                    payload = dict(row.payload)
                    related = pop_related_keys(payload)
                    name_en = payload.pop("name_en", None)
                    description_en = payload.pop("description_en", None)
                    marketing_copy_en = payload.pop("marketing_copy_en", None)
                    payload.pop("active", None)
                    sku = payload["sku"]
                    existing = await self._repo.get_by_sku(sku)
                    if existing is None:
                        if self.actor_id is not None:
                            payload["created_by"] = self.actor_id
                            payload["updated_by"] = self.actor_id
                        await self._repo.create(**payload)
                        if name_en:
                            await self._upsert_en_translation(sku, name_en)
                        await apply_related_entities(
                            self.session, sku, related, actor_id=self.actor_id)
                        inserted += 1
                    else:
                        locked = set(existing.manual_locked_fields or [])
                        for field, new_value in payload.items():
                            if field in locked or field in {
                                "sku", "internal_id", "created_at", "created_by"}:
                                continue
                            if getattr(existing, field, None) != new_value:
                                setattr(existing, field, new_value)
                        if name_en and "translations.en" not in locked:
                            await self._upsert_en_translation(sku, name_en)
                        await apply_related_entities(
                            self.session, sku, related, actor_id=self.actor_id)
                        await self.session.flush()
                        updated += 1
            except Exception as exc:
                error_rows += 1
                if len(errors) < MAX_ERRORS_LOGGED:
                    errors.append({"row": row.row_index, "error": str(exc)[:200]})
                logger.warning("PimImporter XML row %d failed: %s", row.row_index, exc)

        self._run.total_rows = len(parse_result.rows)
        self._run.inserted_rows = inserted
        self._run.updated_rows = updated
        self._run.skipped_rows = skipped
        self._run.error_rows = error_rows
        self._run.errors = errors
        self._run.summary = {"inserted": inserted, "updated": updated,
                             "skipped": skipped, "errors": error_rows}
        self._run.finished_at = datetime.now(tz=UTC)
        self._run.status = "completed" if error_rows == 0 else "completed_with_errors"
        await self.session.commit()
        self._cleanup_tmp()
        return self._run
```

> Note: `description_en`/`marketing_copy_en` se extraen para no pasarlos a
> `repo.create` (no son columnas). El upsert completo de la traducción EN
> (con description/marketing) lo cubre `_translations` cuando el XML lo trae.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd mt-pricing-backend && uv run pytest tests/integration/test_pim_importer_xml.py -v`
Expected: PASS (1 passed).

- [ ] **Step 5: Run async importer regression**

Run: `cd mt-pricing-backend && uv run pytest tests -k pim_import -v`
Expected: PASS (los tests xlsx del PimImporter siguen verdes).

- [ ] **Step 6: Commit**

```bash
git add mt-pricing-backend/app/services/imports/pim_importer.py \
        mt-pricing-backend/tests/integration/test_pim_importer_xml.py
git commit -m "feat(importer): PimImporter soporta fuente xml (async)"
```

---

## Task 8: Upload async — content-type por extensión

**Files:**
- Modify: `mt-pricing-backend/app/api/routes/imports.py:418-429`
- Test: `mt-pricing-backend/tests/api/test_imports_upload_xml.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/api/test_imports_upload_xml.py
from __future__ import annotations

from app.api.routes.imports import _content_type_for


def test_content_type_for_xml() -> None:
    assert _content_type_for("articulos.xml") == "text/xml"


def test_content_type_for_xlsx() -> None:
    assert _content_type_for("PIM.xlsx") == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd mt-pricing-backend && uv run pytest tests/api/test_imports_upload_xml.py -v`
Expected: FAIL — `ImportError: cannot import name '_content_type_for'`.

- [ ] **Step 3: Write the implementation**

In `imports.py`, add a module-level helper near the top (after the router):

```python
def _content_type_for(filename: str) -> str:
    if filename.lower().endswith(".xml"):
        return "text/xml"
    return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
```

Then in `upload_and_run_pim`, replace the hardcoded `content_type=(...)` argument
of `upload_bytes(...)` with:

```python
            content_type=_content_type_for(file.filename),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd mt-pricing-backend && uv run pytest tests/api/test_imports_upload_xml.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Regenerate OpenAPI spec (route module changed)**

Run: `cd mt-pricing-backend && uv run python -m app.scripts.export_openapi`
Expected: regenera `_bmad-output/planning-artifacts/mt-api-contract-openapi.json`
(no debería haber diff si las firmas no cambiaron; commitear si lo hay).

- [ ] **Step 6: Commit**

```bash
git add mt-pricing-backend/app/api/routes/imports.py \
        mt-pricing-backend/tests/api/test_imports_upload_xml.py \
        mt-pricing-backend/_bmad-output/planning-artifacts/mt-api-contract-openapi.json
git commit -m "feat(importer): upload async fija content-type text/xml para .xml"
```

---

## Task 9: Frontend — aceptar `.xml` en el wizard de import

**Files:**
- Modify: el input de archivo del wizard de import (buscar con
  `grep -rn "accept=" --include=*.tsx app | grep -i xlsx` y/o
  `grep -rn "spreadsheetml\|.xlsx" --include=*.tsx`).
- Test: ajustar el test del componente si existe.

- [ ] **Step 1: Localizar el control de subida**

Run: `cd <frontend-root> && grep -rn "\.xlsx\|spreadsheetml" --include=*.tsx src | head`
Expected: 1-2 coincidencias del `<input type="file" accept=...>` del wizard.

- [ ] **Step 2: Ampliar el `accept`**

Cambiar el atributo `accept` para incluir XML, por ejemplo:

```tsx
accept=".xlsx,.xml,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/xml"
```

Si hay texto de ayuda tipo "Sube el archivo .xlsx", actualizarlo a
"Sube el archivo .xlsx o .xml".

- [ ] **Step 3: Typecheck + lint**

Run: `cd <frontend-root> && pnpm tsc --noEmit && pnpm lint`
Expected: sin errores.

- [ ] **Step 4: Commit**

```bash
git add <frontend files>
git commit -m "feat(importer-ui): wizard de import acepta archivos .xml"
```

---

## Task 10: Regresión final + cobertura

**Files:** ninguno (solo verificación).

- [ ] **Step 1: Backend suite completa**

Run: `cd mt-pricing-backend && uv run pytest -q`
Expected: PASS, cobertura ≥ 70%.

- [ ] **Step 2: Lint + typecheck backend**

Run: `cd mt-pricing-backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app`
Expected: sin errores.

- [ ] **Step 3: Verificar OpenAPI sin drift**

Run: `cd mt-pricing-backend && uv run python -m app.scripts.export_openapi && git diff --exit-code _bmad-output/planning-artifacts/mt-api-contract-openapi.json`
Expected: exit 0 (sin cambios pendientes).

- [ ] **Step 4: Documentar la limitación de idempotencia en el README de la plantilla**

Añadir al final de `docs/templates/articulos/README.md`:

```markdown
## Re-importación (importante)

En una re-importación, los bloques anidados (traducciones, releases, conversiones
UoM, dimensiones por norma) solo se vuelven a aplicar si la fila tiene cambios en
campos escalares del producto. Si solo cambiaste datos anidados, modifica también
algún campo escalar (p. ej. `revision`) para forzar la actualización.
```

- [ ] **Step 5: Commit**

```bash
git add docs/templates/articulos/README.md
git commit -m "docs(articulos): documentar idempotencia de bloques en re-importación"
```

---

## Self-Review (completado por el autor del plan)

- **Cobertura del spec:** §3 componentes → Tasks 1-9; §4 contrato claves
  reservadas → Tasks 2,4,6,7; §5 flujo → Tasks 5,7; §6 validación tolerante →
  Tasks 1,5; §7 idempotencia v1 → Tasks 6,7,10(step4); §8 endpoints/OpenAPI →
  Tasks 8,10; §9 pruebas → tests en cada task + Task 10.
- **Sin placeholders:** todo paso de código incluye el código real.
- **Consistencia de tipos:** `parse_xml_stream(bytes|BinaryIO) -> ParseResult`,
  `parse_source(...) -> ParseResult`, `apply_related_entities(session, sku,
  payload, *, actor_id)`, `pop_related_keys(payload) -> dict` usados de forma
  idéntica en Tasks 3-7. `ParsedRow`/`ParseResult`/`RowDiff` reutilizados del
  código existente sin redefinir.
- **Riesgo verificado:** `RowDiff` conserva `payload` en UPDATE (differ.py:178-184),
  por eso Task 6 puede leer los bloques ricos en el branch UPDATE.
```

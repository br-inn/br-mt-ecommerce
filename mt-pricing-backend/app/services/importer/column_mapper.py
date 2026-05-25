"""Column mapping canónico ``PIM completo.xlsx`` → schema `products`.

Fuente de verdad: ``_bmad-output/planning-artifacts/sprint0-pim-column-mapping.md``
(Task 2). Verificado contra el archivo real (5085 rows x 17 cols, headers
exactos coinciden con la spec).

Dos mapeos:
- :data:`EXCEL_COL_TO_FIELD` — header literal → spec del campo destino con
  metadatos de transformación (cast, scale, target table/column, JSONB key).
- :data:`EXPECTED_HEADERS` — orden esperado del header (para validación pre-parse).

Targets soportados en S2 (Fase 1a):
- ``products.<col>`` — escalar simple.
- ``products.dimensions.<key>`` — JSONB key sobre ``products.dimensions``.
- ``products.packaging.<key>`` — JSONB key sobre ``products.packaging``.
- ``products.specs.<key>`` — JSONB key (se reserva por simetría).
- ``product_eans`` — multi-EAN; en S2 los conservamos en
  ``products.specs.eans`` (lista) hasta que llegue la migración de tabla
  ``product_eans`` (Apéndice B sprint2-backlog).

Reglas defaults (sprint0 §4.4):
- ``brand`` default ``MT``.
- ``family`` default ``unclassified``.
- ``data_quality`` default ``partial``; promover a ``complete`` si se cumplen
  campos obligatorios (validación post-parse en :mod:`differ`).
- ``active`` default ``true``.
- ``manual_locked_fields`` default ``[]``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any


@dataclass(frozen=True, slots=True)
class ColumnSpec:
    """Spec por columna Excel: cómo se castea y dónde se guarda."""

    excel_header: str
    target_table: str  # 'products' | 'product_eans'
    target_column: str | None  # column en target_table o None si va a JSONB
    jsonb_key: str | None = None  # key dentro de JSONB (cuando target_column='specs', etc.)
    jsonb_field: str | None = None  # 'dimensions' | 'packaging' | 'specs'
    cast: str = "text"  # 'text' | 'int' | 'decimal' | 'cm_to_mm' | 'ean'
    nullable: bool = True
    notes: str = ""


# ---------------------------------------------------------------------------
# Casts
# ---------------------------------------------------------------------------
def _cast_text(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _cast_int(v: Any) -> int | None:
    if v is None or v == "":
        return None
    try:
        # Algunos llegan como float ("250.0") o como int ya.
        return int(float(str(v).strip()))
    except (ValueError, TypeError) as exc:
        raise ImportCastError(f"Valor no convertible a int: {v!r}") from exc


def _cast_decimal(v: Any) -> Decimal | None:
    if v is None or v == "":
        return None
    try:
        return Decimal(str(v).strip())
    except (InvalidOperation, ValueError) as exc:
        raise ImportCastError(f"Valor no convertible a decimal: {v!r}") from exc


def _cast_cm_to_mm(v: Any) -> Decimal | None:
    """Multiplica x10 para uniformidad mm (sprint0 §4.1)."""
    d = _cast_decimal(v)
    if d is None:
        return None
    return d * Decimal(10)


def _cast_ean(v: Any) -> str | None:
    """EAN/GTIN — sólo dígitos, longitud 13 o 14. None si vacío."""
    s = _cast_text(v)
    if s is None:
        return None
    s = "".join(ch for ch in s if ch.isdigit())
    if not s:
        return None
    if len(s) not in (8, 12, 13, 14):
        raise ImportCastError(f"EAN inválido (longitud {len(s)}): {v!r}")
    return s


CASTERS: dict[str, Callable[[Any], Any]] = {
    "text": _cast_text,
    "int": _cast_int,
    "decimal": _cast_decimal,
    "cm_to_mm": _cast_cm_to_mm,
    "ean": _cast_ean,
}


class ImportCastError(ValueError):
    """Error de cast de un valor de celda — no detiene el parse global, sólo la fila."""


# ---------------------------------------------------------------------------
# Mapping canónico (17 columnas)
# ---------------------------------------------------------------------------
EXCEL_COL_TO_FIELD: dict[str, ColumnSpec] = {
    "Referencia de variante": ColumnSpec(
        excel_header="Referencia de variante",
        target_table="products",
        target_column="sku",
        cast="text",
        nullable=False,
        notes="PK natural, conservar zero-padding y mixto alfanumérico.",
    ),
    "Cod.Intrastat - AX": ColumnSpec(
        excel_header="Cod.Intrastat - AX",
        target_table="products",
        target_column="intrastat_code",
        cast="text",
    ),
    "Nombre ERP - AX": ColumnSpec(
        excel_header="Nombre ERP - AX",
        target_table="products",
        target_column="erp_name",
        cast="text",
        notes="NO mapear directo a name_en (BR-1a-DQ-PIM-01).",
    ),
    "INDIVIDUAL EAN CODE": ColumnSpec(
        excel_header="INDIVIDUAL EAN CODE",
        target_table="products",
        target_column="specs",
        jsonb_field="specs",
        jsonb_key="ean_individual",
        cast="ean",
        notes="S2: lo guardamos en specs.ean_individual hasta migrar a product_eans.",
    ),
    "weight unit": ColumnSpec(
        excel_header="weight unit",
        target_table="products",
        target_column="specs",
        jsonb_field="specs",
        jsonb_key="weight_gross_kg",
        cast="decimal",
    ),
    "net weight unit": ColumnSpec(
        excel_header="net weight unit",
        target_table="products",
        target_column="weight",
        cast="decimal",
        notes="Persistido como products.weight (peso neto canónico).",
    ),
    "High mm": ColumnSpec(
        excel_header="High mm",
        target_table="products",
        target_column="dimensions",
        jsonb_field="dimensions",
        jsonb_key="high_mm",
        cast="decimal",
    ),
    "Wide mm": ColumnSpec(
        excel_header="Wide mm",
        target_table="products",
        target_column="dimensions",
        jsonb_field="dimensions",
        jsonb_key="wide_mm",
        cast="decimal",
    ),
    "Deep mm": ColumnSpec(
        excel_header="Deep mm",
        target_table="products",
        target_column="dimensions",
        jsonb_field="dimensions",
        jsonb_key="deep_mm",
        cast="decimal",
    ),
    "EAN CODE BOX": ColumnSpec(
        excel_header="EAN CODE BOX",
        target_table="products",
        target_column="specs",
        jsonb_field="specs",
        jsonb_key="ean_box",
        cast="ean",
    ),
    "qty x box": ColumnSpec(
        excel_header="qty x box",
        target_table="products",
        target_column="packaging",
        jsonb_field="packaging",
        jsonb_key="qty_per_box",
        cast="int",
    ),
    "Alto caja (cm) - AX": ColumnSpec(
        excel_header="Alto caja (cm) - AX",
        target_table="products",
        target_column="packaging",
        jsonb_field="packaging",
        jsonb_key="box_high_mm",
        cast="cm_to_mm",
        notes="cm to mm (x10) para uniformidad con dimensiones de producto.",
    ),
    "Ancho caja (cm) - AX": ColumnSpec(
        excel_header="Ancho caja (cm) - AX",
        target_table="products",
        target_column="packaging",
        jsonb_field="packaging",
        jsonb_key="box_wide_mm",
        cast="cm_to_mm",
    ),
    "Largo caja (cm) - AX": ColumnSpec(
        excel_header="Largo caja (cm) - AX",
        target_table="products",
        target_column="packaging",
        jsonb_field="packaging",
        jsonb_key="box_deep_mm",
        cast="cm_to_mm",
    ),
    "EAN CODE INNER BOX": ColumnSpec(
        excel_header="EAN CODE INNER BOX",
        target_table="products",
        target_column="specs",
        jsonb_field="specs",
        jsonb_key="ean_inner_box",
        cast="ean",
    ),
    "MOQ INNER BOX": ColumnSpec(
        excel_header="MOQ INNER BOX",
        target_table="products",
        target_column="packaging",
        jsonb_field="packaging",
        jsonb_key="moq_inner_box",
        cast="int",
    ),
    "X PALLET": ColumnSpec(
        excel_header="X PALLET",
        target_table="products",
        target_column="packaging",
        jsonb_field="packaging",
        jsonb_key="x_pallet",
        cast="int",
    ),
}

EXPECTED_HEADERS: tuple[str, ...] = tuple(EXCEL_COL_TO_FIELD.keys())


# ---------------------------------------------------------------------------
# Defaults aplicados a cada row
# ---------------------------------------------------------------------------
ROW_DEFAULTS: dict[str, Any] = {
    "brand": "MT",
    "family": "unclassified",
    "data_quality": "partial",
    "active": True,
    "manual_locked_fields": [],
    "weight_unit": "kg",
}


def map_row(
    excel_row: tuple[Any, ...] | list[Any],
    headers: tuple[str, ...] | list[str] = EXPECTED_HEADERS,
) -> tuple[dict[str, Any], list[str]]:
    """Aplica el mapping a una fila de Excel.

    Devuelve ``(payload_dict, errors_list)``:
    - ``payload_dict``: representación lista para INSERT/UPDATE en `products`,
      con JSONB ya colapsados (``dimensions``, ``packaging``, ``specs``).
    - ``errors_list``: lista de mensajes de cast/validación; si no es vacía la
      fila se considera errónea y NO debe persistirse.

    Aplica defaults de :data:`ROW_DEFAULTS` para campos no presentes en PIM
    (brand, family, etc.).
    """
    payload: dict[str, Any] = dict(ROW_DEFAULTS)
    errors: list[str] = []
    jsonb_buckets: dict[str, dict[str, Any]] = {
        "dimensions": {},
        "packaging": {},
        "specs": {},
    }

    if len(excel_row) < len(headers):
        errors.append(f"Fila con {len(excel_row)} columnas; esperadas {len(headers)}.")
        return payload, errors

    for idx, header in enumerate(headers):
        spec = EXCEL_COL_TO_FIELD.get(header)
        if spec is None:
            continue  # Header desconocido — ignora silenciosamente.
        raw = excel_row[idx] if idx < len(excel_row) else None
        try:
            casted = CASTERS[spec.cast](raw)
        except ImportCastError as exc:
            errors.append(f"col {header!r}: {exc}")
            continue
        if casted is None and not spec.nullable:
            errors.append(f"col {header!r}: requerido y vino vacío.")
            continue
        if spec.jsonb_field is not None and spec.jsonb_key is not None:
            if casted is not None:
                # Decimals → str para serializar JSON-friendly.
                value: Any = str(casted) if isinstance(casted, Decimal) else casted
                jsonb_buckets[spec.jsonb_field][spec.jsonb_key] = value
        elif spec.target_column is not None:
            payload[spec.target_column] = casted

    # Colapsa JSONB buckets sólo si tienen al menos una key.
    for k, v in jsonb_buckets.items():
        if v:
            payload[k] = v

    # name_en es obligatorio en ProductCreate (BRECHA-CAT-01).
    # Si no viene explícito, se rellena desde erp_name; si erp_name también está
    # vacío, se emite un error para que la fila se rechace.
    if not payload.get("name_en"):
        erp = payload.get("erp_name") or ""
        if erp:
            payload["name_en"] = erp
        else:
            errors.append("name_en: requerido y no se pudo inferir desde erp_name.")

    return payload, errors


# ---------------------------------------------------------------------------
# Nuevos casters para mapeo flexible
# ---------------------------------------------------------------------------
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
    except (ValueError, TypeError) as exc:
        raise ImportCastError(f"Valor no convertible a porcentaje: {v!r}") from exc
    if not (0 <= n <= 100):
        raise ImportCastError(f"Porcentaje fuera de rango [0,100]: {v!r}")
    return n


# Registrar los nuevos casters.
CASTERS["bool_check"] = _cast_bool_check
CASTERS["percent"] = _cast_percent


def map_row_with_mapping(
    excel_row: tuple[Any, ...] | list[Any],
    headers: list[str],
    mapping: list[Any],  # list[ColumnMappingItem] — import lazy para evitar ciclos
) -> tuple[dict[str, Any], list[str]]:
    """Mapea una fila usando un mapping flexible (lista de ColumnMappingItem).

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
            casted = caster(raw)  # type: ignore[no-untyped-call]
        except ImportCastError as exc:
            errors.append(f"col {item.excel_col!r}: {exc}")
            continue

        if casted is None:
            continue

        field = item.target_field

        if "." in field:
            prefix, key = field.split(".", 1)
            if prefix in jsonb_buckets:
                stored: Any = str(casted) if isinstance(casted, Decimal) else casted
                jsonb_buckets[prefix][key] = stored
            elif prefix == "translations":
                # translations.en → name_en, translations.es → name_es, etc.
                # Applier strips these from payload and upserts to product_translations.
                payload[f"name_{key}"] = casted
        else:
            payload[field] = casted

    for k, v in jsonb_buckets.items():
        if v:
            payload[k] = v

    return payload, errors


__all__ = [
    "CASTERS",
    "EXCEL_COL_TO_FIELD",
    "EXPECTED_HEADERS",
    "ROW_DEFAULTS",
    "ColumnSpec",
    "ImportCastError",
    "map_row",
    "map_row_with_mapping",
]

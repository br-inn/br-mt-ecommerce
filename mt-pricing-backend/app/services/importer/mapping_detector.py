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
    first = str(non_empty[0]).strip() if non_empty else ""
    if len(non_empty) < 3:
        # A row with < 3 non-empty cells is never a header.
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
    try:
        ws = wb[wb.sheetnames[0]]

        all_rows: list[tuple[Any, ...]] = []
        for i, row in enumerate(ws.iter_rows(values_only=True)):
            if i >= max_scan_rows + 5:
                break
            all_rows.append(row)
    finally:
        wb.close()

    header_idx: int | None = None
    for i, row in enumerate(all_rows[:max_scan_rows]):
        if _is_header_row(row):
            header_idx = i
            break

    if header_idx is None:
        raise ValueError(
            f"No header row detected in the first {max_scan_rows} rows of the xlsx file."
        )

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

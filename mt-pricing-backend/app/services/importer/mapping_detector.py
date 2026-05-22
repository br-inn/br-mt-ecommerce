"""Detección automática de estructura xlsx y propuesta de mapeo via LLM."""

from __future__ import annotations

import io
import json
import logging
import re
from dataclasses import dataclass
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
SCALAR_FIELDS: frozenset[str] = frozenset(
    {
        "sku",
        "family",
        "subfamily",
        "type",
        "erp_name",
        "intrastat_code",
        "hs_code",
        "connection",
        "brand",
        "weight",
        "bore_mm",
        "pressure_max_bar",
        "temp_min_c",
        "temp_max_c",
        "series",
        "material",
        "dn",
        "pn",
        "size",
        "revision",
        "external_url",
        "gtin",
        "dimensional_standard",
        "country_of_origin",
    }
)

# Prefijos JSONB válidos (el sufijo es la clave dentro del bucket).
JSONB_PREFIXES: frozenset[str] = frozenset({"dimensions", "packaging", "specs"})


@dataclass(frozen=True, slots=True)
class ColumnMappingItem:
    """Mapeo de una columna Excel a un campo de `products`."""

    excel_col: str
    target_field: str  # 'sku' | 'family' | 'dimensions.high_mm' | 'specs.ean_box' | '_skip'
    transform: str  # uno de AVAILABLE_TRANSFORMS
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
    for row in all_rows[header_idx + 1 :]:
        if any(v is not None and v != "" for v in row):
            samples.append(list(row))
        if len(samples) >= 5:
            break

    return header_idx, headers, samples


_LLM_MODEL = "claude-sonnet-4-6"

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

Available transforms:
  text        plain text / string
  int         integer number
  decimal     decimal / float
  cm_to_mm    multiply x10 (centimeters to millimeters)
  ean         EAN barcode (digits only, valid lengths 8/12/13/14)
  bool_check  truthy check: "✓", "yes", "1", "true" → true; else false
  percent     numeric percentage stored as integer 0-100
"""


def suggest_mapping(
    headers: list[str],
    sample_rows: list[list[Any]],
) -> list[ColumnMappingItem]:
    """Llama a Claude para proponer el mapeo de columnas Excel → campos product.

    Devuelve lista vacía si el LLM falla o devuelve JSON inválido (tolerante).
    """
    import anthropic

    # Tabla columna → valores de muestra (todas las columnas, no truncadas).
    col_samples: list[str] = []
    for j, h in enumerate(headers):
        vals = [repr(row[j]) if j < len(row) else "None" for row in sample_rows[:3]]
        col_samples.append(f"  {h!r}: {', '.join(vals)}")
    samples_text = "\n".join(col_samples)

    prompt = (
        f"You are a product data mapping assistant for an industrial PVF "
        f"(pipes, valves, fittings) manufacturer PIM system.\n\n"
        f"Given these Excel column headers and their sample values, propose the "
        f"best mapping from each Excel column to a product database field.\n\n"
        f"Use the actual sample values to infer the correct field and transform. "
        f"For example: a column with values like 'DN25', 'DN40' maps to 'dn' with "
        f"transform 'text'; a column with values in cm (e.g. 12.5) that represents "
        f"a physical dimension maps to dimensions.* with transform 'cm_to_mm'.\n"
        f"For multi-language name columns (e.g. 'Nombre ES', 'Name EN', 'Nome IT'), "
        f"use translations.<lang> (translations.es, translations.en, translations.it, etc.).\n"
        f"For certification columns (e.g. 'Normas', 'Certifications', 'CE Mark', "
        f"'Homologaciones'), use 'certifications'.\n\n"
        f"{_AVAILABLE_FIELDS_DOC}\n\n"
        f"Column headers with sample values (up to 3 rows):\n{samples_text}\n\n"
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
        text = message.content[0].text.strip()  # type: ignore[union-attr]
        # Strip markdown code fences (e.g. ```json ... ```)
        text = re.sub(r"^```[^\n]*\n?", "", text, flags=re.MULTILINE).strip()
        data = json.loads(text)
        if not isinstance(data, list):
            logger.warning(
                "suggest_mapping: LLM returned %s instead of a JSON array"
                " — returning empty mapping",
                type(data).__name__,
            )
            return []
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
    except Exception:
        logger.exception("suggest_mapping LLM call failed — returning _skip fallback")
        return [
            ColumnMappingItem(
                excel_col=h,
                target_field="_skip",
                transform="text",
                confidence=0.0,
                notes="LLM no disponible — mapeo manual requerido",
            )
            for h in headers
        ]

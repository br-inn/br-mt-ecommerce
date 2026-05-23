"""Mapping fila Excel `PIM completo.xlsx` → payload `products`.

Wrapper sobre :func:`app.services.importer.column_mapper.map_row` (la fuente de
verdad canónica del mapping, validada contra el PIM real 5085 rows x 17 cols).

Diferencia: `map_row` tradicional asume el header literal validado por
``parse_xlsx_stream``. Aquí exponemos también :func:`map_pim_row_to_product`
que lanza ``ValueError`` si el SKU está vacío y aplica el cap a 100 errores
del lado del importer batch.

Comentarios en español; nombres en inglés.
"""

from __future__ import annotations

from typing import Any

from app.services.importer.column_mapper import EXPECTED_HEADERS, map_row


def map_pim_row_to_product(row: tuple[Any, ...] | list[Any]) -> dict[str, Any]:
    """Mapea una fila tuple del xlsx PIM a payload listo para `Product`.

    Reglas:
    - Aplica el mapping canónico (column_mapper.EXCEL_COL_TO_FIELD).
    - Si la fila no tiene ``sku`` → ``ValueError`` (la fila se loggea como
      error_row en el ImportRun pero no aborta el run).
    - Si hay errores de cast (e.g. EAN inválido) — los recolectamos en
      ``payload['_row_errors']`` para que el importer los capture sin perder
      la fila completa (los campos casteados OK sí persisten).

    Returns:
        ``dict`` con campos de `Product` + claves JSONB ``dimensions``,
        ``packaging``, ``specs``. Incluye ``_row_errors`` (list[str]) si hubo
        cast errors no fatales.
    """
    payload, errors = map_row(row, EXPECTED_HEADERS)
    sku = payload.get("sku")
    if not sku or not str(sku).strip():
        # SKU vacio == fila inutil — el importer la cuenta como error_row.
        raise ValueError("SKU vacio (col 'Referencia de variante').")

    # Si erp_name está vacío, marcar data_quality como partial.
    if not payload.get("erp_name"):
        payload["data_quality"] = "partial"

    if errors:
        # Errores no-fatales recolectados para inspeccion. La fila aún se
        # persiste con los campos OK (best-effort).
        payload["_row_errors"] = errors
    return payload

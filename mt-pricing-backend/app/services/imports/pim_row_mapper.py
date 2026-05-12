"""Mapping fila Excel `PIM completo.xlsx` → payload `products`.

Wrapper sobre :func:`app.services.importer.column_mapper.map_row` (la fuente de
verdad canónica del mapping, validada contra el PIM real 5085 rows × 17 cols).

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

    # Backfill `name_en` cuando erp_name vino vacío (22.2% del PIM real). El
    # column_mapper canónico marca esto como error fatal (refleja el escenario
    # del wizard sincrono que sí lo reporta como error en Pantalla 10), pero
    # para el batch importer preferimos persistir con un placeholder y dejar
    # data_quality='partial' para que TI/Comercial lo backfilleen vía LLM o
    # manualmente.
    #
    # Fase B (mig 065): name_en ya no es columna de products. El payload sigue
    # llevándolo y el ProductService.create_product lo extrae para upsertear en
    # product_translations(lang='en') vía _extract_en_translation_payload.
    if "name_en" not in payload or not payload.get("name_en"):
        payload["name_en"] = f"[Producto sin nombre {sku}]"
        payload["data_quality"] = "partial"
        # Removemos del error list la entrada de "name_en no derivable" porque
        # el placeholder la resuelve para persistencia (deja la fila usable).
        errors = [e for e in errors if "name_en no derivable" not in e]

    if errors:
        # Errores no-fatales recolectados para inspeccion. La fila aún se
        # persiste con los campos OK (best-effort).
        payload["_row_errors"] = errors
    return payload

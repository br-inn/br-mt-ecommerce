"""Importer compatibilidades materiales (US-1A-06-03 — Sprint 3).

Excel ``Copia de Compatibilidad de Materiales MT V4.xlsx`` (~657 filas) con la
estructura:

    producto_descriptor | temperatura_c | <material_1> | <material_2> | ... | <material_N>

Cada celda de las columnas material_X contiene el flag de compatibilidad
(``OK``, ``X``, ``-``, vacío). El parser persiste:

- ``producto_descriptor`` TEXT (PK natural junto a ``temperatura_c``).
- ``temperatura_c`` NUMERIC.
- ``compatibilities`` JSONB con ``{material_name: flag}``.

Modo ``apply``:
- ``mode='replace'`` (default) — TRUNCATE + INSERT (idempotente, tabla referencial).
- ``mode='append'`` — sólo INSERT (útil para diffs en futuros sprints).

NO expone API de consulta — el matching pipeline (US-1A-09-01-S3) la consume
directo. La UI tab Compatibilidades es S4.
"""

from __future__ import annotations

from app.services.importer_materials.applier import (
    ApplyMaterialsResult,
    apply_material_rows,
)
from app.services.importer_materials.parser import (
    MaterialRow,
    MaterialsParseResult,
    parse_materials_xlsx_stream,
)

__all__ = [
    "ApplyMaterialsResult",
    "MaterialRow",
    "MaterialsParseResult",
    "apply_material_rows",
    "parse_materials_xlsx_stream",
]

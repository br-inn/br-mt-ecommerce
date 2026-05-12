"""Importer service — wizard PIM completo.xlsx (US-1A-06-01).

Componentes:
- :mod:`column_mapper` — dict canónico ``EXCEL_COL_TO_FIELD`` (sprint0 mapping).
- :mod:`parser` — openpyxl streaming reader; emite ``ParsedRow`` objects.
- :mod:`differ` — compara ``ParsedRow`` vs estado DB; respeta ``manual_locked_fields``.
- :mod:`applier` — aplica diffs en chunks de 1000 rows con savepoints.

Flow público desde el router (``app/api/routes/imports.py``):
    1. ``POST /imports/preview``  → :class:`ImporterService.preview` (parser + differ).
    2. ``POST /imports/{id}/apply`` → :class:`ImporterService.apply` (chunked).
    3. ``GET  /imports/{id}/status`` → memoria/run-state.
    4. ``GET  /imports/{id}/report`` → CSV/JSON con detalle por row.

S2: backend no persiste el run en BD (modelo ``import_runs`` queda para
sprint posterior si Agente 1 publica la migración). En su lugar, mantiene
runs en memoria por proceso (suficiente para test/demo monolítico) — es
intercambiable por un repo cuando llegue.
"""

from __future__ import annotations

from app.services.importer.column_mapper import (
    EXCEL_COL_TO_FIELD,
    EXPECTED_HEADERS,
    map_row,
)
from app.services.importer.differ import RowAction, RowDiff, compute_diff
from app.services.importer.importer_service import ImporterService, ImportRunState, RejectedRow
from app.services.importer.parser import ParsedRow, parse_xlsx_stream

__all__ = [
    "EXCEL_COL_TO_FIELD",
    "EXPECTED_HEADERS",
    "ImportRunState",
    "ImporterService",
    "ParsedRow",
    "RejectedRow",
    "RowAction",
    "RowDiff",
    "compute_diff",
    "map_row",
    "parse_xlsx_stream",
]

"""Importer batch costos (US-1A-06-02 — Sprint 3).

Reusa el patrón S2 de :mod:`app.services.importer` (PIM) pero opera sobre el
Excel de costos: una fila = un coste para (SKU, scheme, supplier?). El
``ImporterCostsService`` orquesta preview/apply/status/report en memoria con
el mismo contrato del wizard genérico.

Componentes:
- :mod:`parser` — openpyxl streaming → :class:`CostRow`.
- :mod:`differ` — compara contra costos activos (matching SKU+scheme+supplier),
  reporta huérfanos (``sku_not_in_pim``, ``scheme_unknown``, ``supplier_unknown``).
- :mod:`applier` — invoca ``CostService.create_cost`` por fila, FX as-of del
  batch. Mock-friendly (acepta ``cost_service`` inyectado).
- :mod:`importer_service` — fachada igual a la de PIM, distinto kind.

Persistencia: reusa la tabla ``import_runs`` (kind='costs') más una columna
nueva ``orphans`` JSONB añadida en migración ``20260507_019``.
"""

from __future__ import annotations

from app.services.importer_costs.applier import (
    ApplyCostsResult,
    CostsApplier,
    apply_cost_diffs,
)
from app.services.importer_costs.differ import (
    CostDiff,
    CostRowAction,
    OrphanReport,
    compute_cost_diff,
)
from app.services.importer_costs.importer_service import (
    ImporterCostsRunState,
    ImporterCostsService,
)
from app.services.importer_costs.parser import (
    EXPECTED_COSTS_HEADERS,
    CostRow,
    CostsParseResult,
    parse_costs_xlsx_stream,
)

__all__ = [
    "EXPECTED_COSTS_HEADERS",
    "ApplyCostsResult",
    "CostDiff",
    "CostRow",
    "CostRowAction",
    "CostsApplier",
    "CostsParseResult",
    "ImporterCostsRunState",
    "ImporterCostsService",
    "OrphanReport",
    "apply_cost_diffs",
    "compute_cost_diff",
    "parse_costs_xlsx_stream",
]

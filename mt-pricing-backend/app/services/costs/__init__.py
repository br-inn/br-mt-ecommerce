"""Costs services — US-1A-04-02 / US-1A-04-03 motor de costes.

Componentes:
- ``cost_service.CostService`` — create/update versionados, list_by_sku,
  compute_landed_aed (helper Python para previews; en BD es trigger).
- ``breakdown_validator.validate_breakdown`` — valida claves del JSONB
  contra ``schemes.cost_components_template``.
"""

from __future__ import annotations

from app.services.costs.breakdown_validator import (
    BreakdownValidationResult,
    validate_breakdown,
)
from app.services.costs.cost_service import CostService

__all__ = [
    "BreakdownValidationResult",
    "CostService",
    "validate_breakdown",
]

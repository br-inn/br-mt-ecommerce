"""Pydantic schemas para `schemes` — US-1A-04-S4.

Expone el modelo `CostScheme` (tabla `schemes`) vía GET /api/v1/schemes
y GET /api/v1/schemes/{code} para que el frontend pueda leer
`cost_components_template` de forma dinámica en lugar de hardcodearlo.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class CostComponentsTemplate(BaseModel):
    """Estructura de `cost_components_template` JSONB del scheme.

    Campos definidos por el seed de la tabla `schemes` (US-1A-04-01).
    """

    model_config = ConfigDict(populate_by_name=True)

    required: list[str] = []
    optional: list[str] = []


class SchemeResponse(BaseModel):
    """Representación pública de un scheme de coste."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    code: str
    name: str
    description: str | None = None
    cost_components_template: CostComponentsTemplate
    active: bool

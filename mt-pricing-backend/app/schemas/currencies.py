"""Pydantic schemas para `currencies` admin (US-1A-05-01-S3).

S2 dejó la tabla seed con AED/USD/EUR/SAR. S3 cierra el admin con:
- GET listing
- PATCH active (activate/deactivate)

NO hay endpoints de creación de currencies en S3 (riesgo: monedas sin FX rates
asociados rompen el motor de costes). Sólo activate/deactivate del seed.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CurrencyResponse(BaseModel):
    """Response estándar para listado/PATCH currencies."""

    model_config = ConfigDict(from_attributes=True, extra="ignore")

    code: str
    name: str
    symbol: str | None = None
    decimals: int
    is_base: bool
    active: bool
    created_at: datetime


class CurrencyActivePatch(BaseModel):
    """PATCH /currencies/{code}/active — payload mínimo (`active` boolean)."""

    model_config = ConfigDict(extra="forbid")

    active: bool = Field(description="Activar (true) o desactivar (false) la moneda.")
    reason: str | None = Field(
        default=None,
        max_length=512,
        description="Motivo opcional (queda en `audit_events.reason`).",
    )


__all__ = ["CurrencyResponse", "CurrencyActivePatch"]

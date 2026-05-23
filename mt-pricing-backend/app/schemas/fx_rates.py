"""Pydantic schemas para `fx_rates` admin (US-1A-05-02 + US-1A-05-03).

Independiente de `app.schemas.pricing` (que ya tiene `FXRateCreate`/`Response`
acoplados al endpoint legacy `/api/v1/pricing/fx-rates`). Estos schemas son los
que consume el endpoint NUEVO `/api/v1/fx-rates` (US-1A-05-03).

Diferencias con el schema legacy:
- `source` validado contra el set `{manual, cbuae, ecb, imported}` (alineado al
  CHECK constraint en migración 017).
- `effective_from` requerido (no se acepta default = now() — el caller debe ser
  explícito para que el trigger valide retroactividad correctamente).
- `allow_retroactive` opcional, sólo permitido a admin con audit reason.
- `created_by` se popula desde el actor JWT (no del payload).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
)

CURRENCY_CODE_REGEX = r"^[A-Z]{3}$"

CurrencyCodeStr = Annotated[
    str,
    StringConstraints(min_length=3, max_length=3, pattern=CURRENCY_CODE_REGEX),
]

FX_SOURCES = ("manual", "cbuae", "ecb", "imported")
FXSourceLiteral = Literal["manual", "cbuae", "ecb", "imported"]


class FXRateCreate(BaseModel):
    """POST /api/v1/fx-rates — payload de creación."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    from_code: CurrencyCodeStr = Field(
        alias="from_currency",
        description=(
            "Código ISO-4217 de la moneda origen. Aceptamos también el alias "
            "`from_currency` para compatibilidad con el legacy schema."
        ),
    )
    to_code: CurrencyCodeStr = Field(
        alias="to_currency",
        description="Código ISO-4217 de la moneda destino.",
    )
    rate: Decimal = Field(
        gt=0,
        description=(
            "Tasa positiva (`from→to`). Si `from_code == to_code` el trigger "
            "fuerza 1.0 (caso identidad)."
        ),
    )
    effective_from: datetime = Field(
        description=(
            "Fecha/hora de inicio de vigencia. El trigger cierra automáticamente "
            "el rate previo del mismo par con `effective_to = NEW.effective_from`."
        ),
    )
    source: FXSourceLiteral = Field(
        default="manual",
        description=(
            "Origen del rate. Sólo manual habilitado en S3 — cbuae/ecb/imported "
            "para integraciones futuras."
        ),
    )
    allow_retroactive: bool = Field(
        default=False,
        description=(
            "Si true permite `effective_from < último rate vigente`. Reservado a "
            "TI/admin con audit reason; el endpoint exige rol admin si se usa."
        ),
    )
    reason: str | None = Field(
        default=None,
        max_length=512,
        description="Motivo (queda en audit). Requerido si allow_retroactive=true.",
    )

    @field_validator("from_code", "to_code", mode="before")
    @classmethod
    def _upper(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip().upper()
        return v


class FXRateResponse(BaseModel):
    """Response estándar para listado / mutación."""

    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: UUID
    # Mantenemos los nombres del schema BD existente (`from_currency`/`to_currency`)
    # para no romper el frontend legacy del divisas page. El nuevo endpoint los
    # acepta por alias en input también (ver FXRateCreate).
    from_currency: str
    to_currency: str
    rate: Decimal
    effective_from: datetime
    effective_to: datetime | None = None
    source: str | None = None
    created_by: UUID | None = None
    created_at: datetime


__all__ = ["FX_SOURCES", "FXRateCreate", "FXRateResponse", "FXSourceLiteral"]

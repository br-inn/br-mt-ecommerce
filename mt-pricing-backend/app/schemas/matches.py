"""Pydantic schemas — Match candidates API.

Alineado con `app/db/models/match_candidate.py` y el patrón de los demás
schemas (extra=forbid, from_attributes=True).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

ChannelStr = Literal["amazon_uae", "noon_uae"]
KindStr = Literal["peer", "drop", "unknown"]
StatusStr = Literal["pending", "validated", "discarded"]


SkuStr = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=64,
        strip_whitespace=True,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9\-_]{0,63}$",
    ),
]


class MatchCandidateBase(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    product_sku: str
    channel: ChannelStr
    external_id: str
    brand: str | None = None
    title: str
    price_aed: Decimal | None = None
    delivery_text: str | None = None
    specs_jsonb: dict[str, Any] = Field(default_factory=dict)
    kind: KindStr = "unknown"
    score: int = Field(ge=0, le=100)
    status: StatusStr = "pending"
    image_url: str | None = None
    source_url: str | None = None
    delivery_category: str | None = None
    price_confidence_score: int | None = Field(default=None, ge=0, le=100)
    pack_units: int | None = Field(
        default=None,
        ge=1,
        description="Unidades por pack. NULL/1 = precio individual. Si >1, precio/unidad = price_aed / pack_units.",
    )


class MatchCandidateResponse(MatchCandidateBase):
    """Item devuelto por GET /matches y endpoints de transición."""

    id: UUID
    validated_by: UUID | None = None
    validated_at: datetime | None = None
    discarded_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class MatchCandidateDetail(MatchCandidateResponse):
    """Detalle — incluye scoring breakdown extraído de specs_jsonb._scoring."""

    scoring: dict[str, Any] | None = Field(
        default=None,
        description="Breakdown de scoring extraído de specs_jsonb._scoring.",
    )


class MatchRefreshResponse(BaseModel):
    """Respuesta del POST /matches/{sku}/refresh."""

    model_config = ConfigDict(extra="forbid")

    sku: str
    refreshed_count: int = Field(ge=0)
    candidates: list[MatchCandidateResponse]


class MatchRefreshJobResponse(BaseModel):
    """Respuesta 202 del POST /matches/{sku}/refresh — el scraping corre en background.

    ``candidates`` contiene el estado actual de la DB (stale) para que la UI
    tenga algo que mostrar mientras espera. Usar GET /matches/{sku}/refresh/status/{task_id}
    para saber cuando terminó y obtener los candidatos actualizados.
    """

    model_config = ConfigDict(extra="forbid")

    sku: str
    task_id: str
    task_status: Literal["queued", "running", "done", "failed"] = "queued"
    refreshed_count: int = Field(default=0, ge=0)
    candidates: list[MatchCandidateResponse] = Field(default_factory=list)


class MatchRefreshStatusResponse(BaseModel):
    """Respuesta del GET /matches/{sku}/refresh/status/{task_id}."""

    model_config = ConfigDict(extra="forbid")

    sku: str
    task_id: str
    task_status: Literal["queued", "running", "done", "failed"]
    refreshed_count: int = Field(default=0, ge=0)
    candidates: list[MatchCandidateResponse] = Field(default_factory=list)
    error: str | None = None


class MatchDiscardRequest(BaseModel):
    """Body opcional para POST /matches/{id}/discard."""

    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(default=None, max_length=512)


# ---------------------------------------------------------------------------
# Three-way summary — US-ERP-03-04 / matching pricing
# ---------------------------------------------------------------------------

class ThreeWaySummaryResponse(BaseModel):
    """Resumen three-way match de pricing para un SKU.

    Cruza:
    - Leg 1: producto MT (specs conocidas).
    - Leg 2: mejor candidato validado del scraper (precio de mercado).
    - Leg 3: último costo de compra real (CostLot.unit_cost_aed).
    """

    model_config = ConfigDict(extra="forbid")

    sku: str = Field(description="SKU del producto MT.")

    # Leg 2 — candidato scraper
    best_candidate_id: UUID | None = Field(
        default=None,
        description="ID del candidato validado con mayor score.",
    )
    best_candidate_title: str | None = Field(
        default=None,
        description="Título del candidato validado con mayor score.",
    )
    best_candidate_channel: str | None = Field(
        default=None,
        description="Canal del candidato (amazon_uae / noon_uae).",
    )
    precio_mercado_aed: Decimal | None = Field(
        default=None,
        description="Precio de mercado del mejor candidato validado (AED).",
    )
    candidate_score: int | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Score de matching del candidato (0-100).",
    )

    # Leg 3 — costo de compra real
    costo_compra_aed: Decimal | None = Field(
        default=None,
        description="Último costo unitario real de compra (CostLot.unit_cost_aed, AED).",
    )
    costo_lot_id: UUID | None = Field(
        default=None,
        description="ID del CostLot de referencia.",
    )
    costo_supplier: str | None = Field(
        default=None,
        description="Código del proveedor del lote de costo.",
    )

    # Margen estimado
    margen_estimado_pct: Decimal | None = Field(
        default=None,
        description=(
            "Margen bruto estimado (%) = (precio_mercado - costo_compra) / precio_mercado * 100. "
            "NULL si falta precio_mercado o costo_compra."
        ),
    )
    margen_estimado_aed: Decimal | None = Field(
        default=None,
        description="Margen bruto absoluto estimado (AED). NULL si falta algún leg.",
    )

    # Completitud
    is_three_way_complete: bool = Field(
        description=(
            "True si los tres legs tienen datos: "
            "SKU existe + candidato validado con precio + costo de compra real."
        ),
    )
    missing_legs: list[str] = Field(
        default_factory=list,
        description="Legs que faltan datos ('market_candidate', 'purchase_cost').",
    )

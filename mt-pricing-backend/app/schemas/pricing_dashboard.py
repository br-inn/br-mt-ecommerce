"""Pydantic schemas — Pricing Dashboard `/api/v1/dashboard/pricing-stats`.

Endpoint de observabilidad del workflow de aprobación de precios:
- Lag promedio de aprobación (últimos 7 días)
- % auto-aprobados vs manuales
- Top exception rules más disparadas (últimos 7 días)
- Conteos por estado + escaladas
- Tendencia diaria 7 días
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ExceptionRuleHit(BaseModel):
    """Una exception rule con su conteo de activaciones (últimos 7 días)."""

    rule_code: str = Field(description="Código único de la ExceptionRule.")
    channel_id: str | None = Field(
        None,
        description="UUID del canal asociado; NULL si aplica globalmente.",
    )
    scheme_code: str | None = Field(
        None,
        description="Código de scheme asociado; NULL si aplica globalmente.",
    )
    count: int = Field(ge=0, description="Precios en pending_review vinculados a esta regla.")


class DailyPricingTrend(BaseModel):
    """Conteos de precios procesados para un día calendario (UTC)."""

    date: str = Field(description="Fecha ISO-8601 (YYYY-MM-DD, UTC).")
    auto_approved: int = Field(ge=0)
    manual_approved: int = Field(ge=0)
    pending: int = Field(ge=0, description="Snapshot del conteo pending_review al cierre del día.")


class PricingDashboardStats(BaseModel):
    """Respuesta del endpoint `/api/v1/dashboard/pricing-stats`.

    `as_of` es ISO-8601 UTC; el frontend lo usa para mostrar el timestamp
    de última actualización.
    """

    # -- Conteos de estado actual (snapshot) -----------------------------------
    pending_review_count: int = Field(ge=0)
    auto_approved_count: int = Field(ge=0)
    approved_today_count: int = Field(ge=0, description="Precios aprobados hoy (UTC).")
    escalated_count: int = Field(ge=0, description="Precios con Price.escalated=true.")

    # -- Lag de aprobación (últimos 7 días) ------------------------------------
    avg_approval_lag_hours: float = Field(
        ge=0.0,
        description=(
            "Promedio de horas entre primer evento pending_review y aprobación. "
            "Calculado sobre Price.approved_at − timestamp del evento from_status=pending_review. "
            "0.0 si no hay datos suficientes."
        ),
    )

    # -- Top exception rules ---------------------------------------------------
    top_exception_rules: list[ExceptionRuleHit] = Field(
        default_factory=list,
        description="Top 3 exception rules por conteo de activaciones (últimos 7 días).",
    )

    # -- Tendencia 7 días -------------------------------------------------------
    daily_trend: list[DailyPricingTrend] = Field(
        default_factory=list,
        description="7 días de tendencia de precios procesados (día más antiguo primero).",
    )

    as_of: str

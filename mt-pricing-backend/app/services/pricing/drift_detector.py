"""Detección de drift de optimización (F8): baseline vs actual.

Reconstruye los params del último snapshot del canal, re-optimiza el catálogo
actual con ambos juegos de parámetros y diffea por SKU. No aplica nada — solo
mide el impacto (cuántos SKUs cambiarían de esquema/señal) para decidir si
alertar.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.channel_pricing import PricingScenario
from app.services.pricing.loader import ParameterLoader
from app.services.pricing.optimization_diff import DiffSummary, diff_results
from app.services.pricing.optimizer import ChannelOptimizer
from app.services.pricing.scenarios import route_fees_from_config
from app.services.pricing.schemas import (
    ChannelFees,
    PriceResult,
    ProductPricingData,
    RouteParams,
    SchemeConfig,
)


@dataclass
class DriftResult:
    summary: DiffSummary
    drift_reasons: dict[str, Any]
    baseline_snapshot_id: UUID
    should_alert: bool


def _optimize(
    products: list[ProductPricingData],
    route: RouteParams,
    fees: ChannelFees,
    schemes: list[SchemeConfig],
    selling_model: str,
) -> list[PriceResult]:
    if selling_model == "b2b":
        return ChannelOptimizer.full_optimize_catalog_b2b(products, route, fees, schemes)
    return ChannelOptimizer.full_optimize_catalog_b2c(products, route, fees, schemes)


def _pct_delta(a: Decimal, b: Decimal) -> str:
    if a == 0:
        return "0"
    return str((abs(b - a) / a * Decimal("100")).quantize(Decimal("0.01")))


async def detect_drift(
    session: AsyncSession, *, channel_id: UUID, selling_model: str
) -> DriftResult | None:
    """Compara la última optimización (snapshot) contra los params actuales.

    Devuelve ``None`` si no hay baseline o catálogo con qué comparar.
    """
    baseline = (
        await session.execute(
            select(PricingScenario)
            .where(
                PricingScenario.channel_id == channel_id,
                PricingScenario.selling_model == selling_model,
            )
            .order_by(PricingScenario.snapshot_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if baseline is None:
        return None
    rebuilt = route_fees_from_config(baseline.config_jsonb)
    if rebuilt is None:
        return None
    base_route, base_fees = rebuilt

    loader = ParameterLoader(session)
    cur_route, cur_fees, schemes = await loader.load_route_and_fees(channel_id)
    products = await loader.load_product_data(channel_id)
    if not products:
        return None

    base_results = _optimize(products, base_route, base_fees, schemes, selling_model)
    cur_results = _optimize(products, cur_route, cur_fees, schemes, selling_model)
    summary = diff_results(base_results, cur_results)

    reasons: dict[str, Any] = {
        "fx_pct": _pct_delta(base_route.fx_rate, cur_route.fx_rate),
        "commission_pp": str(abs(cur_fees.commission_pct - base_fees.commission_pct)),
        "tariff_pp": str(abs(cur_route.import_tariff_pct - base_route.import_tariff_pct)),
    }
    settings = get_settings()
    should = (summary.skus_scheme_changed + summary.skus_signal_changed) >= settings.DRIFT_MIN_SKUS
    return DriftResult(summary, reasons, baseline.id, should)


__all__ = ["DriftResult", "detect_drift"]

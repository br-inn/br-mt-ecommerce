"""Price Sanity Check Service (US-F15-02-04).

Filtra candidatos con precios anómalos antes de invocar el VLM judge,
evitando gastar tokens en candidatos obviamente incorrectos.

Lógica:
- Si no existe rango calibrado para (category_id, currency) → ``skipped``
- Si candidate_price < expected_min_p10 * 0.30 → ``price_too_low``
- Si candidate_price > expected_max_p90 * 3.00 → ``price_too_high``
- En cualquier otro caso → ``ok``
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.metrics import price_sanity_rejections_total
from app.db.models.comparator import PriceCalibrationRange

logger = logging.getLogger(__name__)

# Factores de umbral (AC#3)
_LOW_FACTOR = Decimal("0.30")
_HIGH_FACTOR = Decimal("3.00")


class PriceSanityCheckResult(BaseModel):
    """Resultado del check de sanity de precio."""

    passed: bool
    reason: Literal["ok", "price_too_low", "price_too_high", "skipped"]
    price_too_low: bool = False
    price_too_high: bool = False
    sanity_check_skipped: bool = False


class PriceSanityCheckService:
    """Comprueba si un precio candidato está dentro del rango P10/P90 calibrado.

    Uso::

        service = PriceSanityCheckService()
        result = await service.check(
            session=session,
            candidate_price=Decimal("99.95"),
            category_id="electronics",
            currency="AED",
        )
    """

    async def check(
        self,
        *,
        session: AsyncSession,
        candidate_price: Decimal,
        category_id: str,
        currency: str = "AED",
    ) -> PriceSanityCheckResult:
        """Evalúa si ``candidate_price`` pasa el sanity check para la categoría.

        Args:
            session: AsyncSession de SQLAlchemy.
            candidate_price: Precio a evaluar (Decimal, divisa ``currency``).
            category_id: Identificador de categoría (products.family).
            currency: Código ISO-4217 de la divisa (default AED).

        Returns:
            :class:`PriceSanityCheckResult` con ``passed`` y ``reason``.
        """
        stmt = select(PriceCalibrationRange).where(
            PriceCalibrationRange.category_id == category_id,
            PriceCalibrationRange.currency == currency,
        )
        result = await session.execute(stmt)
        calibration = result.scalar_one_or_none()

        if calibration is None:
            logger.debug(
                "price_sanity.skipped",
                extra={"category_id": category_id, "currency": currency},
            )
            return PriceSanityCheckResult(
                passed=True,
                reason="skipped",
                sanity_check_skipped=True,
            )

        low_threshold = calibration.expected_min_p10 * _LOW_FACTOR
        high_threshold = calibration.expected_max_p90 * _HIGH_FACTOR

        if candidate_price < low_threshold:
            price_sanity_rejections_total.labels(reason="price_too_low").inc()
            logger.info(
                "price_sanity.rejected",
                extra={
                    "reason": "price_too_low",
                    "candidate_price": str(candidate_price),
                    "low_threshold": str(low_threshold),
                    "category_id": category_id,
                    "currency": currency,
                },
            )
            return PriceSanityCheckResult(
                passed=False,
                reason="price_too_low",
                price_too_low=True,
            )

        if candidate_price > high_threshold:
            price_sanity_rejections_total.labels(reason="price_too_high").inc()
            logger.info(
                "price_sanity.rejected",
                extra={
                    "reason": "price_too_high",
                    "candidate_price": str(candidate_price),
                    "high_threshold": str(high_threshold),
                    "category_id": category_id,
                    "currency": currency,
                },
            )
            return PriceSanityCheckResult(
                passed=False,
                reason="price_too_high",
                price_too_high=True,
            )

        logger.debug(
            "price_sanity.ok",
            extra={
                "candidate_price": str(candidate_price),
                "category_id": category_id,
                "currency": currency,
            },
        )
        return PriceSanityCheckResult(passed=True, reason="ok")


__all__ = ["PriceSanityCheckResult", "PriceSanityCheckService"]

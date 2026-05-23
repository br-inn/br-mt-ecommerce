"""Task Celery — recalibración nightly de rangos P10/P90 (US-F15-02-04).

Task ``price_sanity.recalibrate_price_ranges`` — registrada en job_definitions
con schedule ``crontab(hour=0, minute=30)`` (00:30 UTC).

Calcula P10/P90 desde ``competitor_listings`` de los últimos 90 días donde
``price IS NOT NULL``, agrupando por ``(category_id, currency)``. Usa
``products.family`` como ``category_id``. UPSERT en ``price_calibration_ranges``.

Patrón: igual a ``mt.pricing.bulk_recalc`` — asyncio.run / get_sessionmaker.
NO hardcodear schedule en celery_config.py; el schedule vive en job_definitions.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from app.workers.worker import celery_app

logger = logging.getLogger(__name__)

_LOOKBACK_DAYS = 90


async def _run_recalibrate() -> dict[str, Any]:
    """Calcula P10/P90 y hace UPSERT en price_calibration_ranges."""
    from sqlalchemy import func, select, text

    from app.db.engine import get_sessionmaker
    from app.db.models.comparator import CompetitorListing, PriceCalibrationRange
    from app.db.models.product import Product

    since = datetime.now(tz=UTC) - timedelta(days=_LOOKBACK_DAYS)

    async with get_sessionmaker()() as session:
        async with session.begin():
            # ------------------------------------------------------------------
            # Query: P10/P90 por (family, currency) desde competitor_listings
            # con join a products via matched_product_sku
            # ------------------------------------------------------------------
            # Nota: usamos percentile_cont (función de ventana de PostgreSQL)
            # via func.percentile_cont().within_group(...)
            # SQLAlchemy 2.0 soporta ordered-set aggregate con .within_group().
            # ------------------------------------------------------------------
            price_col = func.cast(
                func.json_extract_path_text(
                    CompetitorListing.normalized_jsonb,
                    text("'price'"),
                ),
                func.Float(),
            )

            # Subconsulta: precio numérico + category_id + currency
            # currency viene de normalized_jsonb['currency'] o default 'AED'
            subq = (
                select(
                    Product.family.label("category_id"),
                    func.coalesce(
                        func.json_extract_path_text(
                            CompetitorListing.normalized_jsonb,
                            text("'currency'"),
                        ),
                        "AED",
                    ).label("currency"),
                    func.cast(
                        func.json_extract_path_text(
                            CompetitorListing.normalized_jsonb,
                            text("'price'"),
                        ),
                        func.Numeric(),
                    ).label("price"),
                )
                .join(
                    Product,
                    Product.sku == CompetitorListing.matched_product_sku,
                )
                .where(
                    CompetitorListing.matched_product_sku.is_not(None),
                    CompetitorListing.last_seen_at >= since,
                    func.json_extract_path_text(
                        CompetitorListing.normalized_jsonb,
                        text("'price'"),
                    ).is_not(None),
                )
                .subquery("prices")
            )

            # Agregación P10/P90
            agg_stmt = select(
                subq.c.category_id,
                subq.c.currency,
                func.percentile_cont(0.10).within_group(subq.c.price.asc()).label("p10"),
                func.percentile_cont(0.90).within_group(subq.c.price.asc()).label("p90"),
            ).group_by(subq.c.category_id, subq.c.currency)

            rows = (await session.execute(agg_stmt)).all()

            upserted = 0
            skipped = 0
            for row in rows:
                category_id, currency, p10, p90 = (
                    row.category_id,
                    row.currency,
                    row.p10,
                    row.p90,
                )
                if p10 is None or p90 is None:
                    skipped += 1
                    continue

                # UPSERT — buscar existente y actualizar, o crear nuevo
                stmt = select(PriceCalibrationRange).where(
                    PriceCalibrationRange.category_id == category_id,
                    PriceCalibrationRange.currency == currency,
                )
                existing = (await session.execute(stmt)).scalar_one_or_none()

                if existing is not None:
                    existing.expected_min_p10 = Decimal(str(p10))
                    existing.expected_max_p90 = Decimal(str(p90))
                    existing.updated_at = datetime.now(tz=UTC)
                else:
                    session.add(
                        PriceCalibrationRange(
                            category_id=category_id,
                            currency=currency,
                            expected_min_p10=Decimal(str(p10)),
                            expected_max_p90=Decimal(str(p90)),
                            updated_at=datetime.now(tz=UTC),
                        )
                    )
                upserted += 1

            logger.info(
                "price_sanity.recalibrate.done",
                extra={
                    "upserted": upserted,
                    "skipped_null": skipped,
                    "lookback_days": _LOOKBACK_DAYS,
                },
            )
            return {
                "upserted": upserted,
                "skipped_null": skipped,
                "lookback_days": _LOOKBACK_DAYS,
            }


@celery_app.task(
    name="price_sanity.recalibrate_price_ranges",
    queue="comparator",
    bind=True,
    acks_late=True,
)
def recalibrate_price_ranges(self) -> dict[str, Any]:  # type: ignore[no-untyped-def]  # noqa: ANN001
    """Recalibra rangos P10/P90 desde competitor_listings de los últimos 90 días.

    Registrada en job_definitions con schedule crontab(hour=0, minute=30)
    (00:30 UTC). NO hardcodeado en celery_config.py.
    """
    try:
        result = asyncio.run(_run_recalibrate())
    except Exception as exc:  # noqa: BLE001
        logger.exception("price_sanity.recalibrate.failed", extra={"error": str(exc)})
        raise
    return result


__all__ = ["recalibrate_price_ranges"]

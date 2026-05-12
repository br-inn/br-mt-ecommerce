"""Servicio para reporte diff app vs Excel en parallel run (US-1B-05-01).

Compara precios publicados/auto-aprobados de la aplicación contra la tabla
``price_reference_excel`` (datos Excel del proceso manual previo) para la
fecha dada. Calcula la desviación porcentual por SKU+canal y marca con flag
aquellas que superan el umbral del 0.5%.

El reporte se persiste en Redis (si disponible) con TTL de 24h como caché
de último resultado, o se devuelve ephememeramente si Redis no está disponible.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.pricing import Price

logger = logging.getLogger(__name__)

# Threshold de desviación porcentual que activa el flag (0.5%)
DEVIATION_THRESHOLD_PCT = Decimal("0.5")

# Statuses que se comparan contra el Excel
COMPARABLE_STATUSES = ("published", "auto_approved")

# Prefijo de clave Redis para cache
_CACHE_KEY_PREFIX = "parallel_run_report:"


class ParallelRunService:
    """Genera y recupera reportes de parallel run app vs Excel."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def generate_report(self, target_date: date) -> dict:
        """Genera el reporte diff para la fecha dada.

        Flujo:
        1. Lee prices con status in ('published', 'auto_approved') del día.
        2. Lee price_reference_excel del mismo día (por loaded_at).
        3. Hace JOIN en memoria por (sku, channel).
        4. Calcula desviación = abs(app_price - excel_price) / excel_price * 100.
        5. Flag si desviación > 0.5%.
        6. Persiste resultado en Redis con TTL 24h (best-effort).

        Returns:
            {
                "date": "YYYY-MM-DD",
                "generated_at": "<ISO datetime>",
                "total_skus": int,
                "flagged": int,
                "items": [
                    {
                        "sku": str,
                        "channel": str,
                        "app_price_aed": str,      # Decimal serializado
                        "excel_price_aed": str,
                        "deviation_pct": str,
                        "flagged": bool,
                    },
                    ...
                ],
            }
        """
        day_start = datetime(
            target_date.year, target_date.month, target_date.day,
            0, 0, 0, tzinfo=timezone.utc,
        )
        day_end = datetime(
            target_date.year, target_date.month, target_date.day,
            23, 59, 59, 999999, tzinfo=timezone.utc,
        )

        # 1. Leer prices activos del día
        app_prices = await self._fetch_app_prices(day_start, day_end)

        # 2. Leer referencias Excel del día
        excel_refs = await self._fetch_excel_refs(day_start, day_end)

        # 3. Calcular diff
        items = self._compute_diff(app_prices, excel_refs)

        flagged_count = sum(1 for item in items if item["flagged"])
        report = {
            "date": target_date.isoformat(),
            "generated_at": datetime.now(tz=timezone.utc).isoformat(),
            "total_skus": len(items),
            "flagged": flagged_count,
            "items": items,
        }

        # 4. Cachear en Redis (best-effort)
        await self._cache_report(target_date, report)

        logger.info(
            "parallel_run.report_generated date=%s total=%d flagged=%d",
            target_date.isoformat(),
            len(items),
            flagged_count,
        )
        return report

    async def get_latest_report(self, target_date: date) -> dict | None:
        """Recupera el reporte cacheado para la fecha, o None si no existe.

        Intenta Redis primero; si no hay caché devuelve None (el caller
        puede decidir llamar a generate_report o retornar 404).
        """
        try:
            from app.core.redis import get_redis  # lazy import

            redis = get_redis()
            key = f"{_CACHE_KEY_PREFIX}{target_date.isoformat()}"
            raw = await redis.get(key)
            if raw:
                return json.loads(raw)
        except Exception:
            logger.warning("parallel_run.cache_miss — Redis no disponible o clave ausente")
        return None

    # ------------------------------------------------------------------
    # Métodos privados
    # ------------------------------------------------------------------

    async def _fetch_app_prices(
        self, day_start: datetime, day_end: datetime
    ) -> dict[tuple[str, str], Decimal]:
        """Retorna {(sku, channel_code): amount_aed} para prices del período.

        Usa el último precio por SKU+canal si hay múltiples (MAX created_at).
        Solo incluye status in COMPARABLE_STATUSES.
        """
        stmt = text(
            """
            SELECT DISTINCT ON (p.product_sku, c.code)
                p.product_sku AS sku,
                c.code        AS channel,
                p.amount      AS amount_aed
            FROM prices p
            JOIN channels c ON c.id = p.channel_id
            WHERE p.status = ANY(:statuses)
              AND p.created_at >= :day_start
              AND p.created_at <= :day_end
            ORDER BY p.product_sku, c.code, p.created_at DESC
            """
        ).bindparams(
            statuses=list(COMPARABLE_STATUSES),
            day_start=day_start,
            day_end=day_end,
        )
        result = await self.session.execute(stmt)
        return {
            (row.sku, row.channel): Decimal(str(row.amount_aed))
            for row in result
        }

    async def _fetch_excel_refs(
        self, day_start: datetime, day_end: datetime
    ) -> dict[tuple[str, str], Decimal]:
        """Retorna {(sku, channel): reference_price_aed} de price_reference_excel."""
        stmt = text(
            """
            SELECT DISTINCT ON (sku, channel)
                sku,
                channel,
                reference_price_aed
            FROM price_reference_excel
            WHERE loaded_at >= :day_start
              AND loaded_at <= :day_end
            ORDER BY sku, channel, loaded_at DESC
            """
        ).bindparams(day_start=day_start, day_end=day_end)
        result = await self.session.execute(stmt)
        return {
            (row.sku, row.channel): Decimal(str(row.reference_price_aed))
            for row in result
        }

    @staticmethod
    def _compute_diff(
        app_prices: dict[tuple[str, str], Decimal],
        excel_refs: dict[tuple[str, str], Decimal],
    ) -> list[dict]:
        """Calcula la desviación por SKU+canal entre app y Excel.

        Solo incluye pares que existen en AMBAS fuentes. Pares sin match
        en alguna fuente se omiten (no se puede calcular desviación).
        """
        items: list[dict] = []
        all_keys = set(app_prices) | set(excel_refs)

        for sku, channel in sorted(all_keys):
            app_val = app_prices.get((sku, channel))
            excel_val = excel_refs.get((sku, channel))

            if app_val is None or excel_val is None:
                # Par incompleto — reportar como info pero sin desviación
                items.append(
                    {
                        "sku": sku,
                        "channel": channel,
                        "app_price_aed": str(app_val) if app_val is not None else None,
                        "excel_price_aed": str(excel_val) if excel_val is not None else None,
                        "deviation_pct": None,
                        "flagged": False,
                        "note": "missing_in_source" if app_val is None else "missing_in_excel",
                    }
                )
                continue

            if excel_val == 0:
                deviation = Decimal("0")
            else:
                deviation = (
                    abs(app_val - excel_val) / excel_val * Decimal("100")
                ).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

            flagged = deviation > DEVIATION_THRESHOLD_PCT
            items.append(
                {
                    "sku": sku,
                    "channel": channel,
                    "app_price_aed": str(app_val),
                    "excel_price_aed": str(excel_val),
                    "deviation_pct": str(deviation),
                    "flagged": flagged,
                }
            )
        return items

    async def _cache_report(self, target_date: date, report: dict) -> None:
        """Persiste el reporte en Redis con TTL 24h. Best-effort."""
        try:
            from app.core.redis import get_redis  # lazy import

            redis = get_redis()
            key = f"{_CACHE_KEY_PREFIX}{target_date.isoformat()}"
            await redis.setex(key, 86400, json.dumps(report))
        except Exception:
            logger.warning("parallel_run.cache_store_failed — Redis no disponible")


__all__ = ["ParallelRunService"]

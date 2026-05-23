"""Celery task: mt.pricing.parallel_run_diff — parallel run diario 08:00 UAE (US-1B-05-01).

Task name: ``mt.pricing.parallel_run_diff``. Routing queue: ``pricing``.
Schedule: diario 04:00 UTC (08:00 Asia/Dubai) via ``BEAT_SCHEDULE``.

Genera el reporte diff entre precios de la aplicación (status published/auto_approved)
y la tabla ``price_reference_excel`` para la fecha de hoy. El reporte se persiste
en Redis para ser consultado via ``GET /parallel-run/report?date=YYYY-MM-DD``.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, date, datetime
from typing import Any

from app.db.engine import get_sessionmaker
from app.services.pricing.parallel_run_service import ParallelRunService
from app.workers.worker import celery_app

logger = logging.getLogger(__name__)


async def _run_async(target_date: date) -> dict:
    Session = get_sessionmaker()
    async with Session() as session:
        svc = ParallelRunService(session)
        report = await svc.generate_report(target_date)
        return report


@celery_app.task(
    name="mt.pricing.parallel_run_diff",
    queue="pricing",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=3,
)
def parallel_run_diff(
    self: Any,
    target_date_iso: str | None = None,
) -> dict:
    """Genera el reporte de parallel run para la fecha dada.

    Args:
        target_date_iso: fecha ISO-8601 opcional (e.g. "2026-05-12"). Si None,
            usa la fecha UTC actual. Útil para re-runs manuales o backfills.

    Returns:
        dict con date, generated_at, total_skus, flagged, items[].
    """
    target = (
        date.fromisoformat(target_date_iso)
        if target_date_iso
        else datetime.now(tz=UTC).date()
    )
    result = asyncio.run(_run_async(target))
    logger.info(
        "parallel_run_diff: date=%s total_skus=%d flagged=%d",
        result["date"],
        result["total_skus"],
        result["flagged"],
    )
    return result


__all__ = ["parallel_run_diff"]

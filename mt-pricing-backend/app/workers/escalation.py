"""Celery task: escalate pending_review propuestas > 48h (US-1B-02-08).

Task name: ``mt.pricing.escalate_pending``. Routing queue: ``pricing``.
Schedule: cada 2h via ``BEAT_SCHEDULE`` o ``job_definitions`` seed.

Idempotente — vuelve a procesar la cola entera; las propuestas con
``escalated=true`` se skipean dentro del service.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.db.engine import get_sessionmaker
from app.services.pricing.escalation_service import EscalationService
from app.workers.worker import celery_app

logger = logging.getLogger(__name__)


async def _run_async(window_hours: int) -> dict:
    Session = get_sessionmaker()
    async with Session() as session:
        service = EscalationService(session, window_hours=window_hours)
        summary = await service.run_sweep()
        await session.commit()
        return summary


@celery_app.task(
    name="mt.pricing.escalate_pending",
    queue="pricing",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=3,
)
def escalate_pending_reviews(
    self: Any,
    window_hours: int = 48,
) -> dict:
    summary = asyncio.run(_run_async(window_hours))
    logger.info(
        "escalate_pending_reviews: checked=%d escalated=%d window_hours=%d",
        summary["checked"],
        summary["escalated"],
        summary["window_hours"],
    )
    return summary


__all__ = ["escalate_pending_reviews"]

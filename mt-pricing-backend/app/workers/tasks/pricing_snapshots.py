"""Task nightly: limpia snapshots auto vencidos (>retención) (F2)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.db import get_sessionmaker
from app.services.pricing.snapshot_cleanup import cleanup_expired_auto_snapshots
from app.workers.worker import celery_app

logger = logging.getLogger(__name__)


async def _run() -> dict[str, Any]:
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        deleted = await cleanup_expired_auto_snapshots(session)
        await session.commit()
        return {"deleted": deleted}


@celery_app.task(name="mt.pricing.cleanup_auto_snapshots", bind=True, acks_late=True)
def cleanup_auto_snapshots(self) -> dict[str, Any]:
    result = asyncio.run(_run())
    logger.info("pricing.cleanup_auto_snapshots.done", extra=result)
    return result


__all__ = ["cleanup_auto_snapshots"]

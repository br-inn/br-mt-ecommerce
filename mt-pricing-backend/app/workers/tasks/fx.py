"""Task diaria: sincroniza FX EUR→AED desde ECB (F2)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.db import get_sessionmaker
from app.services.fx.fx_sync_service import sync_ecb_eur_aed
from app.workers.worker import celery_app

logger = logging.getLogger(__name__)


async def _run() -> dict[str, Any]:
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        return await sync_ecb_eur_aed(session)


@celery_app.task(name="mt.fx.sync_daily", bind=True, acks_late=True)
def sync_daily(self) -> dict[str, Any]:
    result = asyncio.run(_run())
    logger.info("fx.sync.done", extra=result)
    return result


__all__ = ["sync_daily"]

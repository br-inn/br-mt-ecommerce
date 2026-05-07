"""Tasks para la queue `audit` — append-only events ingestion + cleanups."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import create_engine, text

from app.core.config import settings
from app.workers.worker import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="mt.audit.health_ping")
def health_ping() -> str:
    return "ok"


@celery_app.task(
    bind=True,
    name="mt.audit.cleanup_force_logout_events",
    acks_late=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 2},
)
def cleanup_force_logout_events(self: Any, retention_hours: int = 24) -> dict[str, Any]:
    """Borra rows de `force_logout_events` mayores a `retention_hours` (default 24h).

    Llamada desde job_definition `cleanup_force_logout_events` (cron 03:00 UTC
    daily). El propósito es evitar growth indefinido — el evento solo es útil
    los segundos siguientes a su creación (lo lee el cliente Realtime y se
    desconecta). 24h es buffer generoso por si un usuario abre la SPA tarde.
    """
    sync_url = str(settings.ALEMBIC_DATABASE_URL)
    engine = create_engine(sync_url, future=True)
    deleted = 0
    try:
        with engine.begin() as conn:
            result = conn.execute(
                text(
                    "DELETE FROM public.force_logout_events "
                    "WHERE created_at < now() - make_interval(hours => :hours)"
                ).bindparams(hours=retention_hours)
            )
            deleted = result.rowcount or 0
    finally:
        engine.dispose()
    out = {"deleted": deleted, "retention_hours": retention_hours}
    logger.info("audit.cleanup_force_logout_events.done", extra=out)
    return out

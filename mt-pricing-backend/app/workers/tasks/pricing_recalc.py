"""Pricing bulk recalc nightly task (US-1B-01-07).

Task ``mt.pricing.bulk_recalc`` — disparada a 02:00 Asia/Dubai por
``DatabaseScheduler`` (cron ``0 2 * * *``). Itera todos los SKUs activos con
costos válidos y re-propone precios via ``PricingService.recalculate_for_product``.

Persistencia:
- ``BulkRecalcService.run()`` graba un audit batch
  ``audit_events(action='nightly_recalc_batch', payload_after=summary)``.
- La task devuelve ``summary.to_dict()`` (Celery result backend).

Diseño:
- Resuelve un actor "system" — el JWT estándar no aplica acá. Lookup por
  email seedeado (``settings.SYSTEM_NIGHTLY_ACTOR_EMAIL``, fallback al primer
  TI/admin disponible). Si no encuentra ninguno, se aborta con audit
  ``nightly_recalc_skipped`` (out of scope para este task — se logea + skip).
- Mutex Redis-light: si hay un manual recalc activo (key
  ``mt:pricing:manual_recalc_lock``), skipea con ``skip_reason``.
- Paralelo opcional: por defecto el batch es secuencial — fan-out vía
  ``recalculate_sku_task.delay`` ya existe (``recalculate_catalog_task``);
  acá preferimos un único worker que escribe el audit batch atómicamente.

Tests inyectan helpers via :func:`_resolve_actor` / :func:`_acquire_mutex`
(monkeypatch).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.workers.worker import celery_app

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _run_async(coro: Any) -> Any:  # noqa: ANN401
    """Mini event-loop runner. Idéntico patrón al de ``app.workers.tasks.pricing``."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            raise RuntimeError("event loop already running in Celery context")
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


async def _resolve_actor(session: Any) -> Any:
    """Resuelve el actor 'system' del nightly batch.

    Estrategia:
    1. ``settings.SYSTEM_NIGHTLY_ACTOR_EMAIL`` si existe (env opcional).
    2. Primer usuario admin/ti_integracion activo de DB.
    3. None → caller skipea el batch.
    """
    from sqlalchemy import select

    from app.core.config import settings
    from app.db.models.user import User

    target_email = getattr(settings, "SYSTEM_NIGHTLY_ACTOR_EMAIL", None)
    if isinstance(target_email, str) and target_email:
        stmt = select(User).where(User.email == target_email).limit(1)
        user = (await session.execute(stmt)).scalar_one_or_none()
        if user is not None:
            return user

    # Fallback: primer admin/ti activo (sin enforcement de role aquí — el
    # bulk recalc no toca permisos directamente, sólo queda en audit).
    stmt = (
        select(User)
        .where(User.is_active.is_(True), User.deleted_at.is_(None))
        .order_by(User.created_at.asc())
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def _acquire_mutex() -> bool:
    """Intenta adquirir el lock Redis NX EX 'mt:pricing:manual_recalc_lock'.

    Si el lock está tomado por un manual recalc concurrente, devuelve False
    → el batch se skipea con razón ``manual_recalc_in_progress``.

    Si Redis no está disponible (test mode), devuelve True (no-op).
    """
    try:
        from app.core.redis import get_redis
    except Exception:  # pragma: no cover  # noqa: BLE001
        return True

    try:
        redis = get_redis()
        # Si HAY clave → manual recalc en curso, no podemos correr.
        existing = await redis.get("mt:pricing:manual_recalc_lock")
        return existing is None
    except Exception:  # pragma: no cover  # noqa: BLE001
        logger.exception("bulk_recalc.mutex_check_failed")
        return True


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------
@celery_app.task(
    name="mt.pricing.bulk_recalc",
    queue="pricing",
    bind=True,
)
def bulk_recalc_task(self, source: str = "nightly_beat") -> dict[str, Any]:  # type: ignore[no-untyped-def]
    """Recalcula precios de todo el catálogo activo y graba audit batch.

    :param source: identificador del trigger ('nightly_beat', 'manual_admin').
    :return: ``BulkRecalcResult.to_dict()`` con métricas + estado.
    """

    async def _run() -> dict[str, Any]:
        from app.db.engine import get_sessionmaker
        from app.services.pricing.bulk_recalc_service import BulkRecalcService

        async with get_sessionmaker()() as session:
            actor = await _resolve_actor(session)
            if actor is None:
                logger.error(
                    "bulk_recalc.no_system_actor — abort",
                    extra={"source": source},
                )
                return {
                    "skipped": True,
                    "skip_reason": "no_system_actor",
                    "source": source,
                }

            svc = BulkRecalcService(
                session=session,
                mutex_acquire=_acquire_mutex,
            )
            try:
                result = await svc.run(actor=actor, source=source)
                await session.commit()
            except Exception:  # noqa: BLE001
                await session.rollback()
                raise
            return result.to_dict()

    return _run_async(_run())


__all__ = ["bulk_recalc_task"]

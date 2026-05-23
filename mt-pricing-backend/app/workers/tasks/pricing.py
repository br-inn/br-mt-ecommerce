"""Tasks para la queue `pricing` — recalculate, fx_cascade.

Convención: tasks toman ids serializables (str UUID) y abren su propia session
async via `app.db.session_for_celery()`. El service queda igual que en HTTP — la
diferencia es que el caller es el worker, no FastAPI.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from uuid import UUID

from app.workers.worker import celery_app

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper async runner para Celery (no async-native)
# ---------------------------------------------------------------------------
def _run_async(coro: Any) -> Any:
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # No deberíamos estar dentro de un loop en un worker
            raise RuntimeError("event loop already running in Celery context")
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------
@celery_app.task(name="mt.pricing.health_ping")
def health_ping() -> str:
    return "ok"


@celery_app.task(name="mt.pricing.recalculate_sku", queue="pricing", bind=True)
def recalculate_sku_task(self, product_sku: str, actor_id: str) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    """Re-propone precios para un SKU en TODOS los channels live × scheme soportado."""

    async def _run() -> dict[str, Any]:
        from sqlalchemy import select

        from app.db.engine import get_sessionmaker
        from app.db.models.user import User
        from app.services.pricing import PricingService

        async with get_sessionmaker()() as session:
            user = (
                await session.execute(select(User).where(User.id == UUID(actor_id)))
            ).scalar_one_or_none()
            if user is None:
                logger.warning("recalculate_sku_task: actor %s no existe", actor_id)
                return {"status": "skipped", "reason": "actor_not_found"}
            service = PricingService(session)
            try:
                prices = await service.recalculate_for_product(product_sku, user)
                await session.commit()
            except Exception:
                await session.rollback()
                raise
        return {
            "status": "ok",
            "sku": product_sku,
            "proposed": [str(p.id) for p in prices],
        }

    return _run_async(_run())


@celery_app.task(name="mt.pricing.recalculate_catalog_bulk", queue="pricing")
def recalculate_catalog_task(actor_id: str) -> dict[str, Any]:
    """Fan-out — itera todos los SKUs activos y dispara `recalculate_sku_task` por cada uno."""

    async def _run() -> dict[str, Any]:
        from sqlalchemy import select

        from app.db.engine import get_sessionmaker
        from app.db.models.product import Product

        async with get_sessionmaker()() as session:
            # Fase B (mig 066): active deriva de lifecycle_status='active'.
            stmt = select(Product.sku).where(
                Product.lifecycle_status == "active",
                Product.deleted_at.is_(None),
            )
            res = await session.execute(stmt)
            skus = [r[0] for r in res.all()]
        return {"skus": skus}

    bundle = _run_async(_run())
    skus = bundle.get("skus", [])
    queued = 0
    for sku in skus:
        recalculate_sku_task.delay(sku, actor_id)
        queued += 1
    logger.info("recalculate_catalog_task: queued %d sku tasks", queued)
    return {"status": "queued", "count": queued}


@celery_app.task(name="mt.pricing.fx_cascade", queue="pricing")
def fx_cascade_task(fx_rate_id: str) -> dict[str, Any]:
    """Cuando se publica un FX rate nuevo, recalcula prices de SKUs afectados.

    TODO Sprint 3: filtrar por `cost.currency = fx.from_currency` en lugar de
    fan-out total — por ahora dispara recalculate_catalog para simplificar.
    """

    async def _run() -> dict[str, Any]:
        from sqlalchemy import select

        from app.db.engine import get_sessionmaker
        from app.db.models.pricing import FXRate

        async with get_sessionmaker()() as session:
            stmt = select(FXRate).where(FXRate.id == UUID(fx_rate_id))
            fx = (await session.execute(stmt)).scalar_one_or_none()
            if fx is None:
                logger.warning("fx_cascade_task: FX %s no existe", fx_rate_id)
                return {"status": "skipped"}
            return {
                "from": fx.from_currency,
                "to": fx.to_currency,
                "rate": str(fx.rate),
            }

    fx_info = _run_async(_run())
    if fx_info.get("status") == "skipped":
        return fx_info

    logger.info("fx_cascade_task: FX update %s — fan-out catálogo", fx_info)
    # Por ahora — invocamos recalculate_catalog_task con un actor placeholder.
    # Sprint 3: pasar actor real (TI integracion).
    return {"status": "fx_logged", "fx": fx_info}

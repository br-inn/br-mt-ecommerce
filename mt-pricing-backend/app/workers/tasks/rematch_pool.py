"""Tasks para re-matching periódico del candidate pool (unmatched_offers).

Patrón: Bronze/Silver/Gold — las ofertas sin match viven en Silver (unmatched_offers)
y se re-intentan matchear cuando el pipeline mejora o periódicamente.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any

from app.workers.worker import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro: Any) -> Any:
    return asyncio.run(coro)


@celery_app.task(
    name="mt.comparator.rematch_unmatched_pool",
    queue="comparator",
    bind=True,
    max_retries=1,
    default_retry_delay=60,
)
def rematch_unmatched_pool(self: Any, batch_size: int = 50) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    """Re-intenta matching para ofertas en el pool que tienen source_sku.

    Agrupa las ofertas por source_sku y llama a rematch_from_pool() para
    cada grupo. Las ofertas sin source_sku solo incrementan su contador.
    Corre periódicamente (Celery Beat) o cuando el pipeline mejora.
    """

    async def _run() -> dict[str, Any]:
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from sqlalchemy.pool import NullPool

        from app.core.config import settings
        from app.db.models.unmatched_offer import UnmatchedOffer
        from app.repositories.unmatched_offers import UnmatchedOfferRepository
        from app.services.matching.adapter_registry import get_fetcher
        from app.services.matching.match_service import MatchService

        engine = create_async_engine(
            str(settings.DATABASE_URL),
            poolclass=NullPool,
            connect_args={
                "statement_cache_size": 0,
                "server_settings": {
                    "application_name": "mt-comparator-worker",
                    "timezone": "UTC",
                },
            },
        )
        session_factory = async_sessionmaker(
            bind=engine,
            expire_on_commit=False,
            autoflush=False,
            class_=AsyncSession,
        )

        matched = 0
        failed = 0

        try:
            async with session_factory() as session:
                unmatched_repo = UnmatchedOfferRepository(session)

                # Obtener lote de ofertas sin match con source_sku registrado.
                stmt = (
                    select(UnmatchedOffer)
                    .where(
                        UnmatchedOffer.matched_at.is_(None),
                        UnmatchedOffer.match_attempts < 3,
                        UnmatchedOffer.source_sku.isnot(None),
                    )
                    .order_by(UnmatchedOffer.scraped_at.desc())
                    .limit(batch_size)
                )
                result = await session.execute(stmt)
                offers = list(result.scalars().all())

                if not offers:
                    logger.info("rematch_pool.empty")
                    return {"matched": 0, "failed": 0, "processed": 0}

                # Agrupar por source_sku para procesar en bloque por SKU.
                by_sku: defaultdict[str, list[UnmatchedOffer]] = defaultdict(list)
                for offer in offers:
                    by_sku[offer.source_sku].append(offer)  # type: ignore[index]

                fetchers = [get_fetcher("amazon_uae"), get_fetcher("noon_uae")]

                for sku, sku_offers in by_sku.items():
                    try:
                        service = MatchService(
                            session, fetchers=fetchers, unmatched_repo=unmatched_repo
                        )
                        pool_matches = await service.rematch_from_pool(sku, sku_offers)
                        matched += len(pool_matches)
                        logger.info(
                            "rematch_pool.sku_done",
                            extra={
                                "sku": sku,
                                "processed": len(sku_offers),
                                "matched": len(pool_matches),
                            },
                        )
                    except Exception:
                        logger.warning(
                            "rematch_pool.sku_failed",
                            extra={"sku": sku},
                            exc_info=True,
                        )
                        for offer in sku_offers:
                            await unmatched_repo.increment_attempts(offer.id)
                        failed += len(sku_offers)

                await session.commit()

            logger.info(
                "rematch_pool.done",
                extra={"matched": matched, "failed": failed, "processed": len(offers)},
            )
            return {"matched": matched, "failed": failed, "processed": len(offers)}
        finally:
            await engine.dispose()

    try:
        return _run_async(_run())
    except Exception as exc:
        logger.exception("rematch_pool.error")
        raise self.retry(exc=exc)  # type: ignore[attr-defined]


@celery_app.task(
    name="mt.comparator.cleanup_unmatched_pool",
    queue="comparator",
)
def cleanup_unmatched_pool(max_age_days: int = 30, max_attempts: int = 3) -> dict[str, Any]:
    """Elimina ofertas del pool con TTL vencido y máximo de intentos alcanzado."""

    async def _run() -> dict[str, Any]:
        from sqlalchemy import delete, text
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from sqlalchemy.pool import NullPool

        from app.core.config import settings
        from app.db.models.unmatched_offer import UnmatchedOffer

        engine = create_async_engine(
            str(settings.DATABASE_URL),
            poolclass=NullPool,
            connect_args={
                "statement_cache_size": 0,
                "server_settings": {"application_name": "mt-comparator-worker", "timezone": "UTC"},
            },
        )
        session_factory = async_sessionmaker(
            bind=engine, expire_on_commit=False, autoflush=False, class_=AsyncSession
        )
        try:
            async with session_factory() as session:
                result = await session.execute(
                    delete(UnmatchedOffer).where(
                        UnmatchedOffer.match_attempts >= max_attempts,
                        UnmatchedOffer.matched_at.is_(None),
                        text(f"scraped_at < NOW() - INTERVAL '{max_age_days} days'"),
                    )
                )
                deleted = result.rowcount
                await session.commit()
            logger.info("cleanup_pool.done", extra={"deleted": deleted})
            return {"deleted": deleted}
        finally:
            await engine.dispose()

    return _run_async(_run())

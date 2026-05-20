"""Tasks para la queue `comparator` — matching pipeline."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.workers.worker import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro: Any) -> Any:  # noqa: ANN401
    # asyncio.run() crea un event loop nuevo por invocación — correcto para
    # Celery prefork donde cada fork hereda el estado del padre.
    return asyncio.run(coro)


@celery_app.task(name="mt.comparator.health_ping")
def health_ping() -> str:
    return "ok"


@celery_app.task(
    name="mt.comparator.refresh_sku",
    queue="comparator",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
)
def refresh_sku_task(self: Any, sku: str) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    """Corre el pipeline de matching completo para un SKU y persiste candidatos.

    Se encola desde POST /matches/{sku}/refresh para evitar que el scraping
    bloquee el request HTTP (timeout del gateway).
    """

    async def _run() -> dict[str, Any]:
        from app.core.config import settings
        from app.services.matching.adapter_registry import get_fetcher
        from app.services.matching.match_service import MatchService, MatchSkuNotFoundError
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from sqlalchemy.pool import NullPool

        # NullPool: conexión fresca por sesión, sin reciclado entre invocaciones.
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
        try:
            fetchers = [get_fetcher("amazon_uae"), get_fetcher("noon_uae")]
            async with session_factory() as session:
                from app.repositories.unmatched_offers import UnmatchedOfferRepository  # noqa: PLC0415
                unmatched_repo = UnmatchedOfferRepository(session)
                service = MatchService(session, fetchers=fetchers, unmatched_repo=unmatched_repo)

                # Pool lookup gate: buscar en el pool de ofertas sin match antes de scraping.
                # Si hay hits similares al SKU, intentar re-matchear sin red request.
                pool_matched = 0
                try:
                    from app.services.matching.embeddings import embed_sku  # noqa: PLC0415
                    product = await service._products_repo.get_by_sku_for_matching(sku)
                    if product is not None:
                        sku_dict = service._product_to_dict(product)
                        sku_embedding = embed_sku(sku_dict)
                        pool_hits = await unmatched_repo.find_similar(
                            sku_embedding, limit=10, max_age_days=7, min_similarity=0.75
                        )
                        pool_offers = [offer for offer, _score in pool_hits]
                        # Fallback: offers scraped specifically for this SKU (source_sku match),
                        # regardless of embedding similarity score.
                        if not pool_offers:
                            pool_offers = await unmatched_repo.get_pending_for_sku(sku, limit=50)
                        if pool_offers:
                            pool_matches = await service.rematch_from_pool(sku, pool_offers)
                            pool_matched = len(pool_matches)
                            if pool_matched:
                                await session.commit()
                                logger.info(
                                    "comparator.pool_gate.matched",
                                    extra={"sku": sku, "pool_matched": pool_matched},
                                )
                except Exception:
                    logger.warning(
                        "comparator.pool_gate.failed",
                        extra={"sku": sku},
                        exc_info=True,
                    )

                try:
                    pairs = await service.refresh_candidates_enhanced(sku, mt_image_url=None)
                    count = len(pairs)

                    # Agente de validación — corre inline tras el scoring.
                    if settings.MATCH_AGENT_ENABLED:
                        from app.services.matching.validation_agent import (  # noqa: PLC0415
                            MatchValidationAgent,
                        )
                        agent_decided = await MatchValidationAgent(session).run(sku)
                        logger.info(
                            "comparator.refresh_sku.agent",
                            extra={"sku": sku, "agent_decided": agent_decided},
                        )

                    await session.commit()
                    logger.info(
                        "comparator.refresh_sku.done",
                        extra={"sku": sku, "count": count, "pool_matched": pool_matched},
                    )
                    return {"sku": sku, "refreshed_count": count, "pool_matched": pool_matched}
                except MatchSkuNotFoundError:
                    logger.warning("comparator.refresh_sku.not_found", extra={"sku": sku})
                    return {"sku": sku, "refreshed_count": 0, "pool_matched": pool_matched, "error": "sku_not_found"}
        finally:
            await engine.dispose()

    try:
        return _run_async(_run())
    except Exception as exc:
        logger.exception("comparator.refresh_sku.error", extra={"sku": sku})
        raise self.retry(exc=exc)  # type: ignore[attr-defined]

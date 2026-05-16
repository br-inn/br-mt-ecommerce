"""Celery tasks para monitoreo continuo de precios (US-SCR-04-02/03).

Cola dedicada: ``scraper.price_monitor`` (separada de ``scraper.brand``).
Tasks:
- ``price_monitor_task``: scrape precio de un SKU en un marketplace, guarda en
  ``price_history_raw``, y detecta variación > 5% vs último precio.
- ``bootstrap_price_monitoring``: itera marcas con ``monitoring_active=True`` y
  lanza ``price_monitor_task`` por marca × marketplace.
- ``refresh_price_daily_stats``: REFRESH MATERIALIZED VIEW CONCURRENTLY price_daily_stats.
"""

from __future__ import annotations

import asyncio
import logging
from decimal import Decimal

from celery.exceptions import SoftTimeLimitExceeded

from app.workers.worker import celery_app

logger = logging.getLogger(__name__)

# Cola dedicada para monitoreo de precios — separada del scraping inicial
PRICE_MONITOR_QUEUE = "scraper.price_monitor"

# Marketplaces soportados para monitoreo
MONITORED_MARKETPLACES = ["amazon_uae", "noon_uae"]

# Umbral de variación de precio para alerta (5%)
PRICE_VARIATION_THRESHOLD = Decimal("0.05")


# ---------------------------------------------------------------------------
# price_monitor_task — scrape precio individual
# ---------------------------------------------------------------------------


@celery_app.task(
    bind=True,
    name="mt.scraper.price_monitor",
    max_retries=2,
    default_retry_delay=60,
    acks_late=True,
    queue=PRICE_MONITOR_QUEUE,
)
def price_monitor_task(self, sku: str, marketplace: str) -> dict:  # type: ignore[override]
    """Scrape el precio actual de un SKU en un marketplace y guarda el historial.

    Args:
        sku: Código de producto MT.
        marketplace: Canal de marketplace (``amazon_uae``, ``noon_uae``).

    Returns:
        dict con ``sku``, ``marketplace``, ``price_aed``, ``variation_pct``, ``alert``.
    """
    logger.info(
        "price_monitor.start",
        extra={"sku": sku, "marketplace": marketplace},
    )

    async def _run() -> dict:
        from decimal import Decimal
        from uuid import UUID

        from sqlalchemy import select, text
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from sqlalchemy.pool import NullPool

        from app.core.config import settings
        from app.db.models.match_candidate import MatchCandidate
        from app.db.models.price_history import PriceHistoryRaw
        from app.services.matching.adapter_registry import get_fetcher
        from app.services.matching.ports import Query
        from app.services.scraper.circuit_breaker import ScraperCircuitOpenError, get_circuit_breaker
        from app.services.scraper.rate_limiter import get_rate_limiter

        engine = create_async_engine(
            str(settings.DATABASE_URL),
            poolclass=NullPool,
            connect_args={
                "statement_cache_size": 0,
                "server_settings": {
                    "application_name": "mt-price-monitor",
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
            async with session_factory() as session:
                # ── Verificar circuit breaker ──────────────────────────────
                cb = get_circuit_breaker()
                try:
                    await cb.check_and_raise(marketplace)
                except ScraperCircuitOpenError:
                    logger.warning(
                        "price_monitor.circuit_open",
                        extra={"sku": sku, "marketplace": marketplace},
                    )
                    return {"sku": sku, "marketplace": marketplace, "status": "circuit_open", "alert": False}

                # ── Rate limiter ───────────────────────────────────────────
                rate_limiter = get_rate_limiter()
                await rate_limiter.acquire(marketplace)

                # ── Fetch precio via adapter ───────────────────────────────
                fetcher = get_fetcher(marketplace)
                query = Query(
                    text=sku,
                    source=marketplace,
                    type="sku",
                    dept=None,
                    category_node=None,
                )
                try:
                    candidates = await fetcher.fetch(query, sku=sku)
                    await cb.record_success(marketplace)
                except Exception as fetch_exc:
                    await cb.record_failure(marketplace)
                    raise fetch_exc

                if not candidates:
                    logger.info(
                        "price_monitor.no_candidates",
                        extra={"sku": sku, "marketplace": marketplace},
                    )
                    return {
                        "sku": sku,
                        "marketplace": marketplace,
                        "status": "no_candidates",
                        "alert": False,
                    }

                # Usar el primer candidato (mayor score) para el precio
                top = candidates[0]
                raw = top if isinstance(top, dict) else vars(top)
                price_raw = raw.get("price") or raw.get("price_aed") or raw.get("price_usd")
                if price_raw is None:
                    logger.warning(
                        "price_monitor.no_price_in_candidate",
                        extra={"sku": sku, "marketplace": marketplace},
                    )
                    return {
                        "sku": sku,
                        "marketplace": marketplace,
                        "status": "no_price",
                        "alert": False,
                    }

                current_price = Decimal(str(price_raw))

                # ── Obtener match_id si existe ─────────────────────────────
                match_id_result = await session.execute(
                    select(MatchCandidate.id)
                    .where(MatchCandidate.sku == sku)
                    .where(MatchCandidate.channel == marketplace)
                    .order_by(MatchCandidate.score.desc())
                    .limit(1)
                )
                match_id_row = match_id_result.first()
                match_id = match_id_row[0] if match_id_row else None

                # ── Obtener último precio registrado ───────────────────────
                prev_price_result = await session.execute(
                    text("""
                        SELECT price_aed FROM price_history_raw
                        WHERE sku = :sku AND marketplace = :mkt
                        ORDER BY scraped_at DESC
                        LIMIT 1
                    """),
                    {"sku": sku, "mkt": marketplace},
                )
                prev_row = prev_price_result.first()
                prev_price = Decimal(str(prev_row[0])) if prev_row else None

                # ── Guardar en price_history_raw ───────────────────────────
                source_url = raw.get("source_url") or raw.get("url")
                entry = PriceHistoryRaw(
                    match_id=match_id,
                    marketplace=marketplace,
                    price_aed=current_price,
                    currency="AED",
                    sku=sku,
                    source_url=source_url,
                    raw_payload=raw if isinstance(raw, dict) else {},
                )
                session.add(entry)
                await session.commit()

                # ── Detectar variación > 5% ────────────────────────────────
                alert = False
                variation_pct = None
                if prev_price and prev_price > 0:
                    variation_pct = abs(current_price - prev_price) / prev_price
                    if variation_pct > PRICE_VARIATION_THRESHOLD:
                        alert = True
                        logger.warning(
                            "price_monitor.price_variation_alert",
                            extra={
                                "sku": sku,
                                "marketplace": marketplace,
                                "prev_price": float(prev_price),
                                "current_price": float(current_price),
                                "variation_pct": float(variation_pct),
                            },
                        )

                return {
                    "sku": sku,
                    "marketplace": marketplace,
                    "price_aed": float(current_price),
                    "prev_price_aed": float(prev_price) if prev_price else None,
                    "variation_pct": float(variation_pct) if variation_pct else None,
                    "alert": alert,
                    "status": "ok",
                }

        finally:
            await engine.dispose()

    try:
        result = asyncio.run(_run())
        logger.info(
            "price_monitor.done",
            extra={
                "sku": sku,
                "marketplace": marketplace,
                "alert": result.get("alert", False),
            },
        )
        return result

    except SoftTimeLimitExceeded:
        logger.warning("price_monitor.soft_timeout", extra={"sku": sku, "marketplace": marketplace})
        raise

    except Exception as exc:
        logger.exception(
            "price_monitor.failed",
            extra={"sku": sku, "marketplace": marketplace, "error": str(exc), "retries": self.request.retries},
        )
        raise self.retry(
            exc=exc,
            countdown=60 * (2 ** self.request.retries),
        )


# ---------------------------------------------------------------------------
# bootstrap_price_monitoring — US-SCR-04-03
# ---------------------------------------------------------------------------


@celery_app.task(
    name="mt.scraper.bootstrap_price_monitoring",
    acks_late=True,
    queue=PRICE_MONITOR_QUEUE,
)
def bootstrap_price_monitoring_task() -> dict:
    """Itera marcas con monitoring_active=True y lanza price_monitor_task por marca × marketplace.

    Disparado por Beat via job_definitions o manualmente desde la API.
    """
    async def _load_active_brands() -> list[str]:
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from sqlalchemy.pool import NullPool

        from app.core.config import settings
        from app.db.models.comparator import CompetitorBrand

        engine = create_async_engine(
            str(settings.DATABASE_URL),
            poolclass=NullPool,
            connect_args={"statement_cache_size": 0},
        )
        session_factory = async_sessionmaker(bind=engine, class_=AsyncSession)
        try:
            async with session_factory() as session:
                stmt = (
                    select(CompetitorBrand.name)
                    .where(CompetitorBrand.is_active.is_(True))
                    .where(CompetitorBrand.monitoring_active.is_(True))
                )
                result = await session.execute(stmt)
                return [row[0] for row in result.all()]
        finally:
            await engine.dispose()

    brand_names = asyncio.run(_load_active_brands())

    if not brand_names:
        logger.info("price_monitor.bootstrap_no_active_brands")
        return {"total": 0, "dispatched": 0}

    dispatched = 0
    for brand_name in brand_names:
        for marketplace in MONITORED_MARKETPLACES:
            price_monitor_task.apply_async(
                args=[brand_name, marketplace],
                queue=PRICE_MONITOR_QUEUE,
            )
            dispatched += 1

    logger.info(
        "price_monitor.bootstrap_dispatched",
        extra={"brands": len(brand_names), "dispatched": dispatched},
    )
    return {"total": len(brand_names), "dispatched": dispatched}


# ---------------------------------------------------------------------------
# refresh_price_daily_stats — US-SCR-04-01
# ---------------------------------------------------------------------------


@celery_app.task(
    name="mt.scraper.refresh_price_daily_stats",
    acks_late=True,
    queue=PRICE_MONITOR_QUEUE,
)
def refresh_price_daily_stats_task() -> dict:
    """REFRESH MATERIALIZED VIEW CONCURRENTLY price_daily_stats.

    Disparado cada hora por Beat via job_definitions (código: refresh_price_daily_stats).
    CONCURRENTLY permite reads mientras se refresca (requiere índice único).
    """
    async def _refresh() -> dict:
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from sqlalchemy.pool import NullPool

        from app.core.config import settings

        engine = create_async_engine(
            str(settings.DATABASE_URL),
            poolclass=NullPool,
            connect_args={"statement_cache_size": 0},
        )
        async with engine.connect() as conn:
            try:
                await conn.execute(
                    text("REFRESH MATERIALIZED VIEW CONCURRENTLY price_daily_stats")
                )
                await conn.commit()
                logger.info("price_monitor.stats_refreshed")
                return {"status": "ok"}
            except Exception as exc:
                # Si la vista no tiene datos suficientes para CONCURRENTLY, reintentar sin él
                logger.warning(
                    "price_monitor.stats_refresh_fallback",
                    extra={"error": str(exc)[:120]},
                )
                await conn.execute(text("REFRESH MATERIALIZED VIEW price_daily_stats"))
                await conn.commit()
                return {"status": "ok_fallback"}
        await engine.dispose()

    try:
        return asyncio.run(_refresh())
    except Exception as exc:
        logger.exception("price_monitor.stats_refresh_failed", extra={"error": str(exc)})
        raise

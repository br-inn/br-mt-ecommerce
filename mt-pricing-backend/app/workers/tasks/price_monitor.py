"""Celery tasks para monitoreo continuo de precios (US-SCR-04-02/03/05).

Cola dedicada: ``scraper.price_monitor`` (separada de ``scraper.brand``).
Tasks:
- ``price_monitor_task``: scrape precio de un SKU en un marketplace, guarda en
  ``price_history_raw``, y detecta variación > 5% vs último precio.
  Si alerta: INSERT en ``price_alerts`` (trigger DB emite pg_notify).
- ``bootstrap_price_monitoring``: itera marcas con ``monitoring_active=True`` y
  lanza ``price_monitor_task`` por marca × marketplace.
- ``refresh_price_daily_stats``: REFRESH MATERIALIZED VIEW CONCURRENTLY price_daily_stats.
- ``send_price_alert_emails``: envía emails via SendGrid para alertas sin notificar.
- ``scraper_heartbeat``: heartbeat cada 26h — actualiza last_run_at en job_definitions.
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

                # ── Brand Extractor mapping (US-SCR-05-02 / AC-4) ─────────
                from app.db.models.comparator import CompetitorBrand
                from app.services.scraper.brand_extractor_service import BrandExtractorService

                brand_svc = BrandExtractorService(session)
                brand_uuid = None
                brand_mapping: dict = {}
                brand_row = await session.execute(
                    select(CompetitorBrand).where(CompetitorBrand.name == sku)
                )
                brand_obj = brand_row.scalar_one_or_none()
                if brand_obj:
                    brand_uuid = brand_obj.id
                    brand_mapping = await brand_svc.get_mapping(brand_obj.id, marketplace) or {}
                    if not brand_mapping:
                        logger.debug(
                            "price_monitor.no_extractor",
                            extra={"sku": sku, "marketplace": marketplace},
                        )

                # ── Rate limiter ───────────────────────────────────────────
                rate_limiter = get_rate_limiter()
                await rate_limiter.acquire(marketplace)

                # ── Fetch precio via adapter ───────────────────────────────
                fetcher = get_fetcher(
                    marketplace,
                    brand_id=brand_uuid,
                    brand_attribute_map=brand_mapping or None,
                )
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

                # ── Enriquecer normalized_jsonb con specs del mapping (AC-4) ─
                if brand_uuid and hasattr(top, "external_id") and top.external_id:
                    from app.db.models.comparator import CompetitorListing

                    listing_row = await session.execute(
                        select(CompetitorListing).where(
                            CompetitorListing.source == marketplace,
                            CompetitorListing.source_id == top.external_id,
                        )
                    )
                    listing_obj = listing_row.scalar_one_or_none()
                    if listing_obj and top.specs:
                        existing_nj = dict(listing_obj.normalized_jsonb or {})
                        existing_nj["specs"] = {**(existing_nj.get("specs") or {}), **top.specs}
                        listing_obj.normalized_jsonb = existing_nj
                        await session.flush()

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

                        # ── INSERT price_alert (trigger emite pg_notify) ───
                        from app.db.models.price_alerts import PriceAlert

                        alert_obj = PriceAlert(
                            match_id=match_id,
                            sku=sku,
                            marketplace=marketplace,
                            alert_type="price_variation",
                            threshold_pct=PRICE_VARIATION_THRESHOLD,
                            prev_price_aed=prev_price,
                            current_price_aed=current_price,
                            variation_pct=variation_pct,
                            channel="email",
                        )
                        session.add(alert_obj)
                        await session.commit()
                        logger.info(
                            "price_monitor.alert_inserted",
                            extra={"sku": sku, "marketplace": marketplace},
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
# _evaluate_extractor_alerts — US-SCR-05-04
# ---------------------------------------------------------------------------

async def _evaluate_extractor_alerts() -> int:
    """Detecta degradación de hit_rate > 20pp y crea/actualiza ExtractorAlerts.

    Umbral: hit_rate < 0.60 (>20pp por debajo de la baseline asumida de 0.80).
    Retorna el número de alertas creadas o actualizadas.
    """
    from decimal import Decimal
    from datetime import datetime, timezone

    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from app.core.config import settings
    from app.db.models.comparator import BrandExtractor, ExtractorAlert

    _BASELINE = Decimal("0.80")
    _MIN_RATE = Decimal("0.60")  # 0.80 - 0.20 = 0.60 → degradación de 20pp

    engine = create_async_engine(
        str(settings.DATABASE_URL),
        poolclass=NullPool,
        connect_args={"statement_cache_size": 0},
    )
    session_factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, autoflush=False, expire_on_commit=False
    )
    alerts_modified = 0
    try:
        async with session_factory() as session:
            now = datetime.now(timezone.utc)
            result = await session.execute(select(BrandExtractor))
            extractors = result.scalars().all()

            # Pre-cargar todas las alertas activas en un solo query (evita N+1)
            alerts_result = await session.execute(
                select(ExtractorAlert).where(ExtractorAlert.resolved_at.is_(None))
            )
            alerts_by_key: dict[tuple, ExtractorAlert] = {
                (a.brand_id, a.marketplace): a
                for a in alerts_result.scalars().all()
            }

            for ext in extractors:
                current_rate = ext.hit_rate
                existing_alert = alerts_by_key.get((ext.brand_id, ext.marketplace))

                if current_rate < _MIN_RATE:
                    if existing_alert is None:
                        delta = (_BASELINE - current_rate) * 100
                        session.add(ExtractorAlert(
                            brand_id=ext.brand_id,
                            marketplace=ext.marketplace,
                            triggered_at=now,
                            hit_rate_now=current_rate,
                            hit_rate_baseline=_BASELINE,
                            delta_pp=delta,
                        ))
                    else:
                        existing_alert.hit_rate_now = current_rate
                        existing_alert.delta_pp = (
                            existing_alert.hit_rate_baseline - current_rate
                        ) * 100
                    alerts_modified += 1

            await session.commit()
    finally:
        await engine.dispose()

    return alerts_modified


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

    # ── Evaluar degradación de hit_rate en extractores (US-SCR-05-04 / AC-2) ─
    try:
        alerts_modified = asyncio.run(_evaluate_extractor_alerts())
        if alerts_modified:
            logger.info(
                "price_monitor.extractor_alerts_evaluated",
                extra={"alerts_modified": alerts_modified},
            )
    except Exception as exc:
        logger.warning(
            "price_monitor.extractor_alerts_failed",
            extra={"error": str(exc)[:200]},
        )
        alerts_modified = 0

    return {"total": len(brand_names), "dispatched": dispatched, "alerts_modified": alerts_modified}


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


# ---------------------------------------------------------------------------
# send_price_alert_emails — US-SCR-04-05
# ---------------------------------------------------------------------------


@celery_app.task(
    name="mt.scraper.send_price_alert_emails",
    acks_late=True,
    queue=PRICE_MONITOR_QUEUE,
)
def send_price_alert_emails_task() -> dict:
    """Envía emails via SendGrid para price_alerts con notified_at IS NULL.

    Si SENDGRID_API_KEY no está configurado: log structured warning, no crash.
    Dispara cada 5 min via job_definitions (código: send_price_alert_emails).
    """
    import os

    async def _send() -> dict:
        from datetime import timezone

        from sqlalchemy import select, update
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from sqlalchemy.pool import NullPool

        from app.core.config import settings
        from app.db.models.price_alerts import PriceAlert

        sendgrid_key = os.environ.get("SENDGRID_API_KEY") or getattr(settings, "SENDGRID_API_KEY", None)
        if not sendgrid_key:
            logger.warning(
                "send_price_alert_emails.no_sendgrid_key",
                extra={"action": "skip_send", "reason": "SENDGRID_API_KEY not configured"},
            )
            return {"status": "skipped", "reason": "no_sendgrid_key"}

        engine = create_async_engine(
            str(settings.DATABASE_URL),
            poolclass=NullPool,
            connect_args={"statement_cache_size": 0},
        )
        session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
        try:
            async with session_factory() as session:
                # Cargar alertas pendientes de notificación
                stmt = (
                    select(PriceAlert)
                    .where(PriceAlert.notified_at.is_(None))
                    .order_by(PriceAlert.triggered_at.asc())
                    .limit(50)
                )
                result = await session.execute(stmt)
                pending = list(result.scalars().all())

                if not pending:
                    return {"status": "ok", "sent": 0}

                sent = 0
                failed_ids = []

                try:
                    import sendgrid  # type: ignore[import-untyped]
                    from sendgrid.helpers.mail import Mail  # type: ignore[import-untyped]

                    sg = sendgrid.SendGridAPIClient(api_key=sendgrid_key)
                    from_email = getattr(settings, "SENDGRID_FROM_EMAIL", "noreply@mt-ecommerce.ae")
                    to_email = getattr(settings, "PRICE_ALERT_EMAIL", "pricing@mt-ecommerce.ae")

                    for alert in pending:
                        subject = (
                            f"[MT Price Alert] {alert.sku or 'Unknown'} "
                            f"on {alert.marketplace} — "
                            f"{float(alert.variation_pct or 0):.1%} variation"
                        )
                        body = (
                            f"Price alert triggered:\n\n"
                            f"  SKU:        {alert.sku}\n"
                            f"  Marketplace: {alert.marketplace}\n"
                            f"  Previous:   AED {alert.prev_price_aed}\n"
                            f"  Current:    AED {alert.current_price_aed}\n"
                            f"  Variation:  {float(alert.variation_pct or 0):.2%}\n"
                            f"  Triggered:  {alert.triggered_at.isoformat()}\n"
                        )
                        message = Mail(
                            from_email=from_email,
                            to_emails=to_email,
                            subject=subject,
                            plain_text_content=body,
                        )
                        response = sg.send(message)
                        if response.status_code in (200, 202):
                            alert.notified_at = __import__("datetime").datetime.now(tz=timezone.utc)
                            sent += 1
                        else:
                            failed_ids.append(str(alert.id))
                            logger.warning(
                                "send_price_alert_emails.sendgrid_error",
                                extra={"alert_id": str(alert.id), "status_code": response.status_code},
                            )

                except ImportError:
                    logger.warning(
                        "send_price_alert_emails.sendgrid_not_installed",
                        extra={"action": "skip_send", "reason": "sendgrid package not available"},
                    )
                    return {"status": "skipped", "reason": "sendgrid_not_installed"}

                await session.commit()
                logger.info(
                    "send_price_alert_emails.done",
                    extra={"sent": sent, "failed": len(failed_ids)},
                )
                return {"status": "ok", "sent": sent, "failed": len(failed_ids)}
        finally:
            await engine.dispose()

    try:
        return asyncio.run(_send())
    except Exception as exc:
        logger.exception("send_price_alert_emails.failed", extra={"error": str(exc)})
        raise


# ---------------------------------------------------------------------------
# scraper_heartbeat — US-SCR-04-05
# ---------------------------------------------------------------------------


@celery_app.task(
    name="mt.scraper.scraper_heartbeat",
    acks_late=True,
    queue=PRICE_MONITOR_QUEUE,
)
def scraper_heartbeat_task() -> dict:
    """Heartbeat del scraper — actualiza last_run_at en job_definitions.

    Corre cada 26h. Si falla → log CRITICAL (no propagar excepción para evitar
    retry loops que consuman workers).
    """
    async def _heartbeat() -> dict:
        from datetime import datetime, timezone

        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from sqlalchemy.pool import NullPool

        from app.core.config import settings

        now_utc = datetime.now(tz=timezone.utc)
        engine = create_async_engine(
            str(settings.DATABASE_URL),
            poolclass=NullPool,
            connect_args={"statement_cache_size": 0},
        )
        async with engine.connect() as conn:
            await conn.execute(
                text("""
                    UPDATE job_definitions
                       SET last_run_at = :now
                     WHERE code IN (
                         'scraper_heartbeat',
                         'bootstrap_price_monitoring',
                         'refresh_price_daily_stats',
                         'send_price_alert_emails'
                     )
                """),
                {"now": now_utc},
            )
            await conn.commit()
        await engine.dispose()
        logger.info("scraper_heartbeat.ok", extra={"ts": now_utc.isoformat()})
        return {"status": "ok", "ts": now_utc.isoformat()}

    try:
        return asyncio.run(_heartbeat())
    except Exception as exc:
        logger.critical(
            "scraper_heartbeat.failed",
            extra={"error": str(exc)},
            exc_info=True,
        )
        # No re-raise — heartbeat failure no debe derribar el worker
        return {"status": "error", "error": str(exc)}

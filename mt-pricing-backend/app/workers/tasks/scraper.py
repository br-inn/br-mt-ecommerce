"""Tasks Celery para el scraper Amazon UAE (EP-SCR-01).

Queue: ``comparator`` — comparte workers con el pipeline de matching.
Routing: ``mt.scraper.*`` → queue ``comparator`` (ver worker.py task_routes).

Tasks:
- ``scrape_sku_task``: scraping de un SKU individual — llama a MatchService.
- ``scrape_batch_task``: fan-out — crea un group de ``scrape_sku_task``.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from celery import group as celery_group
from celery.exceptions import SoftTimeLimitExceeded

from app.workers.worker import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro: Any) -> Any:
    """Run a coroutine synchronously from within a Celery task."""
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Task individual — un SKU
# ---------------------------------------------------------------------------


@celery_app.task(
    bind=True,
    name="mt.scraper.scrape_sku",
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
    queue="comparator",
)
def scrape_sku_task(self, sku: str, *, force: bool = False) -> dict:  # type: ignore[override]
    """Scraping de un SKU individual en Amazon UAE.

    Args:
        sku: Código de producto MT a buscar.
        force: Si True, re-scrapea aunque ya existan candidatos recientes.

    Returns:
        dict con ``sku``, ``status`` y ``candidates`` (lista de dicts).

    Retry policy:
        Hasta 3 reintentos con backoff exponencial (60s base).
        SoftTimeLimitExceeded se propaga como fallo sin reintentar.
    """
    logger.info("scraper.sku_start", extra={"sku": sku, "force": force})

    async def _run_async() -> list[dict]:
        from app.core.config import settings
        from app.repositories.feature_flags import FeatureFlagRepository
        from app.services.feature_flags.flag_service import (
            FlagService,
            set_default_service,
            warmup_local_cache,
        )
        from app.services.matching.adapter_registry import get_fetcher
        from app.services.matching.match_service import MatchService
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from sqlalchemy.pool import NullPool

        # NullPool: cada sesión crea una conexión fresca y la cierra al salir.
        # Evita que conexiones corruptas del warmup de flags se reciclen a la
        # sesión de scraping (ConnectionDoesNotExistError). El overhead de
        # reconexión es despreciable para un task de 30-60s.
        # statement_cache_size=0 obligatorio para Supabase PgBouncer transaction mode.
        engine = create_async_engine(
            str(settings.DATABASE_URL),
            poolclass=NullPool,
            connect_args={
                "statement_cache_size": 0,
                "server_settings": {
                    "application_name": "mt-scraper-worker",
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
            # ── Warmup flags — sesión independiente ──────────────────────────
            # Con NullPool cada sesión tiene su propia conexión; si el warmup
            # falla la conexión se cierra y no contamina la sesión de scraping.
            try:
                async with session_factory() as flag_session:
                    flag_repo = FeatureFlagRepository(flag_session)
                    flag_svc = FlagService(flag_repo=flag_repo, redis=None)
                    set_default_service(flag_svc)
                    all_flags = await flag_svc.get_all()
                    warmup_local_cache(all_flags)
            except Exception:
                logger.warning("scraper.flags_warmup_failed", extra={"sku": sku})

            # ── Scraping — conexión fresca garantizada ────────────────────────
            async with session_factory() as session:
                fetchers = [get_fetcher("amazon_uae"), get_fetcher("noon_uae")]
                service = MatchService(session, fetchers=fetchers)
                rows = await service.refresh_candidates(sku)
                result = [
                    {
                        "id": str(r.id),
                        "channel": r.channel,
                        "external_id": r.external_id,
                        "score": r.score,
                        "status": r.status,
                    }
                    for r in rows
                ]
                await session.commit()
        finally:
            await engine.dispose()

        return result

    try:
        candidates = asyncio.run(_run_async())

        logger.info(
            "scraper.sku_done",
            extra={"sku": sku, "candidates_found": len(candidates)},
        )
        return {
            "sku": sku,
            "status": "ok",
            "candidates": candidates,
        }

    except SoftTimeLimitExceeded:
        logger.warning("scraper.sku_soft_timeout", extra={"sku": sku})
        raise  # no reintentar en timeout — dejar que Celery lo marque como failed

    except Exception as exc:
        logger.exception(
            "scraper.sku_failed",
            extra={"sku": sku, "error": str(exc), "retries": self.request.retries},
        )
        raise self.retry(
            exc=exc,
            countdown=60 * (2 ** self.request.retries),  # backoff exponencial
        )


# ---------------------------------------------------------------------------
# Task batch — fan-out
# ---------------------------------------------------------------------------


@celery_app.task(
    name="mt.scraper.scrape_batch",
    acks_late=True,
    queue="comparator",
)
def scrape_batch_task(skus: list[str], *, force: bool = False) -> dict:
    """Fan-out: crea un group de ``scrape_sku_task`` por cada SKU.

    Puede ser disparado directamente por Beat (job_definitions) o desde la
    API (``POST /api/v1/scraper/run``).

    Args:
        skus: Lista de SKUs a procesar.
        force: Propagado a cada ``scrape_sku_task``.

    Returns:
        dict con ``group_id`` y ``total`` de tasks encoladas.
    """
    if not skus:
        logger.warning("scraper.batch_empty")
        return {"group_id": None, "total": 0}

    job = celery_group(
        scrape_sku_task.s(sku, force=force) for sku in skus
    ).apply_async(queue="comparator")

    # Persistir GroupResult para que pueda ser consultado por id
    job.save()

    logger.info(
        "scraper.batch_dispatched",
        extra={"group_id": job.id, "total": len(skus)},
    )
    return {"group_id": job.id, "total": len(skus)}


# ---------------------------------------------------------------------------
# Helpers para brand scraping
# ---------------------------------------------------------------------------


def _build_brand_query(brand: object) -> "Query":
    """Construye el Query para buscar todos los productos de una marca en Amazon."""
    from app.services.matching.ports import Query

    return Query(
        text=brand.amazon_search_term or brand.name,  # type: ignore[union-attr]
        source="amazon_uae",
        type="brand",
        dept=brand.amazon_dept,  # type: ignore[union-attr]
        category_node=brand.amazon_category_node,  # type: ignore[union-attr]
    )


# ---------------------------------------------------------------------------
# Task individual — una marca competidora
# ---------------------------------------------------------------------------


@celery_app.task(
    bind=True,
    name="mt.scraper.scrape_brand",
    max_retries=3,
    default_retry_delay=120,
    acks_late=True,
    queue="scraper",
)
def scrape_brand_task(self, brand_id: str, *, force: bool = False) -> dict:  # type: ignore[override]
    """Scraping de todos los productos de una marca competidora en Amazon UAE.

    Busca en Amazon usando ``amazon_search_term`` (o ``name``) filtrado por
    ``amazon_dept`` y opcionalmente ``amazon_category_node``. Hace upsert de
    los resultados en ``competitor_listings`` con FK a la marca.

    Args:
        brand_id: UUID de la marca en ``competitor_brands``.
        force: Reservado para uso futuro (re-scrapear aunque sea reciente).
    """
    logger.info("scraper.brand_start", extra={"brand_id": brand_id, "force": force})

    async def _run_async() -> dict:
        from uuid import UUID

        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from sqlalchemy.pool import NullPool

        from app.core.config import settings
        from app.db.models.comparator import CompetitorBrand
        from app.repositories.competitor_brands import CompetitorBrandRepository
        from app.repositories.feature_flags import FeatureFlagRepository
        from app.services.feature_flags.flag_service import (
            FlagService,
            set_default_service,
            warmup_local_cache,
        )
        from app.services.matching.adapter_registry import get_fetcher

        engine = create_async_engine(
            str(settings.DATABASE_URL),
            poolclass=NullPool,
            connect_args={
                "statement_cache_size": 0,
                "server_settings": {
                    "application_name": "mt-scraper-worker",
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
        upserted = 0
        try:
            # ── Warmup flags ────────────────────────────────────────────────
            try:
                async with session_factory() as flag_session:
                    flag_repo = FeatureFlagRepository(flag_session)
                    flag_svc = FlagService(flag_repo=flag_repo, redis=None)
                    set_default_service(flag_svc)
                    all_flags = await flag_svc.get_all()
                    warmup_local_cache(all_flags)
            except Exception:
                logger.warning("scraper.brand.flags_warmup_failed", extra={"brand_id": brand_id})

            # ── Scraping ────────────────────────────────────────────────────
            async with session_factory() as session:
                repo = CompetitorBrandRepository(session)
                brand = await repo.get(UUID(brand_id))

                if not brand:
                    logger.warning("scraper.brand.not_found", extra={"brand_id": brand_id})
                    return {"brand_id": brand_id, "status": "not_found", "upserted": 0}

                if not brand.is_active:
                    logger.info("scraper.brand.inactive", extra={"brand_id": brand_id})
                    return {"brand_id": brand_id, "status": "inactive", "upserted": 0}

                # ── Brand Extractor mapping (US-SCR-05-02) ──────────────────
                from app.services.scraper.brand_extractor_service import BrandExtractorService

                svc = BrandExtractorService(session)
                mapping = await svc.get_mapping(brand.id, "amazon_uae")
                if mapping is None:
                    logger.debug(
                        "scraper.brand.no_extractor",
                        extra={"brand_id": brand_id, "marketplace": "amazon_uae"},
                    )

                # ── Rate limiter + circuit breaker ──────────────────────────
                from urllib.parse import urlparse

                from app.services.scraper.circuit_breaker import (
                    ScraperCircuitOpenError,
                    get_circuit_breaker,
                    get_proxy_pool,
                )
                from app.services.scraper.rate_limiter import get_rate_limiter

                fetcher = get_fetcher("amazon_uae", brand_id=brand.id, brand_attribute_map=mapping)
                query = _build_brand_query(brand)

                # Determinar dominio para rate limiter / circuit breaker
                _domain = "amazon_uae"

                rate_limiter = get_rate_limiter()
                circuit_breaker = get_circuit_breaker()
                proxy_pool = get_proxy_pool()

                try:
                    await circuit_breaker.check_and_raise(_domain)
                except ScraperCircuitOpenError:
                    logger.warning(
                        "scraper.brand.circuit_open",
                        extra={"brand_id": brand_id, "domain": _domain},
                    )
                    return {"brand_id": brand_id, "status": "circuit_open", "upserted": 0}

                # Adquirir token de rate limiter antes de hacer el request
                await rate_limiter.acquire(_domain)

                # Obtener proxy rotativo si está disponible
                _proxy = await proxy_pool.get_proxy()
                if _proxy:
                    logger.debug(
                        "scraper.brand.using_proxy",
                        extra={"brand_id": brand_id, "proxy": _proxy[:30]},
                    )

                try:
                    candidates = await fetcher.fetch(query)
                    await circuit_breaker.record_success(_domain)
                except Exception as fetch_exc:
                    await circuit_breaker.record_failure(_domain)
                    # Cool down the proxy that was in use so it is skipped
                    # for the next hour before being retried.
                    if _proxy:
                        try:
                            await proxy_pool.mark_proxy_failed(_proxy)
                        except Exception:
                            pass
                    raise fetch_exc

                for candidate in candidates:
                    await repo.upsert_listing(candidate, competitor_brand_id=brand.id)
                    upserted += 1

                # ── Record extractor hit rate per candidate (AC-2) ─────────
                if mapping is not None:
                    canonical_fields = {
                        v["field"]
                        for v in mapping.values()
                        if isinstance(v, dict) and "field" in v
                    }
                    for candidate in candidates:
                        hit = bool(canonical_fields & set(candidate.specs.keys()))
                        await svc.record_hit(brand.id, "amazon_uae", hit=hit)

                await repo.touch_scraped(brand)
                await session.commit()

        finally:
            await engine.dispose()

        return {"brand_id": brand_id, "status": "ok", "upserted": upserted}

    try:
        result = asyncio.run(_run_async())
        logger.info(
            "scraper.brand_done",
            extra={"brand_id": brand_id, "upserted": result.get("upserted", 0)},
        )
        return result

    except SoftTimeLimitExceeded:
        logger.warning("scraper.brand_soft_timeout", extra={"brand_id": brand_id})
        raise

    except Exception as exc:
        logger.exception(
            "scraper.brand_failed",
            extra={"brand_id": brand_id, "error": str(exc), "retries": self.request.retries},
        )
        raise self.retry(
            exc=exc,
            countdown=120 * (2 ** self.request.retries),
        )


# ---------------------------------------------------------------------------
# Task batch — fan-out de marcas
# ---------------------------------------------------------------------------


@celery_app.task(
    name="mt.scraper.scrape_brands_batch",
    acks_late=True,
    queue="scraper",
)
def scrape_brands_batch_task(brand_ids: list[str] | None = None, *, force: bool = False) -> dict:
    """Fan-out de ``scrape_brand_task`` para todas las marcas activas o las indicadas.

    Puede ser disparado por Beat (job_definitions) o desde la API
    (``POST /api/v1/competitor-brands/run``).
    brand_ids=None → carga todas las marcas activas desde DB.
    """
    if brand_ids is None:
        async def _load_active() -> list[str]:
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
                    stmt = select(CompetitorBrand.id).where(CompetitorBrand.is_active.is_(True))
                    result = await session.execute(stmt)
                    return [str(row[0]) for row in result.all()]
            finally:
                await engine.dispose()

        brand_ids = asyncio.run(_load_active())

    if not brand_ids:
        logger.warning("scraper.brands_batch_empty")
        return {"group_id": None, "total": 0}

    job = celery_group(
        scrape_brand_task.s(bid, force=force) for bid in brand_ids
    ).apply_async(queue="scraper")
    job.save()

    logger.info(
        "scraper.brands_batch_dispatched",
        extra={"group_id": job.id, "total": len(brand_ids)},
    )
    return {"group_id": job.id, "total": len(brand_ids)}


# ---------------------------------------------------------------------------
# Task — Bootstrap Scan: genera attribute-mapping para una marca via Claude
# ---------------------------------------------------------------------------


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    max_retries=2,
    default_retry_delay=60,
    name="mt.scraper.generate_brand_extractor",
)
def generate_brand_extractor_task(self: Any, brand_id: str, marketplace: str = "amazon_uae") -> dict[str, Any]:
    """Bootstrap: genera el JSON attribute-mapping para una marca via Claude (US-SCR-05-01).

    Ejecutado al hacer Bootstrap Scan desde la UI. Fetches 3 sample ASINs
    del brand, extrae raw_pairs, y llama a BrandExtractorService.bootstrap().
    """
    from uuid import UUID as _UUID

    async def _inner() -> dict[str, Any]:
        from sqlalchemy import select as _select

        from app.core.db import AsyncSessionLocal
        from app.db.models.comparator import CompetitorBrand
        from app.services.matching.adapter_registry import get_fetcher
        from app.services.matching.ports import Query
        from app.services.scraper.brand_extractor_service import BrandExtractorService

        async with AsyncSessionLocal() as session:
            # Load brand
            r = await session.execute(
                _select(CompetitorBrand).where(CompetitorBrand.id == _UUID(brand_id))
            )
            brand = r.scalar_one_or_none()
            if not brand:
                return {"error": f"Brand {brand_id} not found"}

            # Fetch sample products for this brand (up to 3 ASINs)
            fetcher = get_fetcher(marketplace)
            query = Query(
                text=brand.effective_search_term,
                source=marketplace,
                type="brand",
                dept=brand.amazon_dept,
                category_node=brand.amazon_category_node,
            )
            try:
                candidates = await fetcher.fetch(query)
            except Exception as exc:  # noqa: BLE001
                return {"error": f"Fetch failed: {exc}"}

            if not candidates:
                return {"error": "No candidates fetched — cannot generate extractor"}

            # Collect raw_pairs from up to 3 candidates
            sample_raw_pairs: list[dict] = []
            sample_asins: list[str] = []
            for cand in candidates[:3]:
                # raw_pairs may be in raw_payload or specs
                asins = cand.raw_payload.get("asin")
                if asins:
                    sample_asins.append(asins)
                # Build flat list of {"label": k, "value": v} from specs
                for k, v in cand.specs.items():
                    sample_raw_pairs.append({"label": k, "value": str(v), "asin": asins})

            if not sample_raw_pairs:
                return {"error": "No specs/raw_pairs collected from candidates"}

            # Generate + save mapping via Claude
            svc = BrandExtractorService(session)
            attribute_map = await svc.bootstrap(
                brand_id=_UUID(brand_id),
                brand_name=brand.name,
                marketplace=marketplace,
                sample_raw_pairs=sample_raw_pairs,
                sample_asins=sample_asins,
            )

            return {
                "brand_id": brand_id,
                "brand_name": brand.name,
                "marketplace": marketplace,
                "mappings_generated": len(attribute_map),
                "sample_asins": sample_asins,
            }

    return _run_async(_inner())


# ---------------------------------------------------------------------------
# Task configurable — un ScraperSource
# ---------------------------------------------------------------------------


async def _scrape_source_async(
    session,
    source_id: str,
    *,
    search_text: str,
    html_fetcher=None,
) -> dict:
    """Ejecuta un ScraperSource configurable y upserta los listings resultantes.

    Reutiliza el contrato CandidateRaw → CompetitorListing del scraper existente.
    Requiere que la source tenga ``competitor_brand_id`` (perfil competitor_price).
    """
    from uuid import UUID

    from app.repositories.competitor_brands import CompetitorBrandRepository
    from app.repositories.scraper_sources import ScraperSourceRepository
    from app.services.matching.adapter_registry import resolve_fetcher
    from app.services.matching.ports import Query

    src_repo = ScraperSourceRepository(session)
    source = await src_repo.get(UUID(source_id))
    if source is None:
        return {"source_id": source_id, "status": "not_found", "upserted": 0}
    if source.status != "active":
        return {"source_id": source_id, "status": "inactive", "upserted": 0}
    if source.competitor_brand_id is None:
        return {"source_id": source_id, "status": "no_brand", "upserted": 0}

    fetcher = await resolve_fetcher(source.slug, session, html_fetcher=html_fetcher)
    query = Query(text=search_text, source=source.slug)
    candidates = await fetcher.fetch(query)

    brand_repo = CompetitorBrandRepository(session)
    upserted = 0
    for candidate in candidates:
        await brand_repo.upsert_listing(
            candidate, competitor_brand_id=source.competitor_brand_id
        )
        upserted += 1
    await session.commit()
    return {"source_id": source_id, "status": "ok", "upserted": upserted}


@celery_app.task(
    bind=True,
    name="mt.scraper.scrape_source",
    max_retries=3,
    default_retry_delay=120,
    acks_late=True,
    queue="scraper",
)
def scrape_source_task(self, source_id: str, *, search_text: str) -> dict:  # type: ignore[override]
    """Celery task: ejecuta un ScraperSource configurable."""
    logger.info("scraper.source_start", extra={"source_id": source_id})

    async def _run() -> dict:
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from sqlalchemy.pool import NullPool

        from app.core.config import settings

        engine = create_async_engine(
            str(settings.DATABASE_URL),
            poolclass=NullPool,
            connect_args={
                "statement_cache_size": 0,
                "server_settings": {
                    "application_name": "mt-scraper-worker",
                    "timezone": "UTC",
                },
            },
        )
        session_factory = async_sessionmaker(
            bind=engine, expire_on_commit=False, autoflush=False, class_=AsyncSession
        )
        try:
            async with session_factory() as session:
                return await _scrape_source_async(
                    session, source_id, search_text=search_text
                )
        finally:
            await engine.dispose()

    try:
        result = asyncio.run(_run())
        logger.info(
            "scraper.source_done",
            extra={"source_id": source_id, "upserted": result.get("upserted", 0)},
        )
        return result
    except SoftTimeLimitExceeded:
        logger.warning("scraper.source_soft_timeout", extra={"source_id": source_id})
        raise
    except Exception as exc:
        logger.exception(
            "scraper.source_failed",
            extra={"source_id": source_id, "error": str(exc)},
        )
        raise self.retry(exc=exc, countdown=120 * (2 ** self.request.retries))

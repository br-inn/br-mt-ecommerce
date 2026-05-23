"""FastAPI application factory + lifespan + middleware + observability.

Entry point para `uvicorn app.main:app`. Lifespan inicializa logging y Sentry
ANTES de aceptar tráfico. El middleware de request_id se monta antes de CORS
para que los logs de errores en CORS también lleven request_id.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.routes import router as api_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.core.metrics import setup_metrics
from app.core.middleware import CacheControlMiddleware, RequestContextMiddleware
from app.core.redis import close_redis
from app.core.sentry import configure_sentry
from app.db import dispose_engine
from app.db.session import get_sessionmaker
from app.repositories.feature_flags import FeatureFlagRepository
from app.services.feature_flags.flag_service import (
    FlagService,
    set_default_service,
    warmup_local_cache,
)
from app.services.graphrag.adapters import shutdown as graphrag_shutdown


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Inicializa observabilidad al arrancar; cierra pools al apagar."""
    configure_logging()
    configure_sentry()

    # Bootstrap feature flags — rellena _local_cache desde DB para que
    # adapter_registry pueda leer flags síncronamente sin tocar Redis/DB.
    try:
        from app.core.redis import get_redis

        redis_client = get_redis()
        async_session = get_sessionmaker()
        async with async_session() as session:
            flag_repo = FeatureFlagRepository(session)
            flag_svc = FlagService(flag_repo=flag_repo, redis=redis_client)
            set_default_service(flag_svc)
            snapshot = await flag_svc.get_all()
            warmup_local_cache(snapshot)
    except Exception:
        import logging

        logging.getLogger(__name__).warning(
            "feature_flags.bootstrap_failed — usando defaults (todo False)"
        )

    # Warm up cross-encoder reranker if enabled
    import logging as _logging

    _lifespan_logger = _logging.getLogger(__name__)
    from app.core.config import settings as _settings

    if _settings.ENABLE_CROSS_ENCODER_RERANKER:
        try:
            from app.services.matching.cross_encoder_reranker import CrossEncoderReranker

            CrossEncoderReranker()  # triggers model load
            _lifespan_logger.info("Cross-encoder reranker warmed up")
        except Exception as _e:
            _lifespan_logger.warning("Cross-encoder warmup failed: %s", _e)

    yield
    await dispose_engine()
    await close_redis()
    graphrag_shutdown()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="MT Middle East — MDM + Pricing API",
    lifespan=lifespan,
    docs_url="/docs" if settings.ENABLE_DOCS else None,
    redoc_url="/redoc" if settings.ENABLE_DOCS else None,
    openapi_url="/openapi.json" if settings.ENABLE_DOCS else None,
)

# --- Middleware --------------------------------------------------------------
# Orden importa: el último `add_middleware` envuelve por fuera. Queremos
# request_id por fuera para que CORS errors también queden trackeados.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[
        "X-Request-ID",
        "X-RateLimit-Remaining",
        "Content-Disposition",
        "X-Rows-Exported",
        "X-Rows-Skipped",
    ],
)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(CacheControlMiddleware)

# --- Métricas Prometheus ----------------------------------------------------
# Se monta tras la app — instrumentator se engancha al middleware stack y expone
# `/metrics`. Excluye healthchecks del scrape (ver app/core/metrics.py).
setup_metrics(app)

# --- Routers ----------------------------------------------------------------
# Health: público en raíz, sin prefijo /api/v1 (ADR-048).
app.include_router(health_router, tags=["Health"])
# API funcional: prefijo /api/v1 — los routers concretos se enchufan en
# `app/api/routes/__init__.py` (Agente F/G).
app.include_router(api_router, prefix="/api/v1")

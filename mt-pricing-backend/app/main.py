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
from app.core.middleware import RequestContextMiddleware
from app.core.redis import close_redis
from app.core.sentry import configure_sentry
from app.db import dispose_engine
from app.services.graphrag.adapters import shutdown as graphrag_shutdown


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Inicializa observabilidad al arrancar; cierra pools al apagar."""
    configure_logging()
    configure_sentry()
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
    expose_headers=["X-Request-ID", "X-RateLimit-Remaining"],
)
app.add_middleware(RequestContextMiddleware)

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

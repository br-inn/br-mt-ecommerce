"""Admin Scraper — health dashboard + CRUD proxies (US-SCR-03-05).

Endpoints:
- GET  /api/v1/admin/scraper-health  — estado circuit breakers + stats por dominio
- GET  /api/v1/admin/proxies         — lista de proxies en el pool
- POST /api/v1/admin/proxies         — añadir proxy al pool
- DELETE /api/v1/admin/proxies/{proxy_b64} — eliminar proxy del pool
"""

from __future__ import annotations

import base64
import logging
from typing import Annotated

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.deps import require_permissions
from app.core.config import settings
from app.db.models.user import User
from app.services.scraper.circuit_breaker import (
    CircuitState,
    get_circuit_breaker,
    get_proxy_pool,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin-scraper"])

# Dominios monitoreados activamente
_MONITORED_DOMAINS = ["amazon_uae", "noon_uae"]

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class DomainHealthSchema(BaseModel):
    domain: str
    circuit_state: str
    failures: int
    failure_threshold: int
    opened_at: float | None
    recovery_timeout: int
    # Stats adicionales (24h) — pobladas desde Redis si existen
    requests_24h: int = 0
    errors_24h: int = 0
    error_rate: float = 0.0


class ScraperHealthResponse(BaseModel):
    domains: list[DomainHealthSchema]
    proxy_count: int
    rate_limit_rpm: int
    cb_failure_threshold: int
    cb_recovery_timeout: int


class ProxyAddRequest(BaseModel):
    proxy: str
    """URL completa del proxy, ej: http://user:pass@host:port"""


class ProxyItem(BaseModel):
    proxy: str
    proxy_b64: str


class ProxyListResponse(BaseModel):
    proxies: list[ProxyItem]
    total: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_domain_stats_24h(r: aioredis.Redis, domain: str) -> dict:
    """Intenta leer stats de las últimas 24h desde Redis counters."""
    try:
        requests_key = f"stats:{domain}:requests_24h"
        errors_key = f"stats:{domain}:errors_24h"
        req_raw, err_raw = await r.mget(requests_key, errors_key)
        requests = int(req_raw) if req_raw else 0
        errors = int(err_raw) if err_raw else 0
        error_rate = (errors / requests) if requests > 0 else 0.0
        return {"requests_24h": requests, "errors_24h": errors, "error_rate": round(error_rate, 4)}
    except Exception:
        return {"requests_24h": 0, "errors_24h": 0, "error_rate": 0.0}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/scraper-health",
    response_model=ScraperHealthResponse,
    operation_id="getScraperHealth",
)
async def get_scraper_health(
    _user: Annotated[User, Depends(require_permissions("admin:read"))],
) -> ScraperHealthResponse:
    """Estado del circuit breaker, stats por dominio, y tamaño del proxy pool."""
    cb = get_circuit_breaker()
    proxy_pool = get_proxy_pool()

    domains: list[DomainHealthSchema] = []

    # Obtener Redis directo para stats
    try:
        r_direct = aioredis.from_url(
            str(settings.REDIS_URL), encoding="utf-8", decode_responses=True
        )
        for domain in _MONITORED_DOMAINS:
            stats = await cb.get_stats(domain)
            extra_stats = await _get_domain_stats_24h(r_direct, domain)
            domains.append(
                DomainHealthSchema(
                    domain=domain,
                    circuit_state=stats["state"],
                    failures=stats["failures"],
                    failure_threshold=stats["failure_threshold"],
                    opened_at=stats.get("opened_at"),
                    recovery_timeout=stats["recovery_timeout"],
                    **extra_stats,
                )
            )
        await r_direct.aclose()
    except Exception as exc:
        logger.warning("admin.scraper_health.redis_error", extra={"error": str(exc)[:120]})
        for domain in _MONITORED_DOMAINS:
            domains.append(
                DomainHealthSchema(
                    domain=domain,
                    circuit_state="unknown",
                    failures=0,
                    failure_threshold=getattr(settings, "SCRAPER_CB_FAILURE_THRESHOLD", 5),
                    opened_at=None,
                    recovery_timeout=getattr(settings, "SCRAPER_CB_RECOVERY_TIMEOUT", 60),
                )
            )

    proxy_count = await proxy_pool.size()

    return ScraperHealthResponse(
        domains=domains,
        proxy_count=proxy_count,
        rate_limit_rpm=getattr(settings, "SCRAPER_RATE_LIMIT_RPM", 20),
        cb_failure_threshold=getattr(settings, "SCRAPER_CB_FAILURE_THRESHOLD", 5),
        cb_recovery_timeout=getattr(settings, "SCRAPER_CB_RECOVERY_TIMEOUT", 60),
    )


@router.post(
    "/scraper-health/circuit/{domain}/reset",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    operation_id="resetCircuitBreaker",
)
async def reset_circuit_breaker(
    domain: str,
    _user: Annotated[User, Depends(require_permissions("admin:read"))],
) -> None:
    """Fuerza el circuit breaker de un dominio a CLOSED (reset manual)."""
    if domain not in _MONITORED_DOMAINS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Domain '{domain}' no monitoreado"
        )
    cb = get_circuit_breaker()
    await cb.force_close(domain)
    logger.info("admin.circuit_breaker.reset", extra={"domain": domain})


class SuspendCircuitResponse(BaseModel):
    domain: str
    state: str
    forced: bool


@router.post(
    "/scraper-health/circuit/{domain}/suspend",
    response_model=SuspendCircuitResponse,
    operation_id="suspendCircuitBreaker",
)
async def suspend_circuit_breaker(
    domain: str,
    _user: Annotated[User, Depends(require_permissions("admin:read"))],
) -> SuspendCircuitResponse:
    """Fuerza el circuit breaker de un dominio a OPEN de forma indefinida (pausar canal).

    A diferencia de un OPEN automático (que se recupera tras ``recovery_timeout``),
    este estado permanece hasta que se llame a ``/reset`` manualmente.
    """
    if domain not in _MONITORED_DOMAINS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Domain '{domain}' no monitoreado"
        )
    cb = get_circuit_breaker()
    await cb.force_open(domain)
    logger.info("admin.circuit_breaker.suspended", extra={"domain": domain})
    return SuspendCircuitResponse(domain=domain, state=CircuitState.OPEN, forced=True)


@router.get(
    "/proxies",
    response_model=ProxyListResponse,
    operation_id="listProxies",
)
async def list_proxies(
    _user: Annotated[User, Depends(require_permissions("admin:read"))],
) -> ProxyListResponse:
    """Lista todos los proxies en el pool."""
    proxy_pool = get_proxy_pool()
    proxies_raw = await proxy_pool.list_proxies()
    items = [
        ProxyItem(
            proxy=p,
            proxy_b64=base64.urlsafe_b64encode(p.encode()).decode(),
        )
        for p in proxies_raw
    ]
    return ProxyListResponse(proxies=items, total=len(items))


@router.post(
    "/proxies",
    response_model=ProxyListResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="addProxy",
)
async def add_proxy(
    body: ProxyAddRequest,
    _user: Annotated[User, Depends(require_permissions("admin:read"))],
) -> ProxyListResponse:
    """Añade un proxy al pool (sin redeploy)."""
    proxy_pool = get_proxy_pool()
    proxy = body.proxy.strip()
    if not proxy:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="proxy no puede estar vacío"
        )

    await proxy_pool.add_proxy(proxy)
    logger.info("admin.proxy.added", extra={"proxy": proxy[:40]})

    proxies_raw = await proxy_pool.list_proxies()
    items = [
        ProxyItem(proxy=p, proxy_b64=base64.urlsafe_b64encode(p.encode()).decode())
        for p in proxies_raw
    ]
    return ProxyListResponse(proxies=items, total=len(items))


@router.delete(
    "/proxies/{proxy_b64}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    operation_id="removeProxy",
)
async def remove_proxy(
    proxy_b64: str,
    _user: Annotated[User, Depends(require_permissions("admin:read"))],
) -> None:
    """Elimina un proxy del pool (sin redeploy). proxy_b64 = URL del proxy en base64url."""
    try:
        proxy = base64.urlsafe_b64decode(proxy_b64.encode()).decode()
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="proxy_b64 inválido")

    proxy_pool = get_proxy_pool()
    removed = await proxy_pool.remove_proxy(proxy)
    if removed == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Proxy no encontrado en el pool"
        )
    logger.info("admin.proxy.removed", extra={"proxy": proxy[:40]})

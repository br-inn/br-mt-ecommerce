"""Healthcheck endpoints — ADR-048.

Seis endpoints, distintos niveles de profundidad y de auth:

| Endpoint              | Auth        | Comprueba                                      |
|-----------------------|-------------|------------------------------------------------|
| GET /health/live      | público     | event loop responde — siempre 200              |
| GET /health/ready     | público     | DB + Redis ping (timeout estricto)             |
| GET /health/db        | basic/token | query trivial Postgres + reportar pool stats   |
| GET /health/redis     | basic/token | PING + roundtrip + INFO                        |
| GET /health/storage   | basic/token | list 1 file en Supabase Storage                |
| GET /health/celery    | basic/token | heartbeat workers (custom, NO celery.control)  |

Cada check downstream usa `asyncio.timeout(...)` para no colgar nunca al monitor.
- Liveness es público (Kubernetes-style) y NO depende de servicios externos.
- Readiness es público también (lo consume el orquestador / load balancer).
- Deep checks exigen basic-auth o token para no exponer pool stats / latencia
  interna a internet.

Implementación:
- DB:      `app.db.engine` (Wave 1, Agente C).
- Redis:   `app.core.redis` (Wave 1).
- Storage: `app.core.supabase` admin client (bucket SUPABASE_STORAGE_BUCKET_IMAGES).
- Celery:  heartbeats en Redis publicados por `app.workers.heartbeat` (signal
           worker_ready + task periódica `mt.system.publish_heartbeat`).
"""

from __future__ import annotations

import asyncio
import secrets
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy import text

from app.core.config import settings
from app.core.redis import get_redis
from app.core.supabase import get_supabase_admin
from app.db import engine as db_engine

router = APIRouter()
_basic = HTTPBasic(auto_error=False)

# Colas Celery monitoreadas (alineado con worker.py topology).
_CELERY_QUEUES: tuple[str, ...] = (
    "imports",
    "pricing",
    "images",
    "comparator",
    "notifications",
    "audit",
)
# Edad máxima del heartbeat antes de declarar muerto al worker (segundos).
_HEARTBEAT_MAX_AGE_S: float = 60.0


# =============================================================================
# Auth dependency
# =============================================================================
async def verify_basic_auth_or_token(
    request: Request,
    credentials: Annotated[HTTPBasicCredentials | None, Depends(_basic)],
) -> None:
    """Acepta basic-auth (HEALTH_BASIC_AUTH_USER/PASSWORD) o header X-Healthcheck-Token.

    Devuelve 401 con WWW-Authenticate si nada matchea — no se filtra cuál de
    las dos vías falló para evitar oráculos.
    """
    # Intento 1: token header (más simple, para Better Stack / UptimeRobot).
    token = request.headers.get("X-Healthcheck-Token") or ""
    expected_token = settings.HEALTH_TOKEN.get_secret_value()
    if expected_token and token and secrets.compare_digest(token, expected_token):
        return

    # Intento 2: basic-auth.
    if credentials is not None:
        user_ok = secrets.compare_digest(credentials.username, settings.HEALTH_BASIC_AUTH_USER)
        pass_ok = secrets.compare_digest(
            credentials.password,
            settings.HEALTH_BASIC_AUTH_PASSWORD.get_secret_value(),
        )
        if user_ok and pass_ok:
            return

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="auth-required",
        headers={"WWW-Authenticate": "Basic"},
    )


# =============================================================================
# Liveness (público, NO depende de servicios externos)
# =============================================================================
@router.get(
    "/health/live",
    summary="Liveness probe",
    status_code=status.HTTP_200_OK,
)
async def liveness() -> dict[str, str]:
    """Liveness — el proceso responde. NO depende de servicios externos.

    Debe responder en < 100ms p99. Sólo verifica que el event loop está vivo.
    """
    return {
        "status": "ok",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "ts": datetime.now(timezone.utc).isoformat(),
    }


# =============================================================================
# Readiness (público — lo consume orquestador / LB)
# =============================================================================
@router.get(
    "/health/ready",
    summary="Readiness probe — DB + Redis",
)
async def readiness() -> JSONResponse:
    """Readiness — verifica dependencias críticas con timeout estricto.

    Chequea: Postgres (`SELECT 1`), Redis (`PING`) y opcionalmente Supabase
    Auth (`/auth/v1/health`) si `SUPABASE_AUTH_HEALTH_URL` está configurado.
    Si cualquiera falla → 503 + body con detalle por servicio.
    Debe responder en < 3s p99.
    """
    coros = [
        _check_db(timeout=5.0),
        _check_redis(timeout=1.0),
        _check_supabase_auth(timeout=settings.SUPABASE_AUTH_HEALTH_TIMEOUT_S),
    ]
    db_check, redis_check, supabase_check = await asyncio.gather(*coros)
    checks: dict[str, Any] = {
        "db": db_check,
        "redis": redis_check,
        "supabase_auth": supabase_check,
    }
    # Excluir checks "skipped" del cálculo de salud (downstream opcional sin URL).
    failed = [c for c in checks.values() if not c.get("ok") and not c.get("skipped")]
    status_code = status.HTTP_200_OK if not failed else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ok" if not failed else "degraded",
            "ts": datetime.now(timezone.utc).isoformat(),
            "checks": checks,
        },
    )


# =============================================================================
# Deep checks — autenticados
# =============================================================================
@router.get(
    "/health/db",
    summary="Postgres healthcheck + pool stats",
    dependencies=[Depends(verify_basic_auth_or_token)],
)
async def deep_db() -> dict[str, Any]:
    """Deep DB check con stats del pool. AUTH requerida (TI/monitoring)."""
    try:
        async with asyncio.timeout(2.0):
            engine = db_engine.get_engine()
            async with engine.connect() as conn:
                result = await conn.execute(
                    text("SELECT 1 AS one, now() AS ts, version() AS pg_version")
                )
                row = result.first()
        if row is None:  # pragma: no cover — defensivo, SELECT 1 nunca devuelve vacío
            return {"ok": False, "error": "empty-result"}

        pool = engine.pool
        return {
            "ok": True,
            "ts": row.ts.isoformat() if hasattr(row.ts, "isoformat") else str(row.ts),
            "pg_version": str(row.pg_version),
            "pool": {
                "size": pool.size() if hasattr(pool, "size") else None,
                "checked_in": pool.checkedin() if hasattr(pool, "checkedin") else None,
                "checked_out": pool.checkedout() if hasattr(pool, "checkedout") else None,
                "overflow": pool.overflow() if hasattr(pool, "overflow") else None,
            },
        }
    except Exception as exc:  # noqa: BLE001 — health debe ser robusto
        return {"ok": False, "error": type(exc).__name__, "detail": str(exc)[:200]}


@router.get(
    "/health/redis",
    summary="Redis PING + INFO server",
    dependencies=[Depends(verify_basic_auth_or_token)],
)
async def deep_redis() -> dict[str, Any]:
    """Deep Redis check — PING + sample de INFO. AUTH requerida."""
    client = get_redis()
    try:
        async with asyncio.timeout(2.0):
            pong = await client.ping()
            info = await client.info(section="server")
        # `info` puede venir como bytes-keyed dict — normalizar.
        version = info.get("redis_version") if isinstance(info, dict) else None
        uptime = info.get("uptime_in_seconds") if isinstance(info, dict) else None
        return {
            "ok": bool(pong),
            "redis_version": version,
            "uptime_in_seconds": uptime,
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": type(exc).__name__, "detail": str(exc)[:200]}


@router.get(
    "/health/storage",
    summary="Supabase Storage — list 1 file en bucket de imágenes",
    dependencies=[Depends(verify_basic_auth_or_token)],
)
async def deep_storage() -> dict[str, Any]:
    """Verifica que el bucket product-images sea accesible. AUTH requerida."""
    bucket = settings.SUPABASE_STORAGE_BUCKET_IMAGES
    try:
        # supabase-py es síncrono — wrap en thread para no bloquear el loop.
        files = await asyncio.wait_for(
            asyncio.to_thread(_list_bucket_one_file, bucket),
            timeout=3.0,
        )
        return {
            "ok": True,
            "bucket": bucket,
            "list_count": len(files) if files is not None else 0,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "bucket": bucket,
            "error": type(exc).__name__,
            "detail": str(exc)[:200],
        }


def _list_bucket_one_file(bucket: str) -> list[Any]:
    """Wrapper síncrono — supabase-py no es async."""
    client = get_supabase_admin()
    return client.storage.from_(bucket).list(
        path="",
        options={"limit": 1},  # type: ignore[arg-type]
    )


@router.get(
    "/health/celery",
    summary="Worker heartbeat — custom (no celery.control.ping)",
    dependencies=[Depends(verify_basic_auth_or_token)],
)
async def celery_health() -> dict[str, Any]:
    """Custom non-blocking healthcheck per ADR-048.

    Lee heartbeats publicados por workers en Redis (key
    `mt:worker:heartbeat:<queue>`). El TTL en Redis es 120s pero declaramos
    "muerto" si han pasado más de 60s desde la última actualización.

    NO usa el `celery.control.inspect.ping()` nativo — exige conexión bidireccional
    al broker, tiende a falsos negativos bajo carga y puede colgar bajo backlog.
    """
    client = get_redis()
    heartbeats: dict[str, dict[str, Any]] = {}
    try:
        async with asyncio.timeout(2.0):
            keys = [f"mt:worker:heartbeat:{q}" for q in _CELERY_QUEUES]
            values = await client.mget(keys)
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "error": type(exc).__name__,
            "detail": str(exc)[:200],
        }

    now = datetime.now(timezone.utc)
    for queue, raw in zip(_CELERY_QUEUES, values, strict=True):
        if not raw:
            heartbeats[queue] = {"alive": False, "last_seen": None, "age_seconds": None}
            continue
        # `decode_responses=True` ya devuelve str, pero defensivo por si cambia.
        text_val = raw.decode() if isinstance(raw, bytes) else str(raw)
        try:
            last_seen = datetime.fromisoformat(text_val)
            if last_seen.tzinfo is None:
                last_seen = last_seen.replace(tzinfo=timezone.utc)
        except ValueError:
            heartbeats[queue] = {
                "alive": False,
                "last_seen": text_val,
                "age_seconds": None,
                "error": "invalid-isoformat",
            }
            continue
        age = (now - last_seen).total_seconds()
        heartbeats[queue] = {
            "alive": age < _HEARTBEAT_MAX_AGE_S,
            "last_seen": last_seen.isoformat(),
            "age_seconds": round(age, 2),
        }

    all_alive = all(h["alive"] for h in heartbeats.values())
    return {"ok": all_alive, "queues": heartbeats}


# =============================================================================
# Internals — checks reutilizables
# =============================================================================
async def _check_db(*, timeout: float) -> dict[str, Any]:
    """SELECT 1 sobre el engine async, con timeout estricto."""
    try:
        async with asyncio.timeout(timeout):
            engine = db_engine.get_engine()
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": type(exc).__name__, "detail": str(exc)[:200]}


async def _check_redis(*, timeout: float) -> dict[str, Any]:
    """Redis PING con timeout estricto."""
    client = get_redis()
    try:
        async with asyncio.timeout(timeout):
            pong = await client.ping()
        return {"ok": bool(pong)}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": type(exc).__name__, "detail": str(exc)[:200]}


async def _check_supabase_auth(*, timeout: float) -> dict[str, Any]:
    """Ping a Supabase Auth (`/auth/v1/health`) con timeout estricto.

    Si `SUPABASE_AUTH_HEALTH_URL` está vacío, devolvemos `{ok: True, skipped: True}`
    — útil en dev/tests sin Supabase real.
    """
    url = settings.SUPABASE_AUTH_HEALTH_URL or ""
    if not url:
        return {"ok": True, "skipped": True, "reason": "no SUPABASE_AUTH_HEALTH_URL"}
    try:
        # Import diferido — sólo cargamos httpx si el chequeo está habilitado.
        import httpx

        async with asyncio.timeout(timeout):  # noqa: SIM117 — timeout context separado
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(url)
        ok = 200 <= resp.status_code < 300
        return {"ok": ok, "status_code": resp.status_code}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": type(exc).__name__, "detail": str(exc)[:200]}

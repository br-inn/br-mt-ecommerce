"""Async engine + session factory.

ADR-031 (Supabase + uuidv7):
- Connection string viene de `Settings.DATABASE_URL` (driver `asyncpg`).
- `statement_cache_size=0` por compatibilidad con pgbouncer en transaction mode.
- `pool_pre_ping=True` evita connections huérfanas tras restarts.

El engine y la session factory se instancian **lazy** (primera vez que se
piden vía `get_engine()` / `get_sessionmaker()`). Esto evita que `import
app.db` falle en entornos donde `asyncpg` no esté instalado (linters,
CI estático, generación de specs OpenAPI offline, etc.).

Roles distintos:
- `mt_app`         → role aplicativo, sujeto a RLS (default).
- `service_role`   → bypass RLS (Celery workers — no aquí, separado).
- `mt_migrate`     → DDL para Alembic (separado, ver `alembic/env.py`).
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings


def make_engine(url: str | None = None, *, echo: bool | None = None) -> AsyncEngine:
    """Crea un nuevo AsyncEngine. Útil para tests con DB efímera."""
    return create_async_engine(
        url or str(settings.DATABASE_URL),
        echo=settings.DATABASE_ECHO if echo is None else echo,
        pool_pre_ping=settings.DATABASE_POOL_PRE_PING,
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=settings.DATABASE_MAX_OVERFLOW,
        pool_recycle=1800,
        connect_args={
            "server_settings": {
                "application_name": settings.APP_NAME,
                "timezone": "UTC",
            },
            # Supabase pgbouncer en modo transaction no soporta prepared
            # statements server-side cacheadas — debe ser 0.
            "statement_cache_size": 0,
        },
    )


# Lazy singletons. Instanciados en el primer acceso a `engine` /
# `AsyncSessionLocal` (proxy via __getattr__).
_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = make_engine()
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,
            autoflush=False,
            class_=AsyncSession,
        )
    return _sessionmaker


def __getattr__(name: str):  # PEP 562 — module-level lazy attrs
    if name == "engine":
        return get_engine()
    if name == "AsyncSessionLocal":
        return get_sessionmaker()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


async def dispose_engine() -> None:
    """Cierra el pool al apagar la app (lifespan shutdown)."""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None

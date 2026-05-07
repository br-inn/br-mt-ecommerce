"""Pytest fixtures base.

Niveles:
- Unit (`tests/unit/`): no IO. Sólo `async_client` mockeado o tests sincronos.
- Integration (`tests/integration/`): testcontainers (Postgres + Redis efímeros).

Convenciones:
- `pytest-asyncio` en modo `auto` — async fixtures sin decorar.
- `event_loop` session-scoped — testcontainers tarda ~2s en arrancar; reusar.
- DB session function-scoped, transaccional, rollback al final → tests aislados.
- Celery configurado `task_always_eager=True` por defecto en tests para evitar
  necesidad de un worker real.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator, Iterator
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio

if TYPE_CHECKING:
    from celery import Celery
    from httpx import AsyncClient
    from redis.asyncio import Redis
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

# --- Force test env BEFORE importing app modules ----------------------------
# Si el desarrollador tiene `.env` con secrets reales, no queremos que los
# tests los toquen. El testcontainer se levanta y mutamos DATABASE_URL/REDIS_URL
# en `_test_env` antes de cualquier import de `app.*`.
os.environ.setdefault("ENV", "development")
os.environ.setdefault("LOG_LEVEL", "WARNING")
os.environ.setdefault("ENABLE_DOCS", "false")


# =============================================================================
# Event loop — session-scoped para que testcontainers no se reinicien
# =============================================================================
@pytest.fixture(scope="session")
def event_loop() -> Iterator[asyncio.AbstractEventLoop]:
    loop = asyncio.new_event_loop()
    try:
        yield loop
    finally:
        loop.close()


# =============================================================================
# Containers (integration tests only — marca @pytest.mark.integration)
# =============================================================================
@pytest.fixture(scope="session")
def postgres_container() -> Iterator[str]:
    """Levanta un Postgres efímero. Devuelve la URL `postgresql+asyncpg://...`.

    Se importa testcontainers dentro del fixture para que tests unit puros
    no paguen el coste del import si no usan este fixture.
    """
    from testcontainers.postgres import PostgresContainer

    # `pgvector/pgvector:pg16` trae la extensión `vector` preinstalada que
    # necesita la migración base 001 (`CREATE EXTENSION IF NOT EXISTS vector`).
    # `postgres:16-alpine` no la incluye → integration suites fallaban con
    # "extension vector is not available".
    with PostgresContainer("pgvector/pgvector:pg16") as pg:
        url = pg.get_connection_url().replace("psycopg2", "asyncpg")
        os.environ["DATABASE_URL"] = url
        os.environ["ALEMBIC_DATABASE_URL"] = pg.get_connection_url().replace(
            "psycopg2", "psycopg",
        )
        yield url


@pytest.fixture(scope="session")
def redis_container() -> Iterator[str]:
    """Levanta un Redis efímero. Devuelve `redis://host:port/0`."""
    from testcontainers.redis import RedisContainer

    with RedisContainer("redis:7-alpine") as r:
        url = f"redis://{r.get_container_host_ip()}:{r.get_exposed_port(6379)}/0"
        os.environ["REDIS_URL"] = url
        os.environ["CELERY_BROKER_URL"] = url
        os.environ["CELERY_RESULT_BACKEND"] = url

        # Refresca settings y clear de los singletons cacheados — `Settings`
        # se construye con .env en import time y get_redis() está lru_cache.
        from app.core import config as _cfg
        from app.core import redis as _redis_mod

        _cfg.get_settings.cache_clear()
        _cfg.settings = _cfg.get_settings()
        _redis_mod.get_redis.cache_clear()

        yield url


# =============================================================================
# Engine / Session (integration)
# =============================================================================
@pytest_asyncio.fixture(scope="session")
async def db_engine(postgres_container: str) -> AsyncIterator[AsyncEngine]:
    """Engine async sobre el Postgres efímero del session.

    NOTA: las migraciones (`alembic upgrade head`) las dispara Agente C en
    su propio fixture cuando agregue tests de modelos. Aquí sólo dejamos el
    engine listo para usar.
    """
    from app.db import make_engine

    engine = make_engine(url=postgres_container)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """Session function-scoped, transaccional. Rollback al final → aislamiento."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    async with db_engine.connect() as connection:
        await connection.begin()
        session_maker = async_sessionmaker(bind=connection, expire_on_commit=False)
        async with session_maker() as session:
            yield session
        await connection.rollback()


# =============================================================================
# Redis client (integration)
# =============================================================================
@pytest_asyncio.fixture
async def redis_client(redis_container: str) -> AsyncIterator[Redis]:
    from redis.asyncio import from_url

    client = from_url(redis_container, decode_responses=True)
    try:
        await client.flushdb()
        yield client
    finally:
        await client.flushdb()
        await client.aclose()


# =============================================================================
# HTTP client (todos los niveles)
# =============================================================================
@pytest_asyncio.fixture
async def async_client() -> AsyncIterator[AsyncClient]:
    """httpx.AsyncClient contra la ASGI app — sin red, in-process."""
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


# =============================================================================
# Celery — eager mode por defecto en tests
# =============================================================================
@pytest.fixture
def celery_app_eager() -> Iterator[Celery]:
    """Configura `task_always_eager=True` — las tasks se ejecutan inline."""
    from app.workers.worker import celery_app

    prev_eager = celery_app.conf.task_always_eager
    prev_propagates = celery_app.conf.task_eager_propagates
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
    try:
        yield celery_app
    finally:
        celery_app.conf.task_always_eager = prev_eager
        celery_app.conf.task_eager_propagates = prev_propagates

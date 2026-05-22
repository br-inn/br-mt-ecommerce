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
import pathlib
import subprocess
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

_BACKEND_DIR = pathlib.Path(__file__).parent.parent


def _create_auth_stub() -> None:
    """Crea el schema `auth` y tabla `auth.users` mínima si no existen.

    Necesario en CI (PostgreSQL puro sin Supabase) porque algunas migraciones
    referencia auth.users con FK. Supabase lo provee de serie; aquí lo stubamos.
    """
    import psycopg

    alembic_url = os.environ.get("ALEMBIC_DATABASE_URL", "")
    if not alembic_url:
        return
    # psycopg v3 URL: postgresql+psycopg://... → remove driver prefix
    raw_url = alembic_url.replace("postgresql+psycopg://", "postgresql://").replace(
        "postgresql+psycopg2://", "postgresql://"
    )
    with psycopg.connect(raw_url, autocommit=True) as conn:
        conn.execute("CREATE SCHEMA IF NOT EXISTS auth")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS auth.users (id UUID PRIMARY KEY)"
        )
        # Supabase function used in RLS policies (migration 013+); stub returns NULL.
        conn.execute(
            "CREATE OR REPLACE FUNCTION auth.uid() RETURNS uuid"
            " LANGUAGE sql STABLE AS $$ SELECT NULL::uuid $$"
        )
        # Supabase built-in roles used in RLS policies; create if absent.
        conn.execute(
            "DO $$ BEGIN"
            "  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role')"
            "  THEN CREATE ROLE service_role NOLOGIN; END IF; END $$"
        )


def _run_migrations() -> None:
    """Corre `alembic upgrade head` en el directorio del backend.

    Usa ALEMBIC_DATABASE_URL (psycopg sync) que debe estar seteada antes de
    llamar a esta función.
    """
    _create_auth_stub()
    result = subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        capture_output=True,
        text=True,
        cwd=_BACKEND_DIR,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Alembic migration failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )


@pytest.fixture(scope="session")
def postgres_container() -> Iterator[str]:
    """Devuelve la URL `postgresql+asyncpg://...` de una DB de tests.

    - Modo CI: si DATABASE_URL ya está en el entorno (servicio de GitHub Actions),
      la reutiliza directamente y corre las migraciones Alembic contra ella.
    - Modo local: levanta un contenedor efímero `pgvector/pgvector:pg16` via
      testcontainers (no requiere Docker pre-configurado más allá del daemon local).

    En ambos casos corre `alembic upgrade head` una vez por sesión.
    """
    existing = os.environ.get("DATABASE_URL")
    if existing:
        # CI / entorno externo: usar la DB ya provisionada.
        # Derivar la URL sync para Alembic: asyncpg → psycopg.
        alembic_url = existing.replace("+asyncpg", "+psycopg2").replace("+asyncpg", "")
        if "+psycopg" not in alembic_url and "postgresql" in alembic_url:
            alembic_url = alembic_url.replace("postgresql://", "postgresql+psycopg2://")
        os.environ.setdefault("ALEMBIC_DATABASE_URL", alembic_url)
        _run_migrations()
        yield existing
        return

    # Modo local: testcontainers.
    # `pgvector/pgvector:pg16` incluye la extensión `vector` requerida por
    # la migración base. `postgres:16-alpine` no la tiene.
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("pgvector/pgvector:pg16") as pg:
        url = pg.get_connection_url().replace("psycopg2", "asyncpg")
        os.environ["DATABASE_URL"] = url
        os.environ["ALEMBIC_DATABASE_URL"] = pg.get_connection_url().replace(
            "psycopg2", "psycopg",
        )
        _run_migrations()
        yield url


@pytest.fixture(scope="session")
def redis_container() -> Iterator[str]:
    """Devuelve la URL `redis://host:port/0` de un Redis de tests.

    - Modo CI: si REDIS_URL ya está en el entorno, la reutiliza.
    - Modo local: levanta un contenedor efímero via testcontainers.
    """
    existing = os.environ.get("REDIS_URL")
    if existing:
        os.environ.setdefault("CELERY_BROKER_URL", existing)
        os.environ.setdefault("CELERY_RESULT_BACKEND", existing)
        from app.core import config as _cfg
        from app.core import redis as _redis_mod

        _cfg.get_settings.cache_clear()
        _cfg.settings = _cfg.get_settings()
        _redis_mod.get_redis.cache_clear()
        yield existing
        return

    from testcontainers.redis import RedisContainer

    with RedisContainer("redis:7-alpine") as r:
        url = f"redis://{r.get_container_host_ip()}:{r.get_exposed_port(6379)}/0"
        os.environ["REDIS_URL"] = url
        os.environ["CELERY_BROKER_URL"] = url
        os.environ["CELERY_RESULT_BACKEND"] = url

        from app.core import config as _cfg
        from app.core import redis as _redis_mod

        _cfg.get_settings.cache_clear()
        _cfg.settings = _cfg.get_settings()
        _redis_mod.get_redis.cache_clear()

        yield url


@pytest.fixture(scope="session")
def neo4j_container() -> Iterator[str]:
    """Levanta un Neo4j efímero (5.x community) via testcontainers.

    Bypass para entornos sin Docker-in-Docker: si ``NEO4J_TEST_URI`` está
    definida, reusamos esa instancia (típicamente el servicio `neo4j` del
    docker-compose dev). Útil para correr el suite desde dentro del
    container backend sin montar `/var/run/docker.sock`.

    Devuelve la Bolt URI y resetea el singleton del driver al terminar.
    """
    external = os.environ.get("NEO4J_TEST_URI")
    user = os.environ.get("NEO4J_TEST_USER", "neo4j")
    password = os.environ.get("NEO4J_TEST_PASSWORD", "devpassword")

    if external:
        os.environ["NEO4J_URI"] = external
        os.environ["NEO4J_USER"] = user
        os.environ["NEO4J_PASSWORD"] = password
        os.environ["NEO4J_DATABASE"] = "neo4j"
        os.environ["GRAPHRAG_BACKEND"] = "neo4j"

        from app.core import config as _cfg

        _cfg.get_settings.cache_clear()
        _cfg.settings = _cfg.get_settings()

        try:
            yield external
        finally:
            from app.services.graphrag.adapters import factory as _factory

            _factory.shutdown()
        return

    from testcontainers.neo4j import Neo4jContainer

    with Neo4jContainer("neo4j:5.20-community").with_env(
        "NEO4J_AUTH", f"{user}/{password}"
    ) as neo:
        bolt_uri = neo.get_connection_url()
        os.environ["NEO4J_URI"] = bolt_uri
        os.environ["NEO4J_USER"] = user
        os.environ["NEO4J_PASSWORD"] = password
        os.environ["NEO4J_DATABASE"] = "neo4j"
        os.environ["GRAPHRAG_BACKEND"] = "neo4j"

        from app.core import config as _cfg

        _cfg.get_settings.cache_clear()
        _cfg.settings = _cfg.get_settings()

        try:
            yield bolt_uri
        finally:
            from app.services.graphrag.adapters import factory as _factory

            _factory.shutdown()


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
# PDF fixtures — generados automáticamente si no existen (US-F15-01-05)
# =============================================================================

_FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures"
_SAMPLE_PDF = _FIXTURES_DIR / "sample_equivalences.pdf"


def _ensure_sample_pdf() -> None:
    """Genera sample_equivalences.pdf si no existe."""
    if _SAMPLE_PDF.exists():
        return
    from tests.fixtures.generate_sample_pdf import build_pdf

    _FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    _SAMPLE_PDF.write_bytes(build_pdf())


def pytest_configure(config: pytest.Config) -> None:
    """Hook de sesión — genera fixtures binarias antes de cualquier test."""
    _ensure_sample_pdf()


@pytest.fixture(scope="session")
def sample_equivalences_pdf() -> pathlib.Path:
    """Ruta al PDF de equivalencias de prueba."""
    _ensure_sample_pdf()
    return _SAMPLE_PDF


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

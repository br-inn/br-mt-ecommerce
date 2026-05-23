"""Pytest fixtures base.

Niveles:
- Unit (`tests/unit/`): no IO. Sólo `async_client` mockeado o tests sincronos.
- Integration (`tests/integration/`): testcontainers (Postgres + Redis efímeros).

Convenciones:
- `pytest-asyncio` en modo `auto` — async fixtures sin decorar.
- `asyncio_default_fixture_loop_scope = "session"` en pyproject.toml — loop
  compartido por toda la sesión; testcontainers arranca sólo una vez.
- DB session function-scoped, transaccional, rollback al final → tests aislados.
- Celery configurado `task_always_eager=True` por defecto en tests para evitar
  necesidad de un worker real.
"""

from __future__ import annotations

import os
import pathlib
import subprocess
from collections.abc import AsyncIterator, Callable, Iterator
from typing import TYPE_CHECKING, Any

import pytest
import pytest_asyncio

if TYPE_CHECKING:
    from celery import Celery
    from httpx import AsyncClient
    from redis.asyncio import Redis
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

# =============================================================================
# CONTRATO DEL MODELO — Referencia para escribir tests correctamente
# =============================================================================
# HYBRID PROPERTIES de Product (son read-only, NO tienen setter):
#   Product.name_en  → derivado de translations WHERE lang='en'
#   Product.active   → derivado de lifecycle_status == 'active'
#
#   ❌  Product(name_en="Foo")  → AttributeError silencioso en savepoint
#   ❌  Product(active=True)    → AttributeError silencioso en savepoint
#   ✅  Product(lifecycle_status="active", erp_name="Foo")
#
# CAMPOS CORRECTOS al crear un Product:
#   sku            — obligatorio
#   family         — obligatorio
#   lifecycle_status — "active" | "deprecated" | "draft" | "blocked"
#   data_quality   — "complete" | "partial" | "blocked"
#   erp_name       — nombre ERP (equivalente a lo que name_en derivaba antes)
#   Usar fixture make_product() que valida estos contratos.
#
# CHECK CONSTRAINTS de DB (violarlas produce CheckViolationError):
#   match_agent_decisions.signal      : IN ('conformal', 'bootstrap')
#   match_agent_decisions.verdict     : IN ('auto_validate', 'auto_discard', 'no_decision')
#   match_agent_decisions.mode        : IN ('shadow', 'active')
#   match_agent_config.mode           : IN ('shadow', 'active')
#   products.lifecycle_status         : IN ('active', 'deprecated', 'draft', 'blocked')
#   import_runs.status                : IN ('queued', 'running', 'completed', 'failed')
#
# DATOS YA SEEDED EN MIGRACIONES (no insertar duplicados — usar get_or_create):
#   Permission.code : 'products:read', 'products:write', 'prices:read',
#                     'prices:write', 'users:read', 'users:write',
#                     'matches:read', 'matches:write', 'scraper:read',
#                     'scraper:write', 'imports:write'
#   Role.code       : 'admin', 'comercial', 'ti_integracion', 'gerente',
#                     'auditor', 'pim_manager'
#   Usar fixture make_role() / make_permission() que hacen SELECT-first.
#
# PATRÓN CORRECTO para deps FastAPI en mini-apps de tests:
#   ✅  override get_current_user con fake admin (role.code="admin")
#   ❌  override require_permissions(perm) — crea nuevo objeto cada llamada
#       (falla silenciosamente por identidad de objeto)
# =============================================================================

# --- Force test env BEFORE importing app modules ----------------------------
os.environ.setdefault("ENV", "development")
os.environ.setdefault("LOG_LEVEL", "WARNING")
os.environ.setdefault("ENABLE_DOCS", "false")


# =============================================================================
# Containers (integration tests only — marca @pytest.mark.integration)
# =============================================================================

_BACKEND_DIR = pathlib.Path(__file__).parent.parent


def _create_auth_stub() -> None:
    """Crea el schema `auth` y tabla `auth.users` mínima si no existen."""
    import psycopg

    alembic_url = os.environ.get("ALEMBIC_DATABASE_URL", "")
    if not alembic_url:
        return
    raw_url = alembic_url.replace("postgresql+psycopg://", "postgresql://").replace(
        "postgresql+psycopg2://", "postgresql://"
    )
    with psycopg.connect(raw_url, autocommit=True) as conn:
        conn.execute("CREATE SCHEMA IF NOT EXISTS auth")
        conn.execute("CREATE TABLE IF NOT EXISTS auth.users (id UUID PRIMARY KEY)")
        conn.execute(
            "CREATE OR REPLACE FUNCTION auth.uid() RETURNS uuid"
            " LANGUAGE sql STABLE AS $$ SELECT NULL::uuid $$"
        )
        conn.execute(
            "DO $$ BEGIN"
            "  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role')"
            "  THEN CREATE ROLE service_role NOLOGIN; END IF; END $$"
        )


def _run_migrations() -> None:
    """Corre `alembic upgrade head` en el directorio del backend."""
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
      testcontainers.
    """
    existing = os.environ.get("DATABASE_URL")
    if existing:
        alembic_url = existing.replace("+asyncpg", "+psycopg2").replace("+asyncpg", "")
        if "+psycopg" not in alembic_url and "postgresql" in alembic_url:
            alembic_url = alembic_url.replace("postgresql://", "postgresql+psycopg2://")
        os.environ.setdefault("ALEMBIC_DATABASE_URL", alembic_url)
        _run_migrations()
        yield existing
        return

    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("pgvector/pgvector:pg16") as pg:
        url = pg.get_connection_url().replace("psycopg2", "asyncpg")
        os.environ["DATABASE_URL"] = url
        os.environ["ALEMBIC_DATABASE_URL"] = pg.get_connection_url().replace(
            "psycopg2",
            "psycopg",
        )
        _run_migrations()
        yield url


@pytest.fixture(scope="session")
def redis_container() -> Iterator[str]:
    """Devuelve la URL `redis://host:port/0` de un Redis de tests."""
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
    """Levanta un Neo4j efímero (5.x community) via testcontainers."""
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
    """Engine async sobre el Postgres efímero del session."""
    from app.db import make_engine

    engine = make_engine(url=postgres_container)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """Session function-scoped, transaccional. Rollback al final → aislamiento.

    Para tests donde el código bajo test NO llama session.commit() directamente.
    Si el código SIGUE llamando commit(), usar db_session_committed.
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker

    async with db_engine.connect() as connection:
        await connection.begin()
        session_maker = async_sessionmaker(bind=connection, expire_on_commit=False)
        async with session_maker() as session:
            yield session
        await connection.rollback()


@pytest_asyncio.fixture
async def db_session_committed(db_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """Session para tests donde el código bajo test llama session.commit().

    A diferencia de db_session (rollback), esta fixture hace commits reales y
    trunca las tablas afectadas al finalizar para garantizar aislamiento.

    Usar cuando PimImporter, workers u otros servicios llaman commit() internamente.
    """
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import async_sessionmaker

    async_session_maker = async_sessionmaker(db_engine, expire_on_commit=False)
    async with async_session_maker() as session:
        yield session
        # Limpieza post-test — orden inverso a FK constraints.
        await session.execute(text("DELETE FROM product_translations"))
        await session.execute(text("DELETE FROM product_assets"))
        await session.execute(
            text("ALTER TABLE products DISABLE TRIGGER trg_products_no_hard_delete")
        )
        await session.execute(text("DELETE FROM products"))
        await session.execute(
            text("ALTER TABLE products ENABLE TRIGGER trg_products_no_hard_delete")
        )
        await session.execute(text("DELETE FROM import_runs"))
        await session.execute(text("DELETE FROM audit_events"))
        await session.commit()


# =============================================================================
# Factories para entidades de test — evitan errores con hybrid_properties
# =============================================================================


@pytest_asyncio.fixture
async def make_product(db_session: AsyncSession) -> Callable[..., Any]:
    """Factory fixture para crear Products en tests.

    Encapsula el contrato del modelo: lifecycle_status en lugar de active,
    sin name_en (hybrid_property read-only), sin active (hybrid_property).

    Uso:
        product = await make_product("MT-V-001")
        product = await make_product("MT-V-002", lifecycle_status="deprecated")
        product = await make_product("MT-V-003", family="valves_gate", data_quality="partial")
    """
    from app.db.models.product import Product

    async def _factory(
        sku: str,
        *,
        family: str = "valves_ball",
        lifecycle_status: str = "active",
        data_quality: str = "complete",
        erp_name: str | None = None,
        **kwargs: Any,
    ) -> Product:
        # Captura errores tempranos — ambos son hybrid_property sin setter.
        for forbidden in ("name_en", "active"):
            if forbidden in kwargs:
                raise ValueError(
                    f"make_product: '{forbidden}' es hybrid_property read-only. "
                    f"Usa 'lifecycle_status' (no 'active') y 'erp_name' (no 'name_en')."
                )
        p = Product(
            sku=sku,
            family=family,
            lifecycle_status=lifecycle_status,
            data_quality=data_quality,
            erp_name=erp_name,
            **kwargs,
        )
        db_session.add(p)
        await db_session.flush()
        return p

    return _factory


@pytest_asyncio.fixture
async def make_permission(db_session: AsyncSession) -> Callable[..., Any]:
    """Factory SELECT-first para Permission.

    Evita UniqueViolationError al reusar permisos ya seeded en migraciones.

    Uso:
        perm = await make_permission("products:read")
        perm = await make_permission("custom:perm", description="Custom")
    """
    from sqlalchemy import select

    from app.db.models.user import Permission

    async def _factory(code: str, description: str = "") -> Permission:
        existing = (
            await db_session.execute(select(Permission).where(Permission.code == code))
        ).scalar_one_or_none()
        if existing:
            return existing
        perm = Permission(code=code, description=description or code)
        db_session.add(perm)
        await db_session.flush()
        return perm

    return _factory


@pytest_asyncio.fixture
async def make_role(db_session: AsyncSession) -> Callable[..., Any]:
    """Factory SELECT-first para Role.

    Evita UniqueViolationError al reusar roles ya seeded en migraciones.
    Si el rol existe, lo devuelve tal como está (no actualiza permissions_snapshot).

    Uso:
        role = await make_role("comercial")
        role = await make_role("custom_role", name="Custom", permissions=["products:read"])
    """
    from sqlalchemy import select

    from app.db.models.user import Role

    async def _factory(
        code: str,
        *,
        name: str = "",
        permissions: list[str] | None = None,
    ) -> Role:
        existing = (
            await db_session.execute(select(Role).where(Role.code == code))
        ).scalar_one_or_none()
        if existing:
            return existing
        role = Role(
            code=code,
            name=name or code,
            permissions_snapshot=permissions or [],
        )
        db_session.add(role)
        await db_session.flush()
        return role

    return _factory


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

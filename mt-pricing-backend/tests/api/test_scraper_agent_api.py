"""Integration tests for POST /api/v1/scraper-sources/analyze."""
from __future__ import annotations

import os
import time
from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

os.environ["SUPABASE_JWT_SECRET"] = "test-jwt-secret-deterministic-32chars!"
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "anon-test")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "service-test")
os.environ["SUPABASE_JWT_VERIFICATION_MODE"] = "hs256"
os.environ["JWT_ALGORITHM"] = "HS256"
os.environ["SCRAPER_ALLOW_LOOPBACK"] = "true"  # allow html_fixture_server (127.0.0.1)

try:
    from app.core import config as _cfg

    _cfg.get_settings.cache_clear()
    _cfg.settings = _cfg.get_settings()
except Exception:
    pass

JWT_SECRET = "test-jwt-secret-deterministic-32chars!"

pytestmark = [pytest.mark.integration]


@pytest.fixture(autouse=True, scope="module")
def _migrate(postgres_container: str) -> None:
    import sqlalchemy as _sa
    from alembic.config import Config
    from sqlalchemy import text

    from alembic import command

    sync_url = postgres_container.replace("postgresql+asyncpg://", "postgresql+psycopg://")
    from app.core import config as _app_cfg

    _app_cfg.get_settings.cache_clear()
    os.environ["DATABASE_URL"] = postgres_container
    os.environ["ALEMBIC_DATABASE_URL"] = sync_url
    _app_cfg.settings = _app_cfg.get_settings()

    import app.api.deps as _deps

    _deps.settings = _app_cfg.settings
    try:
        import app.core.jwks as _jwks

        _jwks._settings = _app_cfg.settings  # type: ignore[attr-defined]
    except Exception:
        pass

    engine = _sa.create_engine(sync_url)
    try:
        with engine.connect() as conn:
            # auth schema may already exist (Supabase cloud or local supabase start)
            try:
                conn.execute(text("CREATE SCHEMA IF NOT EXISTS auth"))
                conn.execute(
                    text(
                        "CREATE TABLE IF NOT EXISTS auth.users "
                        "(id UUID PRIMARY KEY DEFAULT gen_random_uuid())"
                    )
                )
                for fn, ret in (("uid", "UUID"), ("role", "TEXT"), ("jwt", "JSONB")):
                    conn.execute(
                        text(
                            f"CREATE OR REPLACE FUNCTION auth.{fn}() RETURNS {ret} "
                            f"AS $$ SELECT NULL::{ret} $$ LANGUAGE sql"
                        )
                    )
                for role in ("anon", "authenticated", "service_role"):
                    conn.execute(
                        text(
                            f"DO $$ BEGIN "
                            f"IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') "
                            f"THEN CREATE ROLE {role} NOLOGIN; END IF; END $$"
                        )
                    )
            except Exception:
                conn.rollback()
            conn.commit()
    finally:
        engine.dispose()

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", sync_url)
    command.upgrade(cfg, "head")


def _emit_jwt(*, sub: str, email: str) -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "sub": sub,
            "aud": "authenticated",
            "email": email,
            "iat": now,
            "exp": now + 3600,
            "app_metadata": {"role": "admin"},
        },
        JWT_SECRET,
        algorithm="HS256",
    )


async def _seed_user_with_perms(
    session: AsyncSession, perms_codes: list[str]
) -> tuple[UUID, str]:
    from app.db.models.user import Permission, Role, RolePermission, User

    perm_ids = []
    for code in perms_codes:
        existing = (
            await session.execute(select(Permission).where(Permission.code == code))
        ).scalar_one_or_none()
        if existing is None:
            p = Permission(code=code, description=code)
            session.add(p)
            await session.flush()
            perm_ids.append(p.id)
        else:
            perm_ids.append(existing.id)

    role_code = f"agent_tester_{uuid4().hex[:6]}"
    role = Role(code=role_code, name=role_code, permissions_snapshot=perms_codes)
    session.add(role)
    await session.flush()
    for pid in perm_ids:
        session.add(RolePermission(role_id=role.id, permission_id=pid))
    await session.flush()

    uid = uuid4()
    email = f"agent-{uid.hex[:6]}@mt.ae"
    user = User(
        id=uid,
        email=email,
        full_name="AgentTest",
        locale="es",
        is_active=True,
        role_id=role.id,
    )
    session.add(user)
    await session.flush()
    return uid, email


@pytest_asyncio.fixture
async def agent_client(postgres_container: str) -> AsyncIterator[AsyncClient]:
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.api.deps import get_db_session
    from app.main import app

    engine = create_async_engine(
        postgres_container,
        echo=False,
        connect_args={"statement_cache_size": 0},  # pgbouncer transaction-mode compat
    )
    async with engine.connect() as conn:
        await conn.begin()
        sm = async_sessionmaker(bind=conn, expire_on_commit=False)
        async with sm() as session:
            uid, email = await _seed_user_with_perms(session, ["products:read", "products:write"])
            await session.flush()

            async def _override() -> AsyncIterator[AsyncSession]:
                yield session

            app.dependency_overrides[get_db_session] = _override
            try:
                token = _emit_jwt(sub=str(uid), email=email)
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
                    ac.headers["Authorization"] = f"Bearer {token}"
                    yield ac
            finally:
                app.dependency_overrides.pop(get_db_session, None)
        await conn.rollback()
    await engine.dispose()


@pytest.mark.integration
@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="requires ANTHROPIC_API_KEY",
)
async def test_analyze_happy_path(agent_client: AsyncClient, html_fixture_server: str):
    url = f"{html_fixture_server}/generic_serp.html"
    resp = await agent_client.post("/api/v1/scraper-sources/analyze", json={"url": url})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["detected_mode"] == "static"
    assert "fields" in data["proposed_recipe"]
    assert len(data["proposed_recipe"]["fields"]) > 0
    assert isinstance(data["preview_records"], list)
    assert len(data["preview_records"]) == 3
    assert isinstance(data["field_confidence"], dict)
    assert isinstance(data["missing_required"], list)


@pytest.mark.integration
@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="requires ANTHROPIC_API_KEY",
)
async def test_analyze_with_hint(agent_client: AsyncClient, html_fixture_server: str):
    url = f"{html_fixture_server}/generic_serp.html"
    resp = await agent_client.post(
        "/api/v1/scraper-sources/analyze",
        json={"url": url, "hint": "the product delivery time"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    fields = data["proposed_recipe"].get("fields", [])
    assert len(fields) == 1
    assert fields[0].get("selector") is not None


@pytest.mark.integration
async def test_analyze_blocks_private_ip(agent_client: AsyncClient):
    resp = await agent_client.post(
        "/api/v1/scraper-sources/analyze",
        json={"url": "http://192.168.1.1/products"},
    )
    assert resp.status_code == 422


@pytest.mark.integration
async def test_analyze_requires_auth():
    from app.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as anon_client:
        resp = await anon_client.post(
            "/api/v1/scraper-sources/analyze", json={"url": "http://example.com"}
        )
    assert resp.status_code in (401, 403)

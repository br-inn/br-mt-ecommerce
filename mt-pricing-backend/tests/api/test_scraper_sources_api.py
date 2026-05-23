"""Integration tests para /scraper-sources REST API."""

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
# Force HS256 mode so tests don't require JWKS server (overrides .env jwks/ES256 setting)
os.environ["SUPABASE_JWT_VERIFICATION_MODE"] = "hs256"
os.environ["JWT_ALGORITHM"] = "HS256"

# Clear settings cache so the env overrides take effect
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
    """Aplica `alembic upgrade head` sobre el testcontainer."""
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
            conn.execute(text("CREATE SCHEMA IF NOT EXISTS auth"))
            conn.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS auth.users ("
                    "id UUID PRIMARY KEY DEFAULT gen_random_uuid()"
                    ")"
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
            "app_metadata": {"role": "comercial"},
        },
        JWT_SECRET,
        algorithm="HS256",
    )


async def _seed_user_with_perms(session: AsyncSession, perms_codes: list[str]) -> tuple[UUID, str]:
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

    role_code = f"scraper_tester_{uuid4().hex[:6]}"
    role = Role(
        code=role_code,
        name=role_code,
        permissions_snapshot=perms_codes,
    )
    session.add(role)
    await session.flush()
    for pid in perm_ids:
        session.add(RolePermission(role_id=role.id, permission_id=pid))
    await session.flush()

    uid = uuid4()
    email = f"scraper-{uid.hex[:6]}@mt.ae"
    user = User(
        id=uid,
        email=email,
        full_name="ScraperTest",
        locale="es",
        is_active=True,
        role_id=role.id,
    )
    session.add(user)
    await session.flush()
    return uid, email


@pytest_asyncio.fixture
async def client_rw(postgres_container: str) -> AsyncIterator[AsyncClient]:
    """Client with read-write permissions over a fresh transactional session."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.api.deps import get_db_session
    from app.main import app

    engine = create_async_engine(postgres_container, echo=False)
    async with engine.connect() as conn:
        await conn.begin()
        sm = async_sessionmaker(bind=conn, expire_on_commit=False)
        async with sm() as session:
            uid, email = await _seed_user_with_perms(session, ["products:write", "products:read"])
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


@pytest.mark.api
@pytest.mark.asyncio
async def test_create_and_list_source(client_rw: AsyncClient) -> None:
    resp = await client_rw.post(
        "/api/v1/scraper-sources",
        json={
            "name": "ACME Tools",
            "slug": "acme-api",
            "base_url": "https://acme.example",
            "destination_profile": "competitor_price",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["slug"] == "acme-api"
    assert body["status"] == "draft"

    list_resp = await client_rw.get("/api/v1/scraper-sources")
    assert list_resp.status_code == 200
    assert any(s["slug"] == "acme-api" for s in list_resp.json())


@pytest.mark.api
@pytest.mark.asyncio
async def test_add_recipe_to_source(client_rw: AsyncClient) -> None:
    src = await client_rw.post(
        "/api/v1/scraper-sources",
        json={
            "name": "ACME",
            "slug": "acme-recipe-api",
            "base_url": "https://acme.example",
            "destination_profile": "competitor_price",
        },
    )
    assert src.status_code == 201, src.text
    source_id = src.json()["id"]

    recipe_resp = await client_rw.post(
        f"/api/v1/scraper-sources/{source_id}/recipes",
        json={
            "recipe": {
                "url_templates": {"search": "https://acme.example/s?q={query}"},
                "list_item_selector": "div.product",
                "fields": [{"name": "title", "selector": "h2.name"}],
            }
        },
    )
    assert recipe_resp.status_code == 201, recipe_resp.text
    assert recipe_resp.json()["version"] == 1


@pytest.mark.api
@pytest.mark.asyncio
async def test_patch_source_updates_fields(client_rw: AsyncClient) -> None:
    r = await client_rw.post(
        "/api/v1/scraper-sources",
        json={
            "name": "patch-test",
            "slug": "patch-test",
            "base_url": "https://example.com/s",
            "destination_profile": "competitor_price",
            "fetch_mode": "static",
        },
    )
    assert r.status_code == 201, r.text
    source_id = r.json()["id"]

    r2 = await client_rw.patch(
        f"/api/v1/scraper-sources/{source_id}",
        json={"name": "patched-name", "status": "testing"},
    )
    assert r2.status_code == 200, r2.text
    data = r2.json()
    assert data["name"] == "patched-name"
    assert data["status"] == "testing"


@pytest.mark.api
@pytest.mark.asyncio
async def test_list_recipes_empty_then_populated(client_rw: AsyncClient) -> None:
    r = await client_rw.post(
        "/api/v1/scraper-sources",
        json={
            "name": "recipe-list-test",
            "slug": "recipe-list-test",
            "base_url": "https://example.com/s",
            "destination_profile": "competitor_price",
            "fetch_mode": "static",
        },
    )
    assert r.status_code == 201, r.text
    source_id = r.json()["id"]

    r2 = await client_rw.get(f"/api/v1/scraper-sources/{source_id}/recipes")
    assert r2.status_code == 200
    assert r2.json() == []

    r3 = await client_rw.post(
        f"/api/v1/scraper-sources/{source_id}/recipes",
        json={
            "recipe": {
                "url_templates": {"search": "https://example.com/s?q={query}"},
                "list_item_selector": "div.item",
                "fields": [{"name": "price", "selector": ".price", "type": "currency"}],
            }
        },
    )
    assert r3.status_code == 201, r3.text

    r4 = await client_rw.get(f"/api/v1/scraper-sources/{source_id}/recipes")
    assert r4.status_code == 200
    recipes = r4.json()
    assert len(recipes) == 1
    assert recipes[0]["version"] == 1
    assert "created_at" in recipes[0]

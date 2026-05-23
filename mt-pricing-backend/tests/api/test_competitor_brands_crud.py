"""Integration tests para /competitor-brands CRUD."""

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
    """Aplica `alembic upgrade head` sobre el testcontainer.

    Crea stubs de auth.uid/auth.role/auth.jwt + auth.users porque algunas
    migraciones los referencian en RLS policies o FKs.

    `postgres_container` es la URL asyncpg del testcontainer. La convertimos
    a psycopg (sync) para alembic.
    """
    import sqlalchemy as _sa
    from alembic.config import Config
    from sqlalchemy import text

    from alembic import command

    # Derive sync URL from the asyncpg URL passed as argument
    sync_url = postgres_container.replace("postgresql+asyncpg://", "postgresql+psycopg://")
    # Override settings singleton so env.py picks up the testcontainer URL
    from app.core import config as _app_cfg

    _app_cfg.get_settings.cache_clear()
    os.environ["DATABASE_URL"] = postgres_container
    os.environ["ALEMBIC_DATABASE_URL"] = sync_url
    _app_cfg.settings = _app_cfg.get_settings()

    # Patch all module-level `settings` references so JWT verification uses
    # the updated settings (hs256 mode + HS256 algorithm + correct secret) and
    # not the cached object bound at import time (.env may set ES256/jwks).
    import app.api.deps as _deps

    _deps.settings = _app_cfg.settings
    # Also patch app.core.jwks if it was already imported (avoid JWKS fetch)
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

    role_code = f"brands_tester_{uuid4().hex[:6]}"
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
    email = f"brands-{uid.hex[:6]}@mt.ae"
    user = User(
        id=uid,
        email=email,
        full_name="BrandsTest",
        locale="es",
        is_active=True,
        role_id=role.id,
    )
    session.add(user)
    await session.flush()
    return uid, email


@pytest_asyncio.fixture
async def client_rw(postgres_container: str) -> AsyncIterator[AsyncClient]:
    """Client with read-write permissions.

    Creates a fresh engine per test function to avoid cross-event-loop issues
    on Windows (asyncio ProactorEventLoop closes the connection pool when the
    function-scoped loop ends, breaking session-scoped engines on subsequent
    tests).
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.api.deps import get_db_session
    from app.main import app

    engine = create_async_engine(postgres_container, echo=False)
    async with engine.connect() as conn:
        await conn.begin()
        sm = async_sessionmaker(
            bind=conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )
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


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_brand_happy_path(client_rw: AsyncClient) -> None:
    resp = await client_rw.post(
        "/api/v1/competitor-brands/",
        json={"name": "Nibco", "amazon_dept": "industrial"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["name"] == "Nibco"
    assert data["amazon_dept"] == "industrial"
    assert data["is_active"] is True
    UUID(data["id"])  # must be valid UUID


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_brand_duplicate_name_returns_409(client_rw: AsyncClient) -> None:
    payload = {"name": "Kitz Duplicate"}
    r1 = await client_rw.post("/api/v1/competitor-brands/", json=payload)
    assert r1.status_code == 201, r1.text
    resp = await client_rw.post("/api/v1/competitor-brands/", json=payload)
    assert resp.status_code == 409, resp.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_brands(client_rw: AsyncClient) -> None:
    await client_rw.post("/api/v1/competitor-brands/", json={"name": "Crane List Test"})
    resp = await client_rw.get("/api/v1/competitor-brands/")
    assert resp.status_code == 200, resp.text
    names = [b["name"] for b in resp.json()]
    assert "Crane List Test" in names


@pytest.mark.integration
@pytest.mark.asyncio
async def test_patch_brand(client_rw: AsyncClient) -> None:
    create_resp = await client_rw.post("/api/v1/competitor-brands/", json={"name": "PatchBrand"})
    assert create_resp.status_code == 201, create_resp.text
    brand_id = create_resp.json()["id"]
    patch_resp = await client_rw.patch(
        f"/api/v1/competitor-brands/{brand_id}",
        json={"amazon_category_node": "16118159031", "is_active": False},
    )
    assert patch_resp.status_code == 200, patch_resp.text
    assert patch_resp.json()["amazon_category_node"] == "16118159031"
    assert patch_resp.json()["is_active"] is False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_brand_not_found(client_rw: AsyncClient) -> None:
    resp = await client_rw.get(f"/api/v1/competitor-brands/{uuid4()}")
    assert resp.status_code == 404, resp.text

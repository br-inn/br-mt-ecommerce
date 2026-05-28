"""End-to-end integration: analyze → create source → recipe → validate → activate."""

from __future__ import annotations

import os
import time
from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy import select, text
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
    import sqlalchemy as _sa  # noqa: I001
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import text

    from app.core import config as _app_cfg

    sync_url = postgres_container.replace("postgresql+asyncpg://", "postgresql+psycopg://")
    _app_cfg.get_settings.cache_clear()
    os.environ["DATABASE_URL"] = postgres_container
    os.environ["ALEMBIC_DATABASE_URL"] = sync_url
    _app_cfg.settings = _app_cfg.get_settings()

    import app.api.deps as _deps

    _deps.settings = _app_cfg.settings

    engine = _sa.create_engine(sync_url)
    try:
        with engine.connect() as conn:
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


async def _seed_user(session: AsyncSession, perms_codes: list[str]) -> tuple[UUID, str]:
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

    role_code = f"flow_tester_{uuid4().hex[:6]}"
    role = Role(code=role_code, name=role_code, permissions_snapshot=perms_codes)
    session.add(role)
    await session.flush()
    for pid in perm_ids:
        session.add(RolePermission(role_id=role.id, permission_id=pid))
    await session.flush()

    uid = uuid4()
    email = f"flow-{uid.hex[:6]}@mt.ae"
    user = User(
        id=uid,
        email=email,
        full_name="FlowTest",
        locale="es",
        is_active=True,
        role_id=role.id,
    )
    session.add(user)
    await session.flush()
    return uid, email


@pytest_asyncio.fixture
async def flow_client(postgres_container: str) -> AsyncIterator[AsyncClient]:
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.api.deps import get_db_session
    from app.main import app

    engine = create_async_engine(
        postgres_container,
        echo=False,
        connect_args={"statement_cache_size": 0},  # pgbouncer transaction-mode compat
    )
    sm = async_sessionmaker(engine, expire_on_commit=False)

    # Seed user with committed transaction so foreign keys resolve
    async with sm() as seed_session:
        uid, email = await _seed_user(seed_session, ["products:read", "products:write"])
        await seed_session.commit()

    async def _override() -> AsyncIterator[AsyncSession]:
        async with sm() as session:
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
        # Clean up test sources created during this run (unique slug prefix)
        async with sm() as cleanup:
            await cleanup.execute(text("DELETE FROM scraper_sources WHERE slug LIKE 'test-site-%'"))
            await cleanup.commit()
        await engine.dispose()


@pytest.mark.integration
@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="requires ANTHROPIC_API_KEY",
)
async def test_full_wizard_flow(flow_client: AsyncClient, html_fixture_server: str) -> None:
    """Simulates the 3-step wizard: analyze → create source → recipe → validate → activate."""
    url = f"{html_fixture_server}/generic_serp.html"

    # Step 1: Analyze
    resp = await flow_client.post("/api/v1/scraper-sources/analyze", json={"url": url})
    assert resp.status_code == 200, resp.text
    analysis = resp.json()
    assert analysis["detected_mode"] == "static"
    assert len(analysis["proposed_recipe"].get("fields", [])) > 0

    # Step 2: Create source
    unique_suffix = uuid4().hex[:6]
    source_payload = {
        "name": f"Test Site {unique_suffix}",
        "slug": f"test-site-{unique_suffix}",
        "base_url": analysis["proposed_source"]["base_url"],
        "destination_profile": "competitor_price",
        "fetch_mode": analysis["detected_mode"],
    }
    resp = await flow_client.post("/api/v1/scraper-sources", json=source_payload)
    assert resp.status_code == 201, resp.text
    source = resp.json()
    source_id = source["id"]
    assert source["status"] == "draft"

    # Step 3: Create recipe (user accepted proposed_recipe without edits)
    resp = await flow_client.post(
        f"/api/v1/scraper-sources/{source_id}/recipes",
        json={"recipe": analysis["proposed_recipe"]},
    )
    assert resp.status_code == 201, resp.text
    recipe = resp.json()
    recipe_id = recipe["id"]
    assert recipe["validation_status"] == "unvalidated"

    # Step 4: Validate recipe against original URL
    resp = await flow_client.post(
        f"/api/v1/scraper-sources/{source_id}/validate",
        json={"recipe_id": recipe_id, "test_url": url},
    )
    assert resp.status_code == 200, resp.text
    validation = resp.json()
    assert validation["status"] == "passing", (
        f"Validation failed. field_results: {validation.get('field_results')}"
    )

    # Step 5: Activate (only allowed when validation_status == "passing")
    resp = await flow_client.post(
        f"/api/v1/scraper-sources/{source_id}/activate",
        json={"recipe_id": recipe_id},
    )
    assert resp.status_code == 200, resp.text
    activated = resp.json()
    assert activated["status"] == "active"

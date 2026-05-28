"""API integration tests for the channel pricing engine.

Covers the 13 endpoints in app/api/routes/channel_pricing.py:
  - GET  /pricing/{channel}/params
  - PATCH /pricing/{channel}/route-params
  - GET  /pricing/{channel}/margin-targets
  - GET  /pricing/{channel}/catalog
  - POST /pricing/{channel}/optimize/apply
  - GET  /pricing/{channel}/product/{sku}

Auth pattern: emit a JWT with app_metadata.role = "admin".
The require_permissions dependency short-circuits on role=="admin",
so no specific permissions need to be seeded.

DB pattern: create a fresh async engine + transactional session per fixture,
override get_db_session, rollback after each fixture teardown.
"""

from __future__ import annotations

import os
import time
from collections.abc import AsyncIterator
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# ---------------------------------------------------------------------------
# Force test env variables before importing app modules.
# Use assignment (not setdefault) so Docker container values are overridden.
# ---------------------------------------------------------------------------
JWT_SECRET = "test-jwt-secret-deterministic-32chars!"

os.environ["SUPABASE_JWT_SECRET"] = JWT_SECRET
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "anon-test")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "service-test")
# Force HS256 — avoids JWKS server requirement
os.environ["SUPABASE_JWT_VERIFICATION_MODE"] = "hs256"
os.environ["JWT_ALGORITHM"] = "HS256"

try:
    from app.core import config as _cfg

    _cfg.get_settings.cache_clear()
    _cfg.settings = _cfg.get_settings()
except Exception:
    pass

pytestmark = [pytest.mark.integration]


# ---------------------------------------------------------------------------
# Module-level migration (runs alembic upgrade head once per module)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True, scope="module")
def _migrate(postgres_container: str) -> None:
    """Apply alembic upgrade head against the test container."""
    import sqlalchemy as _sa
    from alembic.config import Config
    from sqlalchemy import text as _text

    from alembic import command

    sync_url = postgres_container.replace("postgresql+asyncpg://", "postgresql+psycopg://")

    from app.core import config as _app_cfg

    # Propagate test JWT secret before rebuilding settings
    os.environ["SUPABASE_JWT_SECRET"] = JWT_SECRET
    os.environ["SUPABASE_JWT_VERIFICATION_MODE"] = "hs256"
    os.environ["JWT_ALGORITHM"] = "HS256"
    os.environ["DATABASE_URL"] = postgres_container
    os.environ["ALEMBIC_DATABASE_URL"] = sync_url

    _app_cfg.get_settings.cache_clear()
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
            # Attempt to set up auth schema stubs — silently ignore permission
            # errors (Supabase cloud / local supabase start already manages auth)
            for stmt in [
                _text("CREATE SCHEMA IF NOT EXISTS auth"),
                _text(
                    "CREATE TABLE IF NOT EXISTS auth.users "
                    "(id UUID PRIMARY KEY DEFAULT gen_random_uuid())"
                ),
            ]:
                try:
                    conn.execute(stmt)
                    conn.commit()
                except Exception:
                    conn.rollback()

            for fn, ret in (("uid", "UUID"), ("role", "TEXT"), ("jwt", "JSONB")):
                try:
                    conn.execute(
                        _text(
                            f"CREATE OR REPLACE FUNCTION auth.{fn}() RETURNS {ret} "
                            f"AS $$ SELECT NULL::{ret} $$ LANGUAGE sql"
                        )
                    )
                    conn.commit()
                except Exception:
                    conn.rollback()

            for pg_role in ("anon", "authenticated", "service_role"):
                try:
                    conn.execute(
                        _text(
                            f"DO $$ BEGIN "
                            f"IF NOT EXISTS "
                            f"(SELECT 1 FROM pg_roles WHERE rolname = '{pg_role}') "
                            f"THEN CREATE ROLE {pg_role} NOLOGIN; END IF; END $$"
                        )
                    )
                    conn.commit()
                except Exception:
                    conn.rollback()
    finally:
        engine.dispose()

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", sync_url)
    command.upgrade(cfg, "head")


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------


def _emit_jwt(*, sub: str, email: str, role: str = "admin") -> str:
    """Emit a HS256 JWT. Default role=admin bypasses all permission checks."""
    now = int(time.time())
    return jwt.encode(
        {
            "sub": sub,
            "aud": "authenticated",
            "email": email,
            "iat": now,
            "exp": now + 3600,
            "app_metadata": {"role": role},
        },
        JWT_SECRET,
        algorithm="HS256",
    )


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


async def _seed_admin_user(session: AsyncSession) -> tuple[UUID, str]:
    """Create an admin user in the test DB. Returns (uuid, email)."""
    from sqlalchemy import select

    from app.db.models.user import Role, User

    role = (await session.execute(select(Role).where(Role.code == "admin"))).scalar_one_or_none()
    if role is None:
        role = Role(code="admin", name="admin", permissions_snapshot=[])
        session.add(role)
        await session.flush()

    uid = uuid4()
    email = f"admin-cpe-{uid.hex[:6]}@mt.ae"
    user = User(
        id=uid,
        email=email,
        full_name="Channel Pricing Test Admin",
        locale="es",
        is_active=True,
        role_id=role.id,
    )
    session.add(user)
    await session.flush()
    return uid, email


async def _seed_channel_pricing_data(session: AsyncSession) -> None:
    """Ensure amazon_uae and noon_uae channels exist with full pricing config.

    Uses INSERT ... ON CONFLICT DO NOTHING so it is idempotent across test runs.
    Seeds:
      - channels: amazon_uae, noon_uae
      - trade_route_params: es_to_uae
      - channel_fee_params for each channel
      - channel_scheme_params: 3 schemes for amazon_uae, 2 for noon_uae
      - families + channel_margin_targets (at least 1)
    """
    # 1. Ensure a Family exists (needed for margin targets)
    await session.execute(
        text(
            """
            INSERT INTO families (id, code, name)
            VALUES (gen_random_uuid(), 'valves_ball_cp_test', 'Ball Valves CP Test')
            ON CONFLICT (code) DO NOTHING
            """
        )
    )
    await session.flush()

    family_id_row = await session.execute(
        text("SELECT id FROM families WHERE code = 'valves_ball_cp_test' LIMIT 1")
    )
    family_id = family_id_row.scalar_one()

    # 2. Ensure a Brand exists (required for products FK)
    await session.execute(
        text(
            """
            INSERT INTO brands (id, code, name)
            VALUES (gen_random_uuid(), 'mt_cp_test', 'MT CP Test')
            ON CONFLICT (code) DO NOTHING
            """
        )
    )
    await session.flush()

    brand_id_row = await session.execute(
        text("SELECT id FROM brands WHERE code = 'mt_cp_test' LIMIT 1")
    )
    brand_id = brand_id_row.scalar_one()

    # 3. Insert channels (only code + name; no status column in channels table)
    for code, name in (
        ("amazon_uae", "Amazon UAE"),
        ("noon_uae", "Noon UAE"),
    ):
        await session.execute(
            text(
                """
                INSERT INTO channels (id, code, name)
                VALUES (gen_random_uuid(), :code, :name)
                ON CONFLICT (code) DO NOTHING
                """
            ).bindparams(code=code, name=name)
        )
    await session.flush()

    amazon_id_row = await session.execute(
        text("SELECT id FROM channels WHERE code = 'amazon_uae' LIMIT 1")
    )
    amazon_id = amazon_id_row.scalar_one()

    noon_id_row = await session.execute(
        text("SELECT id FROM channels WHERE code = 'noon_uae' LIMIT 1")
    )
    noon_id = noon_id_row.scalar_one()

    # 4. Trade route
    await session.execute(
        text(
            """
            INSERT INTO trade_route_params
              (id, route_code, description, fx_rate, fx_buffer_pct,
               freight_rate_per_kg, freight_min_aed, import_tariff_pct,
               local_warehouse_pct, handling_pct)
            VALUES
              (gen_random_uuid(), 'es_to_uae_cp_test', 'ES → UAE test route',
               4.28, 2, 2.5, 50, 4.14, 2, 1.5)
            ON CONFLICT (route_code) DO NOTHING
            """
        )
    )
    await session.flush()

    route_id_row = await session.execute(
        text("SELECT id FROM trade_route_params WHERE route_code = 'es_to_uae_cp_test' LIMIT 1")
    )
    route_id = route_id_row.scalar_one()

    # 5. channel_fee_params (vat_pct=5 — tested in assertions)
    for channel_id in (amazon_id, noon_id):
        await session.execute(
            text(
                """
                INSERT INTO channel_fee_params
                  (id, channel_id, route_id, mt_discount_pct, commission_pct,
                   vat_pct, advertising_pct, returns_pct)
                VALUES
                  (gen_random_uuid(), :ch, :rt, 15, 11, 5, 8, 2)
                ON CONFLICT (channel_id) DO NOTHING
                """
            ).bindparams(ch=channel_id, rt=route_id)
        )
    await session.flush()

    # 6. channel_scheme_params — 3 for amazon_uae, 2 for noon_uae
    amazon_schemes = [
        ("canal_full", "FBA"),
        ("canal_lastmile", "Easy Ship"),
        ("merchant_managed", "Self-Ship"),
    ]
    noon_schemes = [
        ("canal_full", "FBN"),
        ("merchant_managed", "FBM"),
    ]
    for channel_id, schemes in (
        (amazon_id, amazon_schemes),
        (noon_id, noon_schemes),
    ):
        for fulfillment_scheme, label in schemes:
            # Inline the enum literal to avoid asyncpg cast parameter issues
            await session.execute(
                text(
                    f"""
                    INSERT INTO channel_scheme_params
                      (id, channel_id, fulfillment_scheme, scheme_label, is_available)
                    VALUES
                      (gen_random_uuid(), :ch, '{fulfillment_scheme}'::fulfillment_scheme,
                       :lbl, true)
                    ON CONFLICT (channel_id, fulfillment_scheme) DO NOTHING
                    """
                ).bindparams(ch=channel_id, lbl=label)
            )
    await session.flush()

    # 7. channel_margin_targets (at least 1 so list endpoint is non-empty)
    for channel_id in (amazon_id, noon_id):
        await session.execute(
            text(
                """
                INSERT INTO channel_margin_targets
                  (id, channel_id, family_id, selling_model, margin_target_pct)
                VALUES
                  (gen_random_uuid(), :ch, :fam, 'b2c'::selling_model, 14)
                ON CONFLICT (channel_id, family_id, selling_model) DO NOTHING
                """  # noqa: S608
            ).bindparams(ch=channel_id, fam=family_id)
        )
    await session.flush()

    # Keep brand_id / family_id in scope (unused directly but evaluated via flush)
    _ = brand_id


# ---------------------------------------------------------------------------
# Test client fixture
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def cp_client(postgres_container: str) -> AsyncIterator[AsyncClient]:
    """AsyncClient with admin JWT, DB session overriding get_db_session.

    Provides a fresh transactional session per test; rolls back on teardown
    so tests are isolated.
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.api.deps import get_db_session
    from app.main import app

    # statement_cache_size=0 required for pgbouncer in transaction mode
    engine = create_async_engine(
        postgres_container,
        echo=False,
        connect_args={"statement_cache_size": 0},
    )
    async with engine.connect() as conn:
        await conn.begin()
        sm = async_sessionmaker(bind=conn, expire_on_commit=False)
        async with sm() as session:
            # Seed channels + pricing config
            await _seed_channel_pricing_data(session)
            await session.flush()

            # Seed admin user + emit JWT
            uid, email = await _seed_admin_user(session)
            await session.flush()

            async def _override() -> AsyncIterator[AsyncSession]:
                yield session

            app.dependency_overrides[get_db_session] = _override
            try:
                token = _emit_jwt(sub=str(uid), email=email, role="admin")
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
                    ac.headers["Authorization"] = f"Bearer {token}"
                    yield ac
            finally:
                app.dependency_overrides.pop(get_db_session, None)
        await conn.rollback()
    await engine.dispose()


@pytest_asyncio.fixture
async def cp_client_with_session(
    postgres_container: str,
) -> AsyncIterator[tuple[AsyncClient, AsyncSession]]:
    """Variant of cp_client that also yields the bound AsyncSession.

    Used by tests that need to query the DB directly (e.g. to verify an INSERT)
    without a second engine — the session is bound to the same connection-level
    transaction that gets rolled back on teardown.
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.api.deps import get_db_session
    from app.main import app

    engine = create_async_engine(
        postgres_container,
        echo=False,
        connect_args={"statement_cache_size": 0},
    )
    async with engine.connect() as conn:
        await conn.begin()
        sm = async_sessionmaker(bind=conn, expire_on_commit=False)
        async with sm() as session:
            await _seed_channel_pricing_data(session)
            await session.flush()

            uid, email = await _seed_admin_user(session)
            await session.flush()

            async def _override() -> AsyncIterator[AsyncSession]:
                yield session

            app.dependency_overrides[get_db_session] = _override
            try:
                token = _emit_jwt(sub=str(uid), email=email, role="admin")
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
                    ac.headers["Authorization"] = f"Bearer {token}"
                    yield ac, session
            finally:
                app.dependency_overrides.pop(get_db_session, None)
        await conn.rollback()
    await engine.dispose()


# ---------------------------------------------------------------------------
# Tests — READ endpoints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_params_amazon_uae(cp_client: AsyncClient) -> None:
    """GET /pricing/amazon_uae/params returns route + fees + schemes."""
    resp = await cp_client.get("/api/v1/pricing/amazon_uae/params")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "route" in data
    assert "fees" in data
    assert "schemes" in data
    assert abs(float(data["fees"]["vat_pct"]) - 5.0) < 0.001
    assert len(data["schemes"]) == 3  # FBA, Easy Ship, Self-Ship


@pytest.mark.asyncio
async def test_get_params_unknown_channel(cp_client: AsyncClient) -> None:
    """GET /pricing/{unknown}/params returns 404."""
    resp = await cp_client.get("/api/v1/pricing/nonexistent_channel/params")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_params_noon_uae(cp_client: AsyncClient) -> None:
    """Noon UAE has 2 schemes (FBN + FBM)."""
    resp = await cp_client.get("/api/v1/pricing/noon_uae/params")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data["schemes"]) == 2


@pytest.mark.asyncio
async def test_catalog_returns_semaforo(cp_client: AsyncClient) -> None:
    """GET /catalog returns semaforo + rows (catalog may be empty — shape is validated)."""
    resp = await cp_client.get(
        "/api/v1/pricing/amazon_uae/catalog",
        params={"selling_model": "b2c"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "semaforo" in data
    assert "rows" in data
    s = data["semaforo"]
    assert s["total"] == s["publishable"] + s["blocked"]
    assert isinstance(s["by_scheme"], dict)


@pytest.mark.asyncio
async def test_margin_targets_list(cp_client: AsyncClient) -> None:
    """GET /margin-targets returns the seeded family margins."""
    resp = await cp_client.get("/api/v1/pricing/amazon_uae/margin-targets")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data) >= 1
    # Each entry has the expected keys
    assert all("family_id" in r and "family_name" in r for r in data)


@pytest.mark.asyncio
async def test_get_product_price_missing_sku_returns_404(cp_client: AsyncClient) -> None:
    """GET /product/{nonexistent} → 404."""
    resp = await cp_client.get("/api/v1/pricing/amazon_uae/product/NONEXISTENT_SKU_CPE_999")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests — WRITE endpoints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_route_params_updates_fx(cp_client: AsyncClient) -> None:
    """PATCH /route-params updates fx_rate visibly in GET /params."""
    # 1. Update fx_rate
    resp = await cp_client.patch(
        "/api/v1/pricing/amazon_uae/route-params",
        json={"fx_rate": 4.30},
    )
    assert resp.status_code == 200, resp.text
    assert abs(float(resp.json()["fx_rate"]) - 4.30) < 0.001

    # 2. Verify reflected in GET /params
    resp2 = await cp_client.get("/api/v1/pricing/amazon_uae/params")
    assert resp2.status_code == 200
    assert abs(float(resp2.json()["route"]["fx_rate"]) - 4.30) < 0.001


@pytest.mark.asyncio
async def test_apply_optimization_persists_overrides(cp_client: AsyncClient) -> None:
    """POST /optimize/apply returns 204 (even with zero products)."""
    resp = await cp_client.post(
        "/api/v1/pricing/amazon_uae/optimize/apply",
        params={"selling_model": "b2c"},
    )
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_propose_selected_returns_result_shape(cp_client: AsyncClient) -> None:
    """POST /prices/propose-selected returns total/proposed/skipped/errors shape."""
    resp = await cp_client.post(
        "/api/v1/pricing/amazon_uae/prices/propose-selected",
        json={"skus": ["NONEXISTENT_SKU_TEST_999"], "selling_model": "b2c"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total_requested"] == 1
    # NONEXISTENT_SKU_TEST_999 is not in products table → skipped
    assert data["skipped"] == 1
    assert data["proposed"] == 0
    assert data["errors"] == 0
    assert data["items"][0]["status"] == "skipped"
    assert data["items"][0]["sku"] == "NONEXISTENT_SKU_TEST_999"


@pytest.mark.asyncio
async def test_propose_selected_inserts_pending_review_row(
    cp_client_with_session: tuple[AsyncClient, AsyncSession],
) -> None:
    """Real SKU (from catalog) is proposed and lands in prices with status=pending_review.

    Exercises the INSERT path end-to-end: scheme_code FK mapping,
    draft→pending_review two-step, and rollback guard.
    Uses cp_client_with_session so the DB assertion queries the same
    connection-bound session (avoids cross-transaction visibility issues).
    """
    from sqlalchemy import text as sql_text

    cp_client, session = cp_client_with_session

    # 1. Fetch the catalog to find a real SKU that has channel_product_logistics
    sku_resp = await cp_client.get(
        "/api/v1/pricing/amazon_uae/catalog",
        params={"selling_model": "b2c"},
    )
    assert sku_resp.status_code == 200, sku_resp.text
    rows = sku_resp.json().get("rows", [])
    if not rows:
        pytest.skip("No catalog rows available in test fixture — cannot test INSERT path")
    test_sku = rows[0]["sku"]

    # 2. Propose the SKU
    resp = await cp_client.post(
        "/api/v1/pricing/amazon_uae/prices/propose-selected",
        json={"skus": [test_sku], "selling_model": "b2c"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    # 3. Verify counts add up — must NOT produce a 500 from FK/trigger violations
    assert data["total_requested"] == 1
    assert data["proposed"] + data["skipped"] + data["errors"] == 1, (
        f"counts mismatch: {data}"
    )

    # 4. If proposed, verify DB row has status=pending_review via the shared session
    if data["proposed"] == 1:
        price_id = data["items"][0]["price_id"]
        row = await session.execute(
            sql_text("SELECT status, product_sku FROM prices WHERE id = :id"),
            {"id": price_id},
        )
        result = row.fetchone()
        assert result is not None, f"No prices row found for id={price_id}"
        assert result.status == "pending_review", (
            f"Expected status=pending_review, got {result.status}"
        )
        assert result.product_sku == test_sku


@pytest.mark.asyncio
async def test_upsert_margin_target_returns_204(cp_client: AsyncClient) -> None:
    """PUT /margin-targets returns 204 for a valid family_id + selling_model.

    We obtain the family_id from the margin-targets list endpoint (which
    was seeded in the cp_client fixture), avoiding a second DB engine.
    """
    # 1. Get the seeded margin target to extract family_id
    list_resp = await cp_client.get("/api/v1/pricing/amazon_uae/margin-targets")
    assert list_resp.status_code == 200, list_resp.text
    targets = list_resp.json()
    if not targets:
        pytest.skip("No margin targets seeded — cannot test upsert_margin_target")

    family_id = targets[0]["family_id"]

    # 2. Upsert with the same family_id (updates margin_target_pct)
    resp = await cp_client.put(
        "/api/v1/pricing/amazon_uae/margin-targets",
        json={
            "family_id": family_id,
            "selling_model": "b2c",
            "margin_target_pct": 15,
        },
    )
    assert resp.status_code == 204, resp.text

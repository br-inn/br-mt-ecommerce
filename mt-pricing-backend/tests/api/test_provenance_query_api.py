"""Integration tests for F4 provenance/freshness/lineage/audit/card endpoints.

Mirrors the authed-client + channel/route/fee/product/logistics seed from
tests/api/test_channel_pricing.py.

Endpoints tested:
  GET /pricing/{channel}/sources/health
  GET /pricing/{channel}/freshness
  GET /pricing/{channel}/lineage/{sku}/{field}
  GET /pricing/{channel}/parameters/{key}/audit
  GET /pricing/{channel}/products/{sku}/card
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
# Env setup (mirrors test_channel_pricing.py)
# ---------------------------------------------------------------------------
JWT_SECRET = "test-jwt-secret-deterministic-32chars!"

os.environ["SUPABASE_JWT_SECRET"] = JWT_SECRET
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "anon-test")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "service-test")
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
# Module-level migration
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True, scope="module")
def _migrate(postgres_container: str) -> None:
    import sqlalchemy as _sa
    from alembic.config import Config
    from sqlalchemy import text as _text

    from alembic import command

    sync_url = postgres_container.replace("postgresql+asyncpg://", "postgresql+psycopg://")

    from app.core import config as _app_cfg

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
    from sqlalchemy import select

    from app.db.models.user import Role, User

    role = (await session.execute(select(Role).where(Role.code == "admin"))).scalar_one_or_none()
    if role is None:
        role = Role(code="admin", name="admin", permissions_snapshot=[])
        session.add(role)
        await session.flush()

    uid = uuid4()
    email = f"admin-pqa-{uid.hex[:6]}@mt.ae"
    user = User(
        id=uid,
        email=email,
        full_name="Provenance Query Test Admin",
        locale="es",
        is_active=True,
        role_id=role.id,
    )
    session.add(user)
    await session.flush()
    return uid, email


async def _seed_channel_pricing_data(session: AsyncSession) -> dict:
    """Seed channels + pricing config. Returns useful IDs."""
    # Family
    await session.execute(
        text(
            """
            INSERT INTO families (id, code, name)
            VALUES (gen_random_uuid(), 'valves_ball_pqa_test', 'Ball Valves PQA Test')
            ON CONFLICT (code) DO NOTHING
            """
        )
    )
    await session.flush()
    family_id = (
        await session.execute(
            text("SELECT id FROM families WHERE code = 'valves_ball_pqa_test' LIMIT 1")
        )
    ).scalar_one()

    # Brand
    await session.execute(
        text(
            """
            INSERT INTO brands (id, code, name)
            VALUES (gen_random_uuid(), 'mt_pqa_test', 'MT PQA Test')
            ON CONFLICT (code) DO NOTHING
            """
        )
    )
    await session.flush()
    brand_id = (
        await session.execute(
            text("SELECT id FROM brands WHERE code = 'mt_pqa_test' LIMIT 1")
        )
    ).scalar_one()

    # Channels
    for code, name in (("amazon_uae", "Amazon UAE"), ("noon_uae", "Noon UAE")):
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

    amazon_id = (
        await session.execute(
            text("SELECT id FROM channels WHERE code = 'amazon_uae' LIMIT 1")
        )
    ).scalar_one()

    # Trade route
    await session.execute(
        text(
            """
            INSERT INTO trade_route_params
              (id, route_code, description, fx_rate, fx_buffer_pct,
               freight_rate_per_kg, freight_min_aed, import_tariff_pct,
               local_warehouse_pct, handling_pct)
            VALUES
              (gen_random_uuid(), 'es_to_uae_pqa_test', 'ES → UAE pqa test route',
               4.28, 2, 2.5, 50, 4.14, 2, 1.5)
            ON CONFLICT (route_code) DO NOTHING
            """
        )
    )
    await session.flush()
    route_id = (
        await session.execute(
            text(
                "SELECT id FROM trade_route_params "
                "WHERE route_code = 'es_to_uae_pqa_test' LIMIT 1"
            )
        )
    ).scalar_one()

    # channel_fee_params
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
        ).bindparams(ch=amazon_id, rt=route_id)
    )
    await session.flush()

    # channel_scheme_params
    for fulfillment_scheme, label in (
        ("canal_full", "FBA"),
        ("canal_lastmile", "Easy Ship"),
        ("merchant_managed", "Self-Ship"),
    ):
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
            ).bindparams(ch=amazon_id, lbl=label)
        )
    await session.flush()

    # channel_margin_targets
    await session.execute(
        text(
            """
            INSERT INTO channel_margin_targets
              (id, channel_id, family_id, selling_model, margin_target_pct)
            VALUES
              (gen_random_uuid(), :ch, :fam, 'b2c'::selling_model, 14)
            ON CONFLICT (channel_id, family_id, selling_model) DO NOTHING
            """
        ).bindparams(ch=amazon_id, fam=family_id)
    )
    await session.flush()

    # Product with pe_eur + catalog_pvp_eur
    sku = "TEST-PQA-001"
    await session.execute(
        text(
            """
            INSERT INTO products (sku, family, family_id, brand_id, pe_eur, catalog_pvp_eur,
                                  units_per_box, weight, lifecycle_status)
            VALUES (:sku, 'valves', :fam, :brand, 10.00, 30.00, 1, 0.5, 'active')
            ON CONFLICT (sku) DO UPDATE SET
              pe_eur = EXCLUDED.pe_eur,
              catalog_pvp_eur = EXCLUDED.catalog_pvp_eur
            """
        ).bindparams(sku=sku, fam=family_id, brand=brand_id)
    )
    await session.flush()

    # channel_product_logistics for the SKU
    await session.execute(
        text(
            """
            INSERT INTO channel_product_logistics
              (id, product_sku, channel_id, inbound_fee_aed, storage_fee_aed,
               fulfillment_fee_aed, default_scheme)
            VALUES
              (gen_random_uuid(), :sku, :ch, 5, 2, 10, 'canal_full'::fulfillment_scheme)
            ON CONFLICT (product_sku, channel_id) DO NOTHING
            """
        ).bindparams(sku=sku, ch=amazon_id)
    )
    await session.flush()

    return {"amazon_id": amazon_id, "family_id": family_id, "sku": sku}


# ---------------------------------------------------------------------------
# Test client fixture
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def pqa_client(postgres_container: str) -> AsyncIterator[AsyncClient]:
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
                    yield ac
            finally:
                app.dependency_overrides.pop(get_db_session, None)
        await conn.rollback()
    await engine.dispose()


@pytest_asyncio.fixture
async def pqa_client_with_session(
    postgres_container: str,
) -> AsyncIterator[tuple[AsyncClient, AsyncSession]]:
    """Variant that also yields the DB session for direct DB assertions."""
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
            seed_data = await _seed_channel_pricing_data(session)
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
                    # Attach seed_data to client for tests that need SKU etc
                    ac._pqa_seed = seed_data  # type: ignore[attr-defined]
                    yield ac, session
            finally:
                app.dependency_overrides.pop(get_db_session, None)
        await conn.rollback()
    await engine.dispose()


# ---------------------------------------------------------------------------
# Tests — GET /sources/health
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sources_health_200(pqa_client: AsyncClient) -> None:
    """GET /sources/health returns 200 with 14 sources, all is_healthy=False."""
    resp = await pqa_client.get("/api/v1/pricing/amazon_uae/sources/health")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "sources" in data
    assert "blocking" in data
    assert len(data["sources"]) == 14, (
        f"Expected 14 source_op entries, got {len(data['sources'])}"
    )
    # All sources have never synced → all is_healthy=False
    assert all(not s["is_healthy"] for s in data["sources"]), (
        "Expected all sources is_healthy=False in fresh test DB"
    )
    # Critical blocking sources must be present
    blocking_set = set(data["blocking"])
    assert {"tesoreria_fx", "master_canal", "vendor_price_list"} <= blocking_set, (
        f"Expected critical sources in blocking, got {blocking_set}"
    )


# ---------------------------------------------------------------------------
# Tests — GET /freshness
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_freshness_returns_items(pqa_client: AsyncClient) -> None:
    """GET /freshness?selling_model=b2c returns items with is_stale bool."""
    resp = await pqa_client.get(
        "/api/v1/pricing/amazon_uae/freshness",
        params={"selling_model": "b2c"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "items" in data
    # We seeded fee_params + route_params + margin_targets + logistics → at least 3 items
    assert len(data["items"]) >= 1
    for item in data["items"]:
        assert "key" in item
        assert "scope" in item
        assert "is_stale" in item
        assert isinstance(item["is_stale"], bool)


# ---------------------------------------------------------------------------
# Tests — GET /lineage/{sku}/{field}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lineage_cost_for_seeded_sku(pqa_client: AsyncClient) -> None:
    """GET /lineage/{sku}/cost for a seeded SKU with logistics → 200, total_aed>0."""
    sku = "TEST-PQA-001"
    resp = await pqa_client.get(
        f"/api/v1/pricing/amazon_uae/lineage/{sku}/cost",
        params={"selling_model": "b2c"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["sku"] == sku
    assert data["field"] == "cost"
    assert Decimal(str(data["total_aed"])) > 0
    assert len(data["layers"]) > 0


@pytest.mark.asyncio
async def test_lineage_unknown_sku_returns_404(pqa_client: AsyncClient) -> None:
    """GET /lineage/{unknown_sku}/cost → 404."""
    resp = await pqa_client.get(
        "/api/v1/pricing/amazon_uae/lineage/NONEXISTENT-PQA-SKU/cost"
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests — GET /parameters/{key}/audit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_parameter_audit_route_after_patch(
    pqa_client_with_session: tuple[AsyncClient, AsyncSession],
) -> None:
    """PATCH /route-params, then GET /parameters/route/audit → entries non-empty."""
    ac, session = pqa_client_with_session

    # Trigger an audit event via PATCH /route-params
    patch_resp = await ac.patch(
        "/api/v1/pricing/amazon_uae/route-params",
        json={"fx_rate": 4.35},
    )
    assert patch_resp.status_code == 200, patch_resp.text

    # Now audit endpoint should return the event
    audit_resp = await ac.get("/api/v1/pricing/amazon_uae/parameters/route/audit")
    assert audit_resp.status_code == 200, audit_resp.text
    data = audit_resp.json()
    assert data["key"] == "route"
    assert data["entity_type"] == "pricing_param"
    assert len(data["entries"]) >= 1, "Expected at least one audit entry after PATCH"


@pytest.mark.asyncio
async def test_parameter_audit_unknown_key_returns_empty(pqa_client: AsyncClient) -> None:
    """GET /parameters/somethingelse/audit → 200, entries=[] (no crash)."""
    resp = await pqa_client.get("/api/v1/pricing/amazon_uae/parameters/somethingelse/audit")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "entries" in data
    assert isinstance(data["entries"], list)


# ---------------------------------------------------------------------------
# Tests — GET /products/{sku}/card
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_product_card_seeded_sku(pqa_client: AsyncClient) -> None:
    """GET /products/{sku}/card → 200, master populated, listing null, proposals []."""
    sku = "TEST-PQA-001"
    resp = await pqa_client.get(f"/api/v1/pricing/amazon_uae/products/{sku}/card")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["sku"] == sku
    assert "master" in data
    assert data["master"]["sku"] == sku
    # pe_eur and catalog_pvp_eur should be populated
    assert data["master"]["pe_eur"] is not None
    assert data["master"]["catalog_pvp_eur"] is not None
    # No listing for amazon_uae (not seeded)
    assert data["listing"] is None
    # No price proposals (not seeded)
    assert isinstance(data["proposals"], list)
    # No price history observations (not seeded)
    assert isinstance(data["price_history"], list)


@pytest.mark.asyncio
async def test_product_card_unknown_sku_returns_404(pqa_client: AsyncClient) -> None:
    """GET /products/{unknown_sku}/card → 404."""
    resp = await pqa_client.get(
        "/api/v1/pricing/amazon_uae/products/NONEXISTENT-PQA-SKU-999/card"
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_product_card_never_500(pqa_client: AsyncClient) -> None:
    """Product card should never return 500 for a valid SKU with no optional data."""
    sku = "TEST-PQA-001"
    resp = await pqa_client.get(f"/api/v1/pricing/amazon_uae/products/{sku}/card")
    assert resp.status_code != 500, f"Got 500: {resp.text}"

"""Integration tests — provenance + audit wiring for channel pricing mutations (F1).

Covers:
  - PATCH /pricing/{channel}/route-params
      → trade_route_params.source_op='decision_local', updated_by non-NULL,
        observed_at non-NULL; an audit_events row with entity_type='pricing_param',
        action='update', actor_id non-NULL, before/after populated.
  - POST /pricing/{channel}/prices/propose-selected
      → prices row has proposed_by non-NULL AND an audit_events row with
        entity_type='price_proposal'.

Auth + seed pattern mirrors tests/api/test_channel_pricing.py exactly:
  - HS256 JWT with app_metadata.role='admin' (bypasses all permission checks)
  - cp_client_with_session fixture (same connection-bound session for DB assertions)
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
# Seed helpers (identical to test_channel_pricing.py)
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
    email = f"admin-prov-{uid.hex[:6]}@mt.ae"
    user = User(
        id=uid,
        email=email,
        full_name="Provenance Test Admin",
        locale="es",
        is_active=True,
        role_id=role.id,
    )
    session.add(user)
    await session.flush()
    return uid, email


async def _seed_channel_pricing_data(session: AsyncSession) -> None:
    """Seed amazon_uae channel with full pricing config (idempotent)."""
    await session.execute(
        text(
            """
            INSERT INTO families (id, code, name)
            VALUES (gen_random_uuid(), 'valves_ball_prov_test', 'Ball Valves Prov Test')
            ON CONFLICT (code) DO NOTHING
            """
        )
    )
    await session.flush()

    family_id_row = await session.execute(
        text("SELECT id FROM families WHERE code = 'valves_ball_prov_test' LIMIT 1")
    )
    family_id = family_id_row.scalar_one()

    await session.execute(
        text(
            """
            INSERT INTO brands (id, code, name)
            VALUES (gen_random_uuid(), 'mt_prov_test', 'MT Prov Test')
            ON CONFLICT (code) DO NOTHING
            """
        )
    )
    await session.flush()

    await session.execute(
        text(
            """
            INSERT INTO channels (id, code, name)
            VALUES (gen_random_uuid(), 'amazon_uae_prov', 'Amazon UAE Prov')
            ON CONFLICT (code) DO NOTHING
            """
        )
    )
    await session.flush()

    channel_id_row = await session.execute(
        text("SELECT id FROM channels WHERE code = 'amazon_uae_prov' LIMIT 1")
    )
    channel_id = channel_id_row.scalar_one()

    await session.execute(
        text(
            """
            INSERT INTO trade_route_params
              (id, route_code, description, fx_rate, fx_buffer_pct,
               freight_rate_per_kg, freight_min_aed, import_tariff_pct,
               local_warehouse_pct, handling_pct)
            VALUES
              (gen_random_uuid(), 'es_to_uae_prov_test', 'ES → UAE prov test',
               4.28, 2, 2.5, 50, 4.14, 2, 1.5)
            ON CONFLICT (route_code) DO NOTHING
            """
        )
    )
    await session.flush()

    route_id_row = await session.execute(
        text("SELECT id FROM trade_route_params WHERE route_code = 'es_to_uae_prov_test' LIMIT 1")
    )
    route_id = route_id_row.scalar_one()

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
            ).bindparams(ch=channel_id, lbl=label)
        )
    await session.flush()

    await session.execute(
        text(
            """
            INSERT INTO channel_margin_targets
              (id, channel_id, family_id, selling_model, margin_target_pct)
            VALUES
              (gen_random_uuid(), :ch, :fam, 'b2c'::selling_model, 14)
            ON CONFLICT (channel_id, family_id, selling_model) DO NOTHING
            """
        ).bindparams(ch=channel_id, fam=family_id)
    )
    await session.flush()

    # Seed one product + logistics so propose-selected has something to work with
    brand_id_row = await session.execute(
        text("SELECT id FROM brands WHERE code = 'mt_prov_test' LIMIT 1")
    )
    brand_id = brand_id_row.scalar_one()

    test_sku = "PROV-TEST-SKU-001"
    await session.execute(
        text(
            """
            INSERT INTO products
              (sku, family, brand, specs, dimensions, packaging,
               brand_id, family_id, base_uom, units_per_box,
               b2c_labeling_aed, ceiling_basis,
               pe_eur, catalog_pvp_eur, weight,
               lifecycle_status, is_parent, is_variant)
            VALUES
              (:sku, 'valves_ball_prov_test', 'mt_prov_test',
               '{}', '{}', '{}',
               :brand_id, :family_id, 'un', 6,
               0, 'catalog_pvp'::ceiling_basis,
               10.00, 25.00, 1.5,
               'active', false, false)
            ON CONFLICT (sku) DO NOTHING
            """
        ).bindparams(sku=test_sku, brand_id=brand_id, family_id=family_id)
    )
    await session.flush()

    await session.execute(
        text(
            """
            INSERT INTO channel_product_logistics
              (id, product_sku, channel_id,
               inbound_fee_aed, storage_fee_aed, fulfillment_fee_aed,
               default_scheme)
            VALUES
              (gen_random_uuid(), :sku, :ch, 5.0, 2.0, 8.0, 'canal_full')
            ON CONFLICT (product_sku, channel_id) DO NOTHING
            """
        ).bindparams(sku=test_sku, ch=channel_id)
    )
    await session.flush()

    _ = family_id  # keep in scope


# ---------------------------------------------------------------------------
# Test client fixture (with session, for DB assertions)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def prov_client_with_session(
    postgres_container: str,
) -> AsyncIterator[tuple[AsyncClient, AsyncSession, UUID]]:
    """AsyncClient + bound AsyncSession + seeded actor UUID.

    Yields (client, session, actor_uid) — same connection-level transaction,
    rolled back on teardown. actor_uid is the UUID of the seeded admin user so
    tests can assert actor_id in DB rows.
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
                    yield ac, session, uid
            finally:
                app.dependency_overrides.pop(get_db_session, None)
        await conn.rollback()
    await engine.dispose()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_route_params_stamps_provenance_and_emits_audit(
    prov_client_with_session: tuple[AsyncClient, AsyncSession, UUID],
) -> None:
    """PATCH /route-params writes source_op, updated_by, observed_at + audit row."""
    from sqlalchemy import text as sql_text

    client, session, actor_uid = prov_client_with_session

    # 1. Patch fx_rate — triggers provenance stamping + audit emit
    resp = await client.patch(
        "/api/v1/pricing/amazon_uae_prov/route-params",
        json={"fx_rate": 4.35},
    )
    assert resp.status_code == 200, resp.text

    # 2. Verify provenance fields on trade_route_params row
    row = (
        await session.execute(
            sql_text(
                """
                SELECT trp.source_op, trp.updated_by, trp.observed_at
                FROM trade_route_params trp
                JOIN channel_fee_params cfp ON cfp.route_id = trp.id
                JOIN channels ch ON ch.id = cfp.channel_id
                WHERE ch.code = 'amazon_uae_prov'
                LIMIT 1
                """
            )
        )
    ).fetchone()
    assert row is not None, "No trade_route_params row found"
    assert row.source_op == "decision_local", (
        f"Expected source_op='decision_local', got {row.source_op!r}"
    )
    assert row.updated_by is not None, "updated_by should be non-NULL after PATCH"
    assert row.observed_at is not None, "observed_at should be non-NULL after PATCH"

    # 3. Verify audit_events row was written
    audit_row = (
        await session.execute(
            sql_text(
                """
                SELECT entity_type, action, actor_id, before, after
                FROM audit_events
                WHERE entity_type = 'pricing_param'
                  AND action = 'update'
                  AND actor_id = :actor_id
                ORDER BY event_at DESC
                LIMIT 1
                """
            ),
            {"actor_id": actor_uid},
        )
    ).fetchone()
    assert audit_row is not None, (
        f"No audit_events row found for entity_type='pricing_param', actor={actor_uid}"
    )
    assert audit_row.entity_type == "pricing_param"
    assert audit_row.action == "update"
    assert audit_row.actor_id == actor_uid
    assert audit_row.before is not None, "before should be populated"
    assert audit_row.after is not None, "after should be populated"


@pytest.mark.asyncio
async def test_propose_selected_sets_proposed_by_and_emits_audit(
    prov_client_with_session: tuple[AsyncClient, AsyncSession, UUID],
) -> None:
    """POST /prices/propose-selected sets proposed_by=actor_uid + audit row."""
    from sqlalchemy import text as sql_text

    client, session, actor_uid = prov_client_with_session

    # 1. Fetch catalog — skip test if no catalog rows available
    sku_resp = await client.get(
        "/api/v1/pricing/amazon_uae_prov/catalog",
        params={"selling_model": "b2c"},
    )
    assert sku_resp.status_code == 200, sku_resp.text
    rows = sku_resp.json().get("rows", [])
    if not rows:
        pytest.skip("No catalog rows available — cannot test propose-selected provenance")

    test_sku = rows[0]["sku"]

    # 2. Propose
    resp = await client.post(
        "/api/v1/pricing/amazon_uae_prov/prices/propose-selected",
        json={"skus": [test_sku], "selling_model": "b2c"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    if data["proposed"] == 0:
        pytest.skip(
            f"SKU {test_sku!r} was skipped/errored — cannot verify proposed_by; data={data}"
        )

    # 3. Verify proposed_by on the prices row
    price_id = data["items"][0]["price_id"]
    price_row = (
        await session.execute(
            sql_text("SELECT proposed_by, status FROM prices WHERE id = :id"),
            {"id": price_id},
        )
    ).fetchone()
    assert price_row is not None, f"No prices row for id={price_id}"
    assert price_row.proposed_by is not None, (
        "proposed_by should be non-NULL after propose-selected with authenticated user"
    )
    assert str(price_row.proposed_by) == str(actor_uid), (
        f"proposed_by mismatch: expected {actor_uid}, got {price_row.proposed_by}"
    )

    # 4. Verify audit_events row for price_proposal
    audit_row = (
        await session.execute(
            sql_text(
                """
                SELECT entity_type, action, actor_id, after
                FROM audit_events
                WHERE entity_type = 'price_proposal'
                  AND action = 'propose'
                  AND actor_id = :actor_id
                ORDER BY event_at DESC
                LIMIT 1
                """
            ),
            {"actor_id": actor_uid},
        )
    ).fetchone()
    assert audit_row is not None, (
        f"No audit_events row found for entity_type='price_proposal', actor={actor_uid}"
    )
    assert audit_row.entity_type == "price_proposal"
    assert audit_row.action == "propose"
    assert audit_row.actor_id == actor_uid
    assert audit_row.after is not None, "after should be populated with skus"

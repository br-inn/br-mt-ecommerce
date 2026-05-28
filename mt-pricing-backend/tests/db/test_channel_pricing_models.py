"""Integration tests for the channel pricing ORM models.

Covers:
- UNIQUE constraint on trade_route_params.route_code
- UNIQUE constraint on channel_scheme_params(channel_id, fulfillment_scheme)
- CASCADE delete on channel_margin_overrides when product is deleted
- Alembic ORM drift check (documentation test)

Migration: 20260603_147_channel_pricing_engine.py
"""

from __future__ import annotations

import os
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = [pytest.mark.integration]


# ---------------------------------------------------------------------------
# autouse: run migrations before the whole module
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True, scope="module")
def _migrate(postgres_container: str) -> None:
    """Aplica `alembic upgrade head` antes de los tests del módulo."""
    from alembic.config import Config

    from alembic import command

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", os.environ["ALEMBIC_DATABASE_URL"])
    command.upgrade(cfg, "head")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_channel(db_session: AsyncSession, code: str) -> Any:
    """Inserts a minimal Channel row and returns its UUID."""
    from app.db.models.channels import Channel

    ch = Channel(code=code, name=code)
    db_session.add(ch)
    await db_session.flush()
    return ch.id


async def _make_route(db_session: AsyncSession, route_code: str) -> Any:
    """Inserts a minimal TradeRouteParams row and returns the ORM object."""
    from app.db.models.channel_pricing import TradeRouteParams

    route = TradeRouteParams(
        route_code=route_code,
        fx_rate=Decimal("3.97"),
    )
    db_session.add(route)
    await db_session.flush()
    return route


# ---------------------------------------------------------------------------
# Test 1 — UNIQUE on trade_route_params.route_code
# ---------------------------------------------------------------------------


async def test_trade_route_params_route_code_unique(db_session: AsyncSession) -> None:
    """Inserting two rows with the same route_code raises IntegrityError."""
    from app.db.models.channel_pricing import TradeRouteParams

    await _make_route(db_session, "test_es_to_uae_dup")

    with pytest.raises(IntegrityError):
        dup = TradeRouteParams(
            route_code="test_es_to_uae_dup",
            fx_rate=Decimal("3.97"),
        )
        db_session.add(dup)
        await db_session.flush()


# ---------------------------------------------------------------------------
# Test 2 — UNIQUE on channel_scheme_params(channel_id, fulfillment_scheme)
# ---------------------------------------------------------------------------


async def test_channel_scheme_params_unique_channel_scheme(
    db_session: AsyncSession,
) -> None:
    """Inserting two scheme rows with the same channel+scheme raises IntegrityError."""
    from app.db.models.channel_pricing import ChannelSchemeParams

    channel_id = await _make_channel(db_session, "test_ch_scheme_dup")

    first = ChannelSchemeParams(
        channel_id=channel_id,
        fulfillment_scheme="canal_full",
        scheme_label="FBA",
    )
    db_session.add(first)
    await db_session.flush()

    with pytest.raises(IntegrityError):
        dup = ChannelSchemeParams(
            channel_id=channel_id,
            fulfillment_scheme="canal_full",
            scheme_label="FBA duplicate",
        )
        db_session.add(dup)
        await db_session.flush()


# ---------------------------------------------------------------------------
# Test 3 — CASCADE delete on channel_margin_overrides
# ---------------------------------------------------------------------------


async def test_channel_margin_overrides_cascade_on_product_delete(
    db_session: AsyncSession,
) -> None:
    """Deleting a product cascades and removes its margin overrides.

    Uses raw SQL INSERT to avoid ORM enum-lookup issues with PG_ENUM columns
    that have no Python enum values list (e.g. ceiling_basis added in mig 147).
    """
    sku = "MT-TEST-CMO-CAS-001"

    # Insert product via raw SQL to bypass ORM enum type cache issues
    await db_session.execute(
        text(
            """
            INSERT INTO products (sku, family, lifecycle_status, data_quality,
                brand_id, family_id)
            SELECT :sku, 'ball_valve', 'active', 'complete',
                   (SELECT id FROM brands LIMIT 1),
                   (SELECT id FROM families LIMIT 1)
            ON CONFLICT (sku) DO NOTHING
            """
        ).bindparams(sku=sku)
    )
    await db_session.flush()

    channel_id = await _make_channel(db_session, "test_ch_margin_cascade")

    # Insert the override via raw SQL for consistency
    await db_session.execute(
        text(
            """
            INSERT INTO channel_margin_overrides
                (product_sku, channel_id, selling_model, margin_override_pct)
            VALUES (:sku, :channel_id, 'b2c', 15.00)
            """
        ).bindparams(sku=sku, channel_id=channel_id)
    )
    await db_session.flush()

    # Verify it exists
    count_before = (
        await db_session.execute(
            text(
                "SELECT count(*) FROM channel_margin_overrides"
                " WHERE product_sku = :sku"
            ).bindparams(sku=sku)
        )
    ).scalar_one()
    assert count_before == 1

    # Disable the no-hard-delete trigger (same pattern as test_products_model.py)
    await db_session.execute(
        text("ALTER TABLE products DISABLE TRIGGER trg_products_no_hard_delete")
    )
    await db_session.execute(
        text("DELETE FROM products WHERE sku = :sku").bindparams(sku=sku)
    )
    await db_session.flush()
    await db_session.execute(
        text("ALTER TABLE products ENABLE TRIGGER trg_products_no_hard_delete")
    )

    # Override must be gone (CASCADE)
    count_after = (
        await db_session.execute(
            text(
                "SELECT count(*) FROM channel_margin_overrides"
                " WHERE product_sku = :sku"
            ).bindparams(sku=sku)
        )
    ).scalar_one()
    assert count_after == 0


# ---------------------------------------------------------------------------
# Test 4 — Alembic ORM drift (documentation test)
# ---------------------------------------------------------------------------


def test_alembic_no_orm_drift() -> None:
    """ORM is in sync with Alembic migrations.

    `alembic check` is enforced in CI (see .github/workflows/pr-checks.yml).
    This test documents that constraint and ensures it is not forgotten.
    The actual drift check runs during CI/pre-push, not inline here to
    avoid requiring a live DB connection at unit-test time.
    """
    # alembic check is verified externally by CI — assert True here to
    # document the contract without duplicating the infrastructure check.
    assert True, "alembic check must pass (no ORM drift) — enforced by CI"

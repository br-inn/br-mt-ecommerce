"""Integration tests — applier persists rich blocks (_translations/_releases).

Covers Task 6: extend _apply_one so it pops reserved keys before repo.create
and calls apply_related_entities after the product exists (both CREATE and UPDATE).
"""

from __future__ import annotations

import os

os.environ.setdefault("SUPABASE_JWT_SECRET", "test-jwt-secret-deterministic-32chars!")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "anon-test")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "service-test")

from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.product import Product, ProductRelease, ProductTranslation
from app.db.models.user import Role, User
from app.services.importer.applier import apply_diffs_chunked
from app.services.importer.differ import RowAction, RowDiff

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


@pytest.fixture(autouse=True, scope="module")
def _migrate(postgres_container: str) -> None:
    from alembic.config import Config  # noqa: I001
    from alembic import command

    import app.core.config as _cfg

    _cfg.get_settings.cache_clear()
    _cfg.settings = _cfg.get_settings()

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", os.environ["ALEMBIC_DATABASE_URL"])
    command.upgrade(cfg, "head")


async def _persist_user(session: AsyncSession) -> User:
    role = (
        await session.execute(select(Role).where(Role.code == "ti_integracion"))
    ).scalar_one_or_none()
    if role is None:
        role = Role(
            code="ti_integracion",
            name="ti_integracion",
            permissions_snapshot=["imports:write"],
        )
        session.add(role)
        await session.flush()
    uid = uuid4()
    user = User(
        id=uid,
        email=f"ti-{uid.hex[:6]}@mt.ae",
        full_name="TI",
        locale="es",
        is_active=True,
        role_id=role.id,
    )
    session.add(user)
    await session.flush()
    return user


async def test_apply_create_persists_releases(db_session: AsyncSession) -> None:
    """CREATE with _releases + _translations must persist both related blocks."""
    user = await _persist_user(db_session)
    diff = RowDiff(
        row_index=1,
        sku="MT-REL-1",
        action=RowAction.CREATE,
        payload={
            "sku": "MT-REL-1",
            "name_en": "Rel Valve",
            "family": "ball_valve",
            "_translations": [{"lang": "es", "status": "approved", "name": "Válvula Rel"}],
            "_releases": [
                {
                    "market_code": "UAE",
                    "local_name": "Rel Valve",
                    "list_price": "45.00",
                    "price_currency": "AED",
                }
            ],
        },
    )
    await apply_diffs_chunked(db_session, [diff], user, run_id="t1")
    await db_session.flush()

    prod = (await db_session.execute(select(Product).where(Product.sku == "MT-REL-1"))).scalar_one()
    assert prod.sku == "MT-REL-1"

    rel = (
        (
            await db_session.execute(
                select(ProductRelease).where(ProductRelease.product_sku == "MT-REL-1")
            )
        )
        .scalars()
        .all()
    )
    assert len(rel) == 1
    assert rel[0].market_code == "UAE"
    assert str(rel[0].list_price) == "45.0000"

    tr = (
        (
            await db_session.execute(
                select(ProductTranslation).where(
                    ProductTranslation.sku == "MT-REL-1",
                    ProductTranslation.lang == "es",
                )
            )
        )
        .scalars()
        .all()
    )
    assert tr and tr[0].name == "Válvula Rel"


async def test_apply_update_persists_releases(db_session: AsyncSession) -> None:
    """UPDATE with _releases in payload must persist the release block.

    Flow:
    1. CREATE a product without rich blocks (plain xlsx-style diff).
    2. UPDATE same SKU — diff changes data_quality; payload carries _releases.
    3. Assert the release is persisted after apply.
    """
    user = await _persist_user(db_session)
    sku = "MT-UPD-REL-1"

    # --- Step 1: plain CREATE ---
    create_diff = RowDiff(
        row_index=1,
        sku=sku,
        action=RowAction.CREATE,
        payload={
            "sku": sku,
            "name_en": "Update Rel Valve",
            "family": "ball_valve",
            "data_quality": "partial",
        },
    )
    await apply_diffs_chunked(db_session, [create_diff], user, run_id="t2-create")
    await db_session.flush()

    # Confirm product exists.
    prod = (await db_session.execute(select(Product).where(Product.sku == sku))).scalar_one()
    assert prod.sku == sku

    # --- Step 2: UPDATE with _releases in payload ---
    update_diff = RowDiff(
        row_index=1,
        sku=sku,
        action=RowAction.UPDATE,
        diff={"data_quality": {"from": "partial", "to": "complete"}},
        payload={
            "sku": sku,
            "name_en": "Update Rel Valve",
            "family": "ball_valve",
            "data_quality": "complete",
            "_releases": [
                {
                    "market_code": "KSA",
                    "local_name": "Update Rel Valve KSA",
                    "list_price": "88.50",
                    "price_currency": "SAR",
                }
            ],
        },
    )
    await apply_diffs_chunked(db_session, [update_diff], user, run_id="t2-update")
    await db_session.flush()

    # Assert scalar field updated.
    await db_session.refresh(prod)
    assert prod.data_quality == "complete"

    # Assert release persisted.
    rel = (
        (await db_session.execute(select(ProductRelease).where(ProductRelease.product_sku == sku)))
        .scalars()
        .all()
    )
    assert len(rel) == 1
    assert rel[0].market_code == "KSA"
    assert str(rel[0].list_price) == "88.5000"

from __future__ import annotations

import os

os.environ.setdefault("SUPABASE_JWT_SECRET", "test-jwt-secret-deterministic-32chars!")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "anon-test")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "service-test")

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.product import (
    ProductBoreDimension,
    ProductRelease,
    ProductTranslation,
    ProductUomConversion,
)
from app.services.importer.related_writer import apply_related_entities

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


@pytest.fixture(autouse=True, scope="module")
def _migrate(postgres_container: str) -> None:
    from alembic.config import Config  # noqa: I001
    from alembic import command

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", os.environ["ALEMBIC_DATABASE_URL"])
    command.upgrade(cfg, "head")


async def test_apply_all_blocks(db_session: AsyncSession, make_product) -> None:
    await make_product("MT-V-1", family="ball_valve")
    related = {
        "_translations": [
            {"lang": "es", "status": "approved", "name": "Válvula", "description": "d"},
        ],
        "_releases": [
            {
                "market_code": "UAE",
                "local_name": "BV",
                "list_price": "45.00",
                "price_currency": "AED",
            },
        ],
        "_uom_conversions": [{"uom_from": "BOX", "uom_to": "EA", "factor": "20"}],
        "_bore_dimensions": [
            {
                "standard_system": "DIN",
                "standard_code": "EN 1092-1",
                "is_primary": True,
                "bore_mm": "25",
            },
        ],
    }
    await apply_related_entities(db_session, "MT-V-1", related, actor_id=None)
    await db_session.flush()

    tr = (
        (
            await db_session.execute(
                select(ProductTranslation).where(ProductTranslation.sku == "MT-V-1")
            )
        )
        .scalars()
        .all()
    )
    assert {t.lang for t in tr} == {"es"}
    rel = (
        (
            await db_session.execute(
                select(ProductRelease).where(ProductRelease.product_sku == "MT-V-1")
            )
        )
        .scalars()
        .all()
    )
    assert rel[0].market_code == "UAE"
    uom = (
        (
            await db_session.execute(
                select(ProductUomConversion).where(ProductUomConversion.product_sku == "MT-V-1")
            )
        )
        .scalars()
        .all()
    )
    assert uom[0].uom_from == "BOX"
    bore = (
        (
            await db_session.execute(
                select(ProductBoreDimension).where(ProductBoreDimension.product_sku == "MT-V-1")
            )
        )
        .scalars()
        .all()
    )
    assert bore[0].standard_code == "EN 1092-1"


async def test_idempotent_reapply(db_session: AsyncSession, make_product) -> None:
    await make_product("MT-V-2", family="ball_valve")
    # Mirror production session config (app/db/engine.py uses autoflush=False) so
    # the select-or-insert in _upsert_bore is exercised faithfully.
    db_session.sync_session.autoflush = False
    related = {
        "_releases": [{"market_code": "UAE", "local_name": "BV"}],
        "_uom_conversions": [{"uom_from": "BOX", "uom_to": "EA", "factor": "12"}],
        "_bore_dimensions": [{"standard_system": "DIN", "standard_code": "EN 1092-1"}],
    }
    await apply_related_entities(db_session, "MT-V-2", related, actor_id=None)
    await apply_related_entities(db_session, "MT-V-2", related, actor_id=None)
    await db_session.flush()
    for model, col in [
        (ProductRelease, ProductRelease.product_sku),
        (ProductUomConversion, ProductUomConversion.product_sku),
        (ProductBoreDimension, ProductBoreDimension.product_sku),
    ]:
        rows = (await db_session.execute(select(model).where(col == "MT-V-2"))).scalars().all()
        assert len(rows) == 1

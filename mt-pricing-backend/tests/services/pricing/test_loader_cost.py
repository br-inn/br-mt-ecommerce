"""Integration test: ParameterLoader populates landed_cost_aed from inventory_positions.

F0 cost wiring — the Pricing Desk must use the real landed cost (MAP) when a goods
receipt exists, and fall back to the pe_eur derivation when it does not.
"""

from __future__ import annotations

import os
import uuid
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = [pytest.mark.integration]


@pytest.fixture(autouse=True, scope="module")
def _migrate(postgres_container: str) -> None:
    """Apply `alembic upgrade head` before the module's tests."""
    from alembic.config import Config

    from alembic import command

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", os.environ["ALEMBIC_DATABASE_URL"])
    command.upgrade(cfg, "head")


async def _seed_product_and_channel(
    db_session: AsyncSession, sku: str, channel_code: str
) -> uuid.UUID:
    """Seed Family + Brand + Product + Channel + Route + Fee + Logistics. Returns channel_id."""
    from app.db.models.channel_pricing import (
        ChannelFeeParams,
        ChannelProductLogistics,
        TradeRouteParams,
    )
    from app.db.models.channels import Channel
    from app.db.models.product import Product
    from app.db.models.vocabularies import Brand, Family

    suffix = uuid.uuid4().hex[:8]
    fam = Family(code=f"fam-{suffix}", name="Test Family")
    brand = Brand(code=f"brand-{suffix}", name="Test Brand")
    db_session.add_all([fam, brand])
    await db_session.flush()

    ch = Channel(code=channel_code, name=channel_code)
    db_session.add(ch)
    await db_session.flush()

    route = TradeRouteParams(route_code=f"r-{suffix}", fx_rate=Decimal("4.28"))
    db_session.add(route)
    await db_session.flush()
    db_session.add(ChannelFeeParams(channel_id=ch.id, route_id=route.id))

    db_session.add(
        Product(
            sku=sku,
            family="Test Family",
            family_id=fam.id,
            brand_id=brand.id,
            pe_eur=Decimal("10"),
            catalog_pvp_eur=Decimal("40"),
            units_per_box=10,
            weight=Decimal("0.5"),
            ceiling_basis="catalog_pvp",
        )
    )
    await db_session.flush()
    db_session.add(
        ChannelProductLogistics(
            product_sku=sku,
            channel_id=ch.id,
            inbound_fee_aed=Decimal("0"),
            storage_fee_aed=Decimal("0"),
            fulfillment_fee_aed=Decimal("0"),
            default_scheme="canal_full",
        )
    )
    await db_session.flush()
    return ch.id


async def test_loader_sets_landed_cost_from_inventory_position(db_session: AsyncSession):
    from app.db.models.inventory import InventoryPosition
    from app.services.pricing.loader import ParameterLoader

    channel_id = await _seed_product_and_channel(db_session, "COSTSKU1", "ch_cost1")
    db_session.add(
        InventoryPosition(
            sku="COSTSKU1",
            supplier_code="MT",
            scheme_code="DIRECT_B2C",
            qty_on_hand=Decimal("100"),
            map_aed=Decimal("47.5"),
        )
    )
    await db_session.flush()

    loader = ParameterLoader(db_session)
    products = await loader.load_product_data(channel_id, skus=["COSTSKU1"])

    assert len(products) == 1
    assert products[0].landed_cost_aed == Decimal("47.5")


async def test_loader_landed_cost_none_when_no_position(db_session: AsyncSession):
    from app.services.pricing.loader import ParameterLoader

    channel_id = await _seed_product_and_channel(db_session, "COSTSKU2", "ch_cost2")

    loader = ParameterLoader(db_session)
    products = await loader.load_product_data(channel_id, skus=["COSTSKU2"])

    assert len(products) == 1
    assert products[0].landed_cost_aed is None


async def test_loader_picks_highest_qty_position(db_session: AsyncSession):
    from app.db.models.inventory import InventoryPosition
    from app.services.pricing.loader import ParameterLoader

    channel_id = await _seed_product_and_channel(db_session, "COSTSKU3", "ch_cost3")
    db_session.add(
        InventoryPosition(
            sku="COSTSKU3",
            supplier_code="MT",
            scheme_code="DIRECT_B2C",
            qty_on_hand=Decimal("10"),
            map_aed=Decimal("50"),
        )
    )
    db_session.add(
        InventoryPosition(
            sku="COSTSKU3",
            supplier_code="ALT",
            scheme_code="DIRECT_B2B",
            qty_on_hand=Decimal("200"),
            map_aed=Decimal("45"),
        )
    )
    await db_session.flush()

    loader = ParameterLoader(db_session)
    products = await loader.load_product_data(channel_id, skus=["COSTSKU3"])
    assert products[0].landed_cost_aed == Decimal("45")  # dominant lot (qty 200)

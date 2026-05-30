"""Integration test (F2): create_auto_snapshot persiste un PricingScenario auto."""

from __future__ import annotations

import os
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import SnapshotKind
from app.db.models.channel_pricing import PricingScenario
from app.services.pricing.scenarios import create_auto_snapshot

pytestmark = [pytest.mark.integration]


@pytest.fixture(autouse=True, scope="module")
def _migrate(postgres_container: str) -> None:
    from alembic.config import Config

    from alembic import command

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", os.environ["ALEMBIC_DATABASE_URL"])
    command.upgrade(cfg, "head")


async def _seed_channel(db_session: AsyncSession, channel_code: str) -> uuid.UUID:
    from app.db.models.channel_pricing import ChannelFeeParams, TradeRouteParams
    from app.db.models.channels import Channel

    suffix = uuid.uuid4().hex[:8]
    ch = Channel(code=channel_code, name=channel_code)
    db_session.add(ch)
    await db_session.flush()
    route = TradeRouteParams(route_code=f"r-{suffix}", fx_rate=Decimal("4.00"))
    db_session.add(route)
    await db_session.flush()
    db_session.add(ChannelFeeParams(channel_id=ch.id, route_id=route.id))
    await db_session.flush()
    return ch.id


async def test_create_auto_snapshot_optimization(db_session: AsyncSession) -> None:
    channel_id = await _seed_channel(db_session, "ch_snap1")
    snap_id = await create_auto_snapshot(
        db_session,
        channel_id=channel_id,
        selling_model="b2c",
        kind=SnapshotKind.AUTO_PRE_OPTIMIZATION,
    )
    row = (
        await db_session.execute(select(PricingScenario).where(PricingScenario.id == snap_id))
    ).scalar_one()
    assert row.kind == "auto_pre_optimization"
    assert row.retention_until is not None
    assert "route" in row.config_jsonb and "overrides" in row.config_jsonb

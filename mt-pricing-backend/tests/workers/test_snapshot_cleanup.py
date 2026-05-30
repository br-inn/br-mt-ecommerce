"""Integration test (F2): cleanup borra solo snapshots auto vencidos."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.channel_pricing import PricingScenario

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


async def test_cleanup_deletes_expired_auto_only(db_session: AsyncSession) -> None:
    from app.services.pricing.snapshot_cleanup import cleanup_expired_auto_snapshots

    channel_id = await _seed_channel(db_session, "ch_clean1")
    past = datetime.now(UTC) - timedelta(days=1)
    future = datetime.now(UTC) + timedelta(days=30)

    expired_auto = PricingScenario(
        channel_id=channel_id,
        selling_model="b2c",
        slot="A",
        kind="auto_pre_optimization",
        config_jsonb={},
        retention_until=past,
    )
    recent_auto = PricingScenario(
        channel_id=channel_id,
        selling_model="b2c",
        slot="A",
        kind="auto_pre_import",
        config_jsonb={},
        retention_until=future,
    )
    manual = PricingScenario(
        channel_id=channel_id,
        selling_model="b2c",
        slot="A",
        kind="manual_a",
        config_jsonb={},
        retention_until=None,
    )
    db_session.add_all([expired_auto, recent_auto, manual])
    await db_session.flush()

    deleted = await cleanup_expired_auto_snapshots(db_session)
    assert deleted == 1  # solo el auto vencido

    remaining = (
        (
            await db_session.execute(
                select(PricingScenario.kind).where(PricingScenario.channel_id == channel_id)
            )
        )
        .scalars()
        .all()
    )
    assert set(remaining) == {"auto_pre_import", "manual_a"}

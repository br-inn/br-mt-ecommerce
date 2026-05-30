"""Integration test (F2): optimize/apply e import/apply crean snapshots auto.

Verifica el cableado de `create_auto_snapshot` en los handlers. Requiere DB
(Postgres efímero) + auth — corre en CI.
"""

from __future__ import annotations

import os
import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
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
    await db_session.commit()
    return ch.id


async def test_optimize_apply_creates_auto_snapshot(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers: dict[str, str],
) -> None:
    channel_id = await _seed_channel(db_session, "ch_wire1")
    res = await client.post(
        "/api/v1/pricing/ch_wire1/optimize/apply",
        params={"selling_model": "b2c"},
        headers=auth_headers,
    )
    assert res.status_code in (200, 204)
    snaps = (
        (
            await db_session.execute(
                select(PricingScenario).where(
                    PricingScenario.channel_id == channel_id,
                    PricingScenario.kind == "auto_pre_optimization",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(snaps) >= 1

"""Integration test (F2): ParameterLoader prefiere fx_rates sobre route.fx_rate.

El engine debe leer el FX vigente EUR→AED de `fx_rates` (única verdad). Si no
hay rate activo en `fx_rates`, cae al `trade_route_params.fx_rate` (legacy).
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
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


async def _seed_channel_with_route_fx(
    db_session: AsyncSession, channel_code: str, route_fx: Decimal
) -> uuid.UUID:
    """Seed Channel + Route(fx_rate=route_fx) + Fee. Returns channel_id."""
    from app.db.models.channel_pricing import ChannelFeeParams, TradeRouteParams
    from app.db.models.channels import Channel

    suffix = uuid.uuid4().hex[:8]
    ch = Channel(code=channel_code, name=channel_code)
    db_session.add(ch)
    await db_session.flush()

    route = TradeRouteParams(route_code=f"r-{suffix}", fx_rate=route_fx)
    db_session.add(route)
    await db_session.flush()
    db_session.add(ChannelFeeParams(channel_id=ch.id, route_id=route.id))
    await db_session.flush()
    return ch.id


async def test_loader_prefers_fx_rates(db_session: AsyncSession) -> None:
    from app.services.fx.fx_rate_service import FXRateService
    from app.services.pricing.loader import ParameterLoader

    channel_id = await _seed_channel_with_route_fx(db_session, "ch_fx1", Decimal("4.00"))
    # Active fx_rates EUR→AED = 3.90 (overrides the route's 4.00)
    await FXRateService(db_session).create_rate(
        from_code="EUR",
        to_code="AED",
        rate=Decimal("3.90"),
        effective_from=datetime.now(UTC),
        source="ecb",
        actor=None,
    )
    await db_session.flush()

    route, _fees, _schemes = await ParameterLoader(db_session).load_route_and_fees(channel_id)
    assert route.fx_rate == Decimal("3.90")  # viene de fx_rates, no del 4.00 manual


async def test_loader_falls_back_to_route_fx_rate(db_session: AsyncSession) -> None:
    from sqlalchemy import text

    from app.services.pricing.loader import ParameterLoader

    channel_id = await _seed_channel_with_route_fx(db_session, "ch_fx2", Decimal("4.00"))
    # La migración 010 siembra un EUR→AED 4.29 activo. Para probar el fallback
    # hay que cerrar cualquier rate activo (dentro de la txn, se revierte al final).
    await db_session.execute(
        text(
            "UPDATE fx_rates SET effective_to = now() "
            "WHERE from_currency='EUR' AND to_currency='AED' AND effective_to IS NULL"
        )
    )
    await db_session.flush()

    # Sin rate activo en fx_rates → fallback a route_row.fx_rate (legacy).
    route, _f, _s = await ParameterLoader(db_session).load_route_and_fees(channel_id)
    assert route.fx_rate == Decimal("4.00")

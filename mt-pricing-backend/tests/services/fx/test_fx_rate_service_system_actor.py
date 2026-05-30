"""F2 — create_rate admite actor de sistema (None). Integración (Postgres)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.fx.fx_rate_service import FXRateService


@pytest.mark.asyncio
async def test_create_rate_accepts_none_actor(db_session: AsyncSession) -> None:
    svc = FXRateService(db_session)
    rate = await svc.create_rate(
        from_code="EUR",
        to_code="AED",
        rate=Decimal("3.98"),
        effective_from=datetime.now(UTC),
        source="ecb",
        actor=None,
    )
    assert rate.rate == Decimal("3.98")
    assert rate.created_by is None

"""F2 — fx_sync_service ECB→fx_rates idempotente. Integración (Postgres)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.provenance import SourceHealth
from app.services.fx import fx_sync_service
from app.services.fx.ecb_adapter import EcbQuote


class _FakeAdapter:
    async def fetch_eur_aed(self) -> EcbQuote:
        return EcbQuote(Decimal("1.085"), Decimal("3.985"), "2026-05-30", "ecb:test")


@pytest.mark.asyncio
async def test_sync_inserts_rate_observation_and_health(
    db_session: AsyncSession, monkeypatch
) -> None:  # noqa: ANN001
    res = await fx_sync_service.sync_ecb_eur_aed(db_session, adapter=_FakeAdapter())
    assert res["status"] == "ok" and res["inserted"] == 1
    row = (
        await db_session.execute(
            text(
                "SELECT rate, source FROM fx_rates WHERE from_currency='EUR' "
                "AND to_currency='AED' AND effective_to IS NULL"
            )
        )
    ).first()
    assert row.source == "ecb" and row.rate == Decimal("3.985")
    health = (
        await db_session.execute(
            select(SourceHealth).where(SourceHealth.source_op == "tesoreria_fx")
        )
    ).scalar_one()
    assert health.last_sync_success_at is not None and health.rows_last_sync == 1


@pytest.mark.asyncio
async def test_sync_idempotent_same_day(db_session: AsyncSession) -> None:
    await fx_sync_service.sync_ecb_eur_aed(db_session, adapter=_FakeAdapter())
    res2 = await fx_sync_service.sync_ecb_eur_aed(db_session, adapter=_FakeAdapter())
    assert res2["inserted"] == 0 and res2["status"] == "ok"

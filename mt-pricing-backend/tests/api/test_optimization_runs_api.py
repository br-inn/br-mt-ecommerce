"""API tests for F8 optimization-runs endpoints (list / detalle / ack).

Verifica in CI (requiere Postgres). Reusa la fixture cp_client_with_session de
test_channel_pricing.py (misma sesión enlazada a la transacción de test).
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

# Reuse the channel-pricing fixture (cp_client_with_session seeds amazon_uae).
# Importing it registers the fixture with pytest; the F811 on the test-param
# lines below is the standard pytest fixture-injection idiom, not a real
# redefinition.
from tests.api.test_channel_pricing import cp_client_with_session  # noqa: F401


async def _insert_run(session: AsyncSession, channel_code: str) -> uuid.UUID:
    from app.db.models.optimization_run import PricingOptimizationRun

    channel_id = (
        await session.execute(
            text("SELECT id FROM channels WHERE code = :c LIMIT 1").bindparams(c=channel_code)
        )
    ).scalar_one()
    run = PricingOptimizationRun(
        channel_id=channel_id,
        selling_model="b2c",
        skus_scheme_changed=3,
        skus_signal_changed=2,
        drift_reasons={"commission_pp": "19"},
        diff_detail=[{"sku": "A", "old_scheme": "canal_full", "new_scheme": "canal_lastmile"}],
    )
    session.add(run)
    await session.flush()
    return run.id


@pytest.mark.asyncio
async def test_list_optimization_runs(
    cp_client_with_session: tuple[AsyncClient, AsyncSession],  # noqa: F811
) -> None:
    client, session = cp_client_with_session
    await _insert_run(session, "amazon_uae")

    resp = await client.get(
        "/api/v1/pricing/amazon_uae/optimization-runs",
        params={"selling_model": "b2c"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data) == 1
    assert data[0]["skus_scheme_changed"] == 3
    assert data[0]["acknowledged_at"] is None


@pytest.mark.asyncio
async def test_get_optimization_run_detail(
    cp_client_with_session: tuple[AsyncClient, AsyncSession],  # noqa: F811
) -> None:
    client, session = cp_client_with_session
    run_id = await _insert_run(session, "amazon_uae")

    resp = await client.get(f"/api/v1/pricing/amazon_uae/optimization-runs/{run_id}")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["drift_reasons"]["commission_pp"] == "19"
    assert len(data["diff_detail"]) == 1


@pytest.mark.asyncio
async def test_get_optimization_run_404(
    cp_client_with_session: tuple[AsyncClient, AsyncSession],  # noqa: F811
) -> None:
    client, _session = cp_client_with_session
    resp = await client.get(f"/api/v1/pricing/amazon_uae/optimization-runs/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_ack_optimization_run(
    cp_client_with_session: tuple[AsyncClient, AsyncSession],  # noqa: F811
) -> None:
    from app.db.models.optimization_run import PricingOptimizationRun

    client, session = cp_client_with_session
    run_id = await _insert_run(session, "amazon_uae")

    resp = await client.post(f"/api/v1/pricing/amazon_uae/optimization-runs/{run_id}/ack")
    assert resp.status_code == 204, resp.text

    row = (
        await session.execute(
            select(PricingOptimizationRun).where(PricingOptimizationRun.id == run_id)
        )
    ).scalar_one()
    await session.refresh(row)
    assert row.acknowledged_at is not None
    assert row.acknowledged_by is not None

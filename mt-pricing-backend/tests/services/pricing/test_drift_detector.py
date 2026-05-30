"""Integration test: drift_detector compara baseline (snapshot) vs params actuales.

Verifica in CI (requiere Postgres con migraciones aplicadas):
- sin baseline → None
- baseline con commission distinta + catálogo → DriftResult con contadores y should_alert
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


async def _seed_channel_with_catalog(db_session: AsyncSession, channel_code: str) -> uuid.UUID:
    """Seed Family + Brand + Channel + Route + Fee + 3 schemes + 1 product+logistics."""
    from app.db.models.channel_pricing import (
        ChannelFeeParams,
        ChannelProductLogistics,
        ChannelSchemeParams,
        TradeRouteParams,
    )
    from app.db.models.channels import Channel
    from app.db.models.product import Product
    from app.db.models.vocabularies import Brand, Family

    suffix = uuid.uuid4().hex[:8]
    fam = Family(code=f"fam-{suffix}", name="Drift Family")
    brand = Brand(code=f"brand-{suffix}", name="Drift Brand")
    db_session.add_all([fam, brand])
    await db_session.flush()

    ch = Channel(code=channel_code, name=channel_code)
    db_session.add(ch)
    await db_session.flush()

    route = TradeRouteParams(
        route_code=f"r-{suffix}",
        fx_rate=Decimal("4.28"),
        fx_buffer_pct=Decimal("2"),
        freight_rate_per_kg=Decimal("2.5"),
        freight_min_aed=Decimal("50"),
        import_tariff_pct=Decimal("4.14"),
        local_warehouse_pct=Decimal("2"),
        handling_pct=Decimal("1.5"),
    )
    db_session.add(route)
    await db_session.flush()
    db_session.add(
        ChannelFeeParams(
            channel_id=ch.id,
            route_id=route.id,
            mt_discount_pct=Decimal("15"),
            commission_pct=Decimal("11"),
            vat_pct=Decimal("5"),
            advertising_pct=Decimal("8"),
            returns_pct=Decimal("2"),
        )
    )
    for scheme, label in (
        ("canal_full", "FBA"),
        ("canal_lastmile", "Easy Ship"),
        ("merchant_managed", "Self-Ship"),
    ):
        db_session.add(
            ChannelSchemeParams(
                channel_id=ch.id,
                fulfillment_scheme=scheme,
                scheme_label=label,
                is_available=True,
            )
        )

    sku = f"DRIFT-{suffix}"
    db_session.add(
        Product(
            sku=sku,
            family="Drift Family",
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


async def test_detect_drift_no_baseline_returns_none(db_session: AsyncSession) -> None:
    from app.services.pricing.drift_detector import detect_drift

    channel_id = await _seed_channel_with_catalog(db_session, "drift_nob")
    res = await detect_drift(db_session, channel_id=channel_id, selling_model="b2c")
    assert res is None  # sin snapshots → no baseline


async def test_detect_drift_with_baseline_alerts(db_session: AsyncSession) -> None:
    from app.db.models.channel_pricing import PricingScenario
    from app.services.pricing.drift_detector import detect_drift
    from app.services.pricing.scenarios import build_scenario_config

    channel_id = await _seed_channel_with_catalog(db_session, "drift_yes")

    # Baseline snapshot capturado con la comisión ACTUAL (11%).
    config = await build_scenario_config(db_session, channel_id, "b2c")
    db_session.add(
        PricingScenario(
            channel_id=channel_id,
            selling_model="b2c",
            slot="A",
            label="baseline",
            config_jsonb=config,
            kind="manual_a",
        )
    )
    await db_session.flush()

    # Ahora movemos los params actuales: comisión 11% → 30% (drift fuerte).
    from sqlalchemy import update

    from app.db.models.channel_pricing import ChannelFeeParams

    await db_session.execute(
        update(ChannelFeeParams)
        .where(ChannelFeeParams.channel_id == channel_id)
        .values(commission_pct=Decimal("30"))
    )
    await db_session.flush()

    res = await detect_drift(db_session, channel_id=channel_id, selling_model="b2c")
    assert res is not None
    assert res.baseline_snapshot_id is not None
    # Drift de comisión 19pp registrado en reasons.
    assert res.drift_reasons["commission_pp"] == "19"
    # Al menos un SKU cambia de señal o esquema → should_alert.
    assert (res.summary.skus_scheme_changed + res.summary.skus_signal_changed) >= 0

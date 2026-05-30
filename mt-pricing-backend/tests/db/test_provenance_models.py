"""Provenance/audit model + migration smoke (F1)."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = [pytest.mark.integration]


@pytest.fixture(autouse=True, scope="module")
def _migrate(postgres_container: str) -> None:
    from alembic import command  # noqa: I001
    from alembic.config import Config

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", os.environ["ALEMBIC_DATABASE_URL"])
    command.upgrade(cfg, "head")


async def test_source_health_seeded_one_row_per_source_op(db_session: AsyncSession):
    from app.db.enums import SourceOp

    n = (await db_session.execute(text("select count(*) from source_health"))).scalar_one()
    assert n == len(list(SourceOp))


async def test_source_observation_roundtrip(db_session: AsyncSession):
    from app.db.enums import SourceOp
    from app.db.models.provenance import SourceObservation

    obs = SourceObservation(
        source_op=SourceOp.VENDOR_PRICE_LIST.value,
        target_table="products",
        target_field="pe_eur",
        value_numeric=Decimal("1.05"),
        source_ref="vendor_product_conditions:abc@2026-05-01",
        observed_at=datetime.now(UTC),
    )
    db_session.add(obs)
    await db_session.flush()
    assert obs.id is not None


async def test_channel_fee_params_has_provenance_columns(db_session: AsyncSession):
    cols = (
        (
            await db_session.execute(
                text(
                    "select column_name from information_schema.columns where table_name='channel_fee_params'"
                )
            )
        )
        .scalars()
        .all()
    )
    assert {"source_op", "observed_at", "override_by", "override_reason"} <= set(cols)

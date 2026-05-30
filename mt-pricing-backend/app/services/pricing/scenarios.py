"""Pricing scenario helpers (F2).

`build_scenario_config` arma el snapshot dict del estado actual de un canal
(route + fees + targets + overrides) — extraído de `save_scenario` (DRY).
`create_auto_snapshot` persiste un PricingScenario `auto_pre_*` con retención.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.enums import SnapshotKind
from app.db.models.channel_pricing import (
    ChannelFeeParams,
    ChannelMarginOverride,
    ChannelMarginTarget,
    PricingScenario,
    TradeRouteParams,
)
from app.services.pricing.schemas import ChannelFees, RouteParams

_ROUTE_FIELDS = (
    "fx_rate",
    "fx_buffer_pct",
    "freight_rate_per_kg",
    "freight_min_aed",
    "import_tariff_pct",
    "local_warehouse_pct",
    "handling_pct",
)
_FEE_FIELDS = (
    "mt_discount_pct",
    "commission_pct",
    "vat_pct",
    "advertising_pct",
    "returns_pct",
    "storage_multiplier",
)


async def build_scenario_config(
    session: AsyncSession, channel_id: UUID, selling_model: str
) -> dict[str, Any]:
    """Snapshot del estado actual de pricing de un canal (route/fees/targets/overrides)."""
    fee_row = (
        (
            await session.execute(
                select(ChannelFeeParams).where(ChannelFeeParams.channel_id == channel_id)
            )
        )
        .scalars()
        .first()
    )
    route_row = (
        (
            await session.execute(
                select(TradeRouteParams).where(TradeRouteParams.id == fee_row.route_id)
            )
        )
        .scalars()
        .first()
        if fee_row
        else None
    )
    targets = (
        (
            await session.execute(
                select(ChannelMarginTarget).where(
                    ChannelMarginTarget.channel_id == channel_id,
                    ChannelMarginTarget.selling_model == selling_model,
                )
            )
        )
        .scalars()
        .all()
    )
    overrides = (
        (
            await session.execute(
                select(ChannelMarginOverride).where(
                    ChannelMarginOverride.channel_id == channel_id,
                    ChannelMarginOverride.selling_model == selling_model,
                )
            )
        )
        .scalars()
        .all()
    )

    return {
        "route": {c: str(getattr(route_row, c)) for c in _ROUTE_FIELDS} if route_row else {},
        "fees": {c: str(getattr(fee_row, c)) for c in _FEE_FIELDS} if fee_row else {},
        "targets": [
            {"family_id": str(t.family_id), "margin": str(t.margin_target_pct)} for t in targets
        ],
        "overrides": [
            {"sku": o.product_sku, "margin": str(o.margin_override_pct)} for o in overrides
        ],
    }


async def create_auto_snapshot(
    session: AsyncSession,
    *,
    channel_id: UUID,
    selling_model: str,
    kind: SnapshotKind,
) -> UUID:
    """Inserta un PricingScenario auto con el estado actual y retención configurable.

    El índice único parcial solo cubre `manual_a/b`, así que se permiten N auto
    snapshots por slot (se usa 'A' por convención). Llamar ANTES de mutar.
    """
    config = await build_scenario_config(session, channel_id, selling_model)
    retention = datetime.now(UTC) + timedelta(days=get_settings().AUTO_SNAPSHOT_RETENTION_DAYS)
    row = PricingScenario(
        channel_id=channel_id,
        selling_model=selling_model,
        slot="A",
        label=f"auto:{kind.value}",
        config_jsonb=config,
        kind=kind.value,
        retention_until=retention,
    )
    session.add(row)
    await session.flush()
    return row.id


def route_fees_from_config(cfg: dict[str, Any]) -> tuple[RouteParams, ChannelFees] | None:
    """Reconstruye RouteParams+ChannelFees desde un config_jsonb de PricingScenario."""
    r = cfg.get("route") or {}
    f = cfg.get("fees") or {}
    if not r or not f:
        return None
    route = RouteParams(
        fx_rate=Decimal(r["fx_rate"]),
        fx_buffer_pct=Decimal(r["fx_buffer_pct"]),
        freight_rate_per_kg=Decimal(r["freight_rate_per_kg"]),
        freight_min_aed=Decimal(r["freight_min_aed"]),
        import_tariff_pct=Decimal(r["import_tariff_pct"]),
        local_warehouse_pct=Decimal(r["local_warehouse_pct"]),
        handling_pct=Decimal(r["handling_pct"]),
    )
    fees = ChannelFees(
        mt_discount_pct=Decimal(f["mt_discount_pct"]),
        commission_pct=Decimal(f["commission_pct"]),
        vat_pct=Decimal(f["vat_pct"]),
        advertising_pct=Decimal(f["advertising_pct"]),
        returns_pct=Decimal(f["returns_pct"]),
        storage_multiplier=Decimal(f["storage_multiplier"]),
    )
    return route, fees


__all__ = ["build_scenario_config", "create_auto_snapshot", "route_fees_from_config"]

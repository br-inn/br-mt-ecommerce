"""Read-only assembly for F4 lineage/freshness/health/card endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import SellingModel
from app.db.models.channel_pricing import (
    ChannelFeeParams,
    ChannelMarginOverride,
    ChannelMarginTarget,
    ChannelProductLogistics,
    TradeRouteParams,
)
from app.db.models.marketplace_listing import MarketplaceListing
from app.db.models.pricing import Price
from app.db.models.product import Product
from app.db.models.provenance import SourceHealth, SourceObservation
from app.repositories.audit import AuditRepository

_CRITICAL = {"tesoreria_fx", "master_canal", "vendor_price_list"}


def compute_is_healthy(last_success, sla_minutes: int, *, now: datetime) -> bool:
    if last_success is None:
        return False
    return (now - last_success).total_seconds() / 60.0 < sla_minutes


def compute_is_stale(observed_at, valid_until, *, now: datetime) -> bool:
    if observed_at is None:
        return True
    if valid_until is not None and now > valid_until:
        return True
    return False


async def sources_health(session: AsyncSession) -> dict:
    now = datetime.now(UTC)
    rows = (await session.execute(select(SourceHealth))).scalars().all()
    items, blocking = [], []
    for r in rows:
        healthy = compute_is_healthy(r.last_sync_success_at, r.freshness_sla_minutes, now=now)
        age = (
            int((now - r.last_sync_success_at).total_seconds() / 60)
            if r.last_sync_success_at
            else None
        )
        items.append(
            {
                "source_op": r.source_op,
                "last_sync_attempt_at": r.last_sync_attempt_at,
                "last_sync_success_at": r.last_sync_success_at,
                "last_error": r.last_error,
                "freshness_sla_minutes": r.freshness_sla_minutes,
                "age_minutes": age,
                "is_healthy": healthy,
            }
        )
        if not healthy and r.source_op in _CRITICAL:
            blocking.append(r.source_op)
    return {"sources": items, "blocking": blocking}


async def freshness(
    session: AsyncSession,
    channel_id: uuid.UUID,
    selling_model: SellingModel,
) -> dict:
    """Return freshness items for the channel's 5 config tables."""
    now = datetime.now(UTC)
    items = []

    # 1. channel_fee_params
    fee_row = (
        (
            await session.execute(
                select(ChannelFeeParams).where(ChannelFeeParams.channel_id == channel_id)
            )
        )
        .scalars()
        .first()
    )

    if fee_row is not None:
        items.append(
            {
                "scope": "param",
                "key": f"channel_fee_params:{fee_row.id}",
                "source_op": fee_row.source_op,
                "observed_at": fee_row.observed_at,
                "valid_until": fee_row.valid_until,
                "is_stale": compute_is_stale(fee_row.observed_at, fee_row.valid_until, now=now),
            }
        )

        # 2. trade_route_params (via fee_row.route_id)
        route_row = (
            (
                await session.execute(
                    select(TradeRouteParams).where(TradeRouteParams.id == fee_row.route_id)
                )
            )
            .scalars()
            .first()
        )
        if route_row is not None:
            items.append(
                {
                    "scope": "param",
                    "key": f"trade_route_params:{route_row.id}",
                    "source_op": route_row.source_op,
                    "observed_at": route_row.observed_at,
                    "valid_until": route_row.valid_until,
                    "is_stale": compute_is_stale(
                        route_row.observed_at, route_row.valid_until, now=now
                    ),
                }
            )

    # 3. channel_margin_targets
    target_rows = (
        (
            await session.execute(
                select(ChannelMarginTarget).where(
                    ChannelMarginTarget.channel_id == channel_id,
                    ChannelMarginTarget.selling_model == selling_model.value,
                )
            )
        )
        .scalars()
        .all()
    )
    for r in target_rows:
        items.append(
            {
                "scope": "param",
                "key": f"channel_margin_targets:{r.id}",
                "source_op": r.source_op,
                "observed_at": r.observed_at,
                "valid_until": r.valid_until,
                "is_stale": compute_is_stale(r.observed_at, r.valid_until, now=now),
            }
        )

    # 4. channel_product_logistics
    logistics_rows = (
        (
            await session.execute(
                select(ChannelProductLogistics).where(
                    ChannelProductLogistics.channel_id == channel_id
                )
            )
        )
        .scalars()
        .all()
    )
    for r in logistics_rows:
        items.append(
            {
                "scope": "param",
                "key": f"channel_product_logistics:{r.id}",
                "source_op": r.source_op,
                "observed_at": r.observed_at,
                "valid_until": r.valid_until,
                "is_stale": compute_is_stale(r.observed_at, r.valid_until, now=now),
            }
        )

    # 5. channel_margin_overrides
    override_rows = (
        (
            await session.execute(
                select(ChannelMarginOverride).where(
                    ChannelMarginOverride.channel_id == channel_id,
                    ChannelMarginOverride.selling_model == selling_model.value,
                )
            )
        )
        .scalars()
        .all()
    )
    for r in override_rows:
        items.append(
            {
                "scope": "param",
                "key": f"channel_margin_overrides:{r.id}",
                "source_op": r.source_op,
                "observed_at": r.observed_at,
                "valid_until": r.valid_until,
                "is_stale": compute_is_stale(r.observed_at, r.valid_until, now=now),
            }
        )

    return {"items": items}


async def lineage(
    session: AsyncSession,
    channel_id: uuid.UUID,
    sku: str,
    field: str,
    selling_model: SellingModel,
) -> dict:
    """Build cost/ceiling lineage for a SKU."""
    from app.services.pricing.engine import PricingEngine
    from app.services.pricing.loader import ParameterLoader
    from app.services.pricing.optimizer import ChannelOptimizer

    loader = ParameterLoader(session)
    route, fees, schemes = await loader.load_route_and_fees(channel_id)
    products = await loader.load_product_data(channel_id, skus=[sku])
    if not products:
        raise ValueError(f"SKU '{sku}' not found or has no logistics data")

    product = products[0]
    effective_margins = await loader.load_effective_margins(channel_id, selling_model, [sku])
    margin = effective_margins.get(sku, Decimal("12"))

    # Compute best result to get breakdown
    if selling_model == SellingModel.B2C:
        best = ChannelOptimizer.best_scheme_b2c(product, route, fees, schemes, margin)
    else:
        best = ChannelOptimizer.best_scheme_b2b(product, route, fees, schemes, margin)

    if best is None:
        raise ValueError(f"No feasible scheme found for SKU '{sku}'")

    bd = best.breakdown

    # Fetch route_row for source provenance
    fee_row = (
        (
            await session.execute(
                select(ChannelFeeParams).where(ChannelFeeParams.channel_id == channel_id)
            )
        )
        .scalars()
        .first()
    )
    route_row = None
    if fee_row is not None:
        route_row = (
            (
                await session.execute(
                    select(TradeRouteParams).where(TradeRouteParams.id == fee_row.route_id)
                )
            )
            .scalars()
            .first()
        )

    route_source_op = route_row.source_op if route_row else None
    route_source_ref = route_row.source_ref if route_row else None
    route_observed_at = route_row.observed_at if route_row else None

    # Latest SourceObservation for this SKU + target fields
    obs_rows = (
        (
            await session.execute(
                select(SourceObservation)
                .where(
                    SourceObservation.sku == sku,
                    SourceObservation.target_field.in_(["pe_eur", "catalog_pvp_eur"]),
                )
                .order_by(SourceObservation.observed_at.desc())
                .limit(2)
            )
        )
        .scalars()
        .all()
    )
    obs_by_field: dict[str, SourceObservation] = {o.target_field: o for o in obs_rows}

    now = datetime.now(UTC)

    if field == "cost":
        pe_obs = obs_by_field.get("pe_eur")
        layers = [
            {
                "layer": 1,
                "label": "Compra MT",
                "amount_aed": bd.net_eur,
                "components": [
                    {
                        "key": "net_eur",
                        "value": bd.net_eur,
                        "source_op": pe_obs.source_op if pe_obs else None,
                        "source_ref": pe_obs.source_ref if pe_obs else None,
                        "observed_at": pe_obs.observed_at if pe_obs else None,
                        "is_stale": compute_is_stale(
                            pe_obs.observed_at if pe_obs else None, None, now=now
                        ),
                    }
                ],
            },
            {
                "layer": 2,
                "label": "Ruta ES→Dubai",
                "amount_aed": bd.fx_applied + bd.freight_aed,
                "components": [
                    {
                        "key": "fx_applied",
                        "value": bd.fx_applied,
                        "source_op": route_source_op,
                        "source_ref": route_source_ref,
                        "observed_at": route_observed_at,
                        "is_stale": compute_is_stale(route_observed_at, None, now=now),
                    },
                    {
                        "key": "freight_aed",
                        "value": bd.freight_aed,
                        "source_op": route_source_op,
                        "source_ref": route_source_ref,
                        "observed_at": route_observed_at,
                        "is_stale": compute_is_stale(route_observed_at, None, now=now),
                    },
                ],
            },
            {
                "layer": 3,
                "label": "Importación",
                "amount_aed": bd.landed_aed,
                "components": [
                    {
                        "key": "landed_aed",
                        "value": bd.landed_aed,
                        "source_op": route_source_op,
                        "source_ref": route_source_ref,
                        "observed_at": route_observed_at,
                        "is_stale": compute_is_stale(route_observed_at, None, now=now),
                    }
                ],
            },
            {
                "layer": 4,
                "label": "Logística canal",
                "amount_aed": bd.channel_logistics_aed,
                "components": [
                    {
                        "key": "channel_logistics_aed",
                        "value": bd.channel_logistics_aed,
                        "source_op": route_source_op,
                        "source_ref": route_source_ref,
                        "observed_at": route_observed_at,
                        "is_stale": compute_is_stale(route_observed_at, None, now=now),
                    }
                ],
            },
        ]
        return {
            "sku": sku,
            "field": field,
            "total_aed": bd.cost_op_aed,
            "layers": layers,
        }
    else:
        # ceiling
        pvp_obs = obs_by_field.get("catalog_pvp_eur")
        ceiling_val = best.ceiling_aed
        return {
            "sku": sku,
            "field": field,
            "total_aed": ceiling_val,
            "layers": [
                {
                    "layer": 1,
                    "label": "Techo",
                    "amount_aed": ceiling_val,
                    "components": [
                        {
                            "key": "ceiling_aed",
                            "value": ceiling_val,
                            "source_op": pvp_obs.source_op if pvp_obs else None,
                            "source_ref": pvp_obs.source_ref if pvp_obs else None,
                            "observed_at": pvp_obs.observed_at if pvp_obs else None,
                            "is_stale": compute_is_stale(
                                pvp_obs.observed_at if pvp_obs else None, None, now=now
                            ),
                        }
                    ],
                }
            ],
        }


async def parameter_audit(
    session: AsyncSession,
    channel_id: uuid.UUID,
    channel_code: str,
    key: str,
) -> dict:
    """Resolve (entity_type, entity_id) from key and return audit entries."""
    # Resolve entity_type and entity_id
    if key == "route":
        fee_row = (
            (
                await session.execute(
                    select(ChannelFeeParams).where(ChannelFeeParams.channel_id == channel_id)
                )
            )
            .scalars()
            .first()
        )
        if fee_row is None:
            entity_type = "pricing_param"
            entity_id = str(channel_code)
        else:
            entity_type = "pricing_param"
            entity_id = str(fee_row.route_id)
    elif key == "fees":
        fee_row = (
            (
                await session.execute(
                    select(ChannelFeeParams).where(ChannelFeeParams.channel_id == channel_id)
                )
            )
            .scalars()
            .first()
        )
        entity_type = "pricing_param"
        entity_id = str(fee_row.id) if fee_row else channel_code
    elif key.startswith("margin:"):
        family_id = key[len("margin:") :]
        entity_type = "margin_target"
        entity_id = family_id
    elif key.startswith("override:"):
        sku = key[len("override:") :]
        entity_type = "margin_override"
        entity_id = f"{channel_code}:{sku}"
    elif key in ("optimization", "import", "proposal"):
        entity_type = {
            "optimization": "optimization",
            "import": "catalog_import",
            "proposal": "price_proposal",
        }[key]
        entity_id = channel_code
    else:
        entity_type = "pricing_param"
        entity_id = key

    repo = AuditRepository(session)
    events = await repo.list_for_entity(entity_type, entity_id)

    entries = [
        {
            "actor_id": str(e.actor_id) if e.actor_id else None,
            "action": e.action,
            "before": e.before,
            "after": e.after,
            "reason": e.reason,
            "event_at": e.event_at,
        }
        for e in events
    ]

    return {
        "key": key,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "entries": entries,
    }


async def product_card(
    session: AsyncSession,
    channel_id: uuid.UUID,
    channel_code: str,
    sku: str,
) -> dict:
    """Build product card: master data, price history, listing, proposals."""
    # master
    product = (await session.execute(select(Product).where(Product.sku == sku))).scalars().first()
    if product is None:
        raise ValueError(f"Product '{sku}' not found")

    master = {
        "sku": product.sku,
        "pe_eur": str(product.pe_eur) if product.pe_eur is not None else None,
        "catalog_pvp_eur": (
            str(product.catalog_pvp_eur) if product.catalog_pvp_eur is not None else None
        ),
        "units_per_box": product.units_per_box,
        "weight": str(product.weight) if product.weight is not None else None,
        "hs_code": product.hs_code,
        "family_id": str(product.family_id),
        "updated_at": product.updated_at.isoformat() if product.updated_at else None,
    }

    # price_history from SourceObservation
    obs_rows = (
        (
            await session.execute(
                select(SourceObservation)
                .where(
                    SourceObservation.sku == sku,
                    SourceObservation.target_field.in_(["pe_eur", "catalog_pvp_eur"]),
                )
                .order_by(SourceObservation.observed_at.desc())
                .limit(20)
            )
        )
        .scalars()
        .all()
    )
    price_history = [
        {
            "source_op": o.source_op,
            "target_field": o.target_field,
            "value_numeric": str(o.value_numeric) if o.value_numeric is not None else None,
            "value_text": o.value_text,
            "source_ref": o.source_ref,
            "observed_at": o.observed_at.isoformat(),
        }
        for o in obs_rows
    ]

    # listing from product_marketplace_listings
    listing_row = (
        (
            await session.execute(
                select(MarketplaceListing).where(
                    MarketplaceListing.product_sku == sku,
                    MarketplaceListing.marketplace == channel_code,
                )
            )
        )
        .scalars()
        .first()
    )
    listing = None
    if listing_row is not None:
        listing = {
            "id": listing_row.id,
            "marketplace": listing_row.marketplace,
            "status": listing_row.status,
            "listing_title": listing_row.listing_title,
            "ai_generated_at": (
                listing_row.ai_generated_at.isoformat() if listing_row.ai_generated_at else None
            ),
        }

    # proposals from prices
    price_rows = (
        (
            await session.execute(
                select(Price)
                .where(
                    Price.product_sku == sku,
                    Price.channel_id == channel_id,
                )
                .order_by(Price.created_at.desc())
                .limit(20)
            )
        )
        .scalars()
        .all()
    )
    proposals = [
        {
            "id": str(p.id),
            "scheme_code": p.scheme_code,
            "amount": str(p.amount),
            "status": p.status,
            "proposed_by": str(p.proposed_by) if p.proposed_by else None,
            "created_at": p.created_at.isoformat(),
        }
        for p in price_rows
    ]

    return {
        "sku": sku,
        "master": master,
        "price_history": price_history,
        "listing": listing,
        "proposals": proposals,
    }

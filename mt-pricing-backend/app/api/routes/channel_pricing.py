"""Channel Pricing Engine — configuration and margin endpoints.

Endpoints prefix: /pricing/{channel_code}

- GET  /params                    — route + fee + scheme params
- PATCH /route-params             — update FX, freight, arancel, etc.
- PATCH /fee-params               — update commissions per channel
- GET  /margin-targets            — list family margin targets (with family_name JOIN)
- PUT  /margin-targets            — upsert margin target; clears overrides for family
- PUT  /margin-overrides/{sku}    — upsert per-SKU override
- DELETE /margin-overrides/{sku}  — remove SKU override (revert to family)
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_permissions
from app.db.enums import FulfillmentScheme, SellingModel
from app.services.pricing.engine import PricingEngine
from app.services.pricing.loader import ParameterLoader
from app.services.pricing.optimizer import ChannelOptimizer
from app.db.models.channel_pricing import (
    ChannelFeeParams,
    ChannelMarginOverride,
    ChannelMarginTarget,
    ChannelSchemeParams,
    TradeRouteParams,
)
from app.db.models.channels import Channel
from app.db.models.product import Product
from app.db.models.vocabularies import Family
from app.db.models.user import User
from app.schemas.channel_pricing import (
    ChannelFeeParamsRead,
    ChannelFeeParamsUpdate,
    ChannelSchemeParamsRead,
    MarginOverrideRead,
    MarginOverrideUpsert,
    MarginTargetRead,
    MarginTargetUpsert,
    TradeRouteParamsRead,
    TradeRouteParamsUpdate,
)

router = APIRouter(prefix="/pricing/{channel_code}", tags=["channel-pricing"])


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _resolve_channel_id(
    channel_code: str,
    session: AsyncSession,
) -> uuid.UUID:
    """Resolve channel_code → channel.id. Raises 404 if not found."""
    row = (
        await session.execute(
            select(Channel.id).where(Channel.code == channel_code)
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"Channel '{channel_code}' not found",
        )
    return row


# ---------------------------------------------------------------------------
# GET /params — read all config for this channel
# ---------------------------------------------------------------------------


@router.get(
    "/params",
    summary="Channel pricing config (route + fees + schemes)",
    operation_id="channelPricingGetParams",
)
async def get_params(
    channel_code: str,
    _user: Annotated[User, Depends(require_permissions("prices:read"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict:
    """Return route + fee + scheme params for this channel."""
    channel_id = await _resolve_channel_id(channel_code, session)

    fee_row = (
        await session.execute(
            select(ChannelFeeParams).where(ChannelFeeParams.channel_id == channel_id)
        )
    ).scalars().first()
    if fee_row is None:
        raise HTTPException(
            404, detail=f"Channel '{channel_code}' has no fee params configured"
        )

    route_row = (
        await session.execute(
            select(TradeRouteParams).where(TradeRouteParams.id == fee_row.route_id)
        )
    ).scalars().first()
    if route_row is None:
        raise HTTPException(
            500, detail="Trade route params missing — data integrity issue"
        )

    scheme_rows = (
        await session.execute(
            select(ChannelSchemeParams).where(
                ChannelSchemeParams.channel_id == channel_id
            )
        )
    ).scalars().all()

    total_fees_pct = float(
        fee_row.commission_pct
        + fee_row.vat_pct
        + fee_row.advertising_pct
        + fee_row.returns_pct
    )

    return {
        "route": TradeRouteParamsRead.model_validate(route_row).model_dump(mode="json"),
        "fees": {
            **ChannelFeeParamsRead.model_validate(fee_row).model_dump(mode="json"),
            "total_fees_pct": total_fees_pct,
        },
        "schemes": [
            ChannelSchemeParamsRead.model_validate(s).model_dump(mode="json")
            for s in scheme_rows
        ],
    }


# ---------------------------------------------------------------------------
# PATCH /route-params — update FX, freight, arancel, etc.
# ---------------------------------------------------------------------------


@router.patch(
    "/route-params",
    response_model=TradeRouteParamsRead,
    summary="Update trade route parameters",
    operation_id="channelPricingPatchRouteParams",
)
async def update_route_params(
    channel_code: str,
    body: TradeRouteParamsUpdate,
    _user: Annotated[User, Depends(require_permissions("prices:propose"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TradeRouteParamsRead:
    """Update trade route parameters (FX, freight, arancel…) for this channel."""
    channel_id = await _resolve_channel_id(channel_code, session)

    fee_row = (
        await session.execute(
            select(ChannelFeeParams).where(ChannelFeeParams.channel_id == channel_id)
        )
    ).scalars().first()
    if fee_row is None:
        raise HTTPException(
            404, detail=f"Channel '{channel_code}' has no fee params configured"
        )

    values = body.model_dump(exclude_unset=True)
    if values:
        await session.execute(
            update(TradeRouteParams)
            .where(TradeRouteParams.id == fee_row.route_id)
            .values(**values)
        )
        await session.commit()

    route = (
        await session.execute(
            select(TradeRouteParams).where(TradeRouteParams.id == fee_row.route_id)
        )
    ).scalars().first()
    return TradeRouteParamsRead.model_validate(route)


# ---------------------------------------------------------------------------
# PATCH /fee-params — update commissions per channel
# ---------------------------------------------------------------------------


@router.patch(
    "/fee-params",
    response_model=ChannelFeeParamsRead,
    summary="Update channel fee parameters",
    operation_id="channelPricingPatchFeeParams",
)
async def update_fee_params(
    channel_code: str,
    body: ChannelFeeParamsUpdate,
    _user: Annotated[User, Depends(require_permissions("prices:propose"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ChannelFeeParamsRead:
    """Update channel-specific fee parameters (commission, VAT, advertising, returns…)."""
    channel_id = await _resolve_channel_id(channel_code, session)

    values = body.model_dump(exclude_unset=True)
    if values:
        await session.execute(
            update(ChannelFeeParams)
            .where(ChannelFeeParams.channel_id == channel_id)
            .values(**values)
        )
        await session.commit()

    row = (
        await session.execute(
            select(ChannelFeeParams).where(ChannelFeeParams.channel_id == channel_id)
        )
    ).scalars().first()
    if row is None:
        raise HTTPException(404, detail="Channel fee params not configured")
    return ChannelFeeParamsRead.model_validate(row)


# ---------------------------------------------------------------------------
# GET /margin-targets — list with family_name JOIN
# ---------------------------------------------------------------------------


@router.get(
    "/margin-targets",
    response_model=list[MarginTargetRead],
    summary="List margin targets for channel",
    operation_id="channelPricingListMarginTargets",
)
async def list_margin_targets(
    channel_code: str,
    _user: Annotated[User, Depends(require_permissions("prices:read"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[MarginTargetRead]:
    """List margin targets for this channel, with family name joined in."""
    channel_id = await _resolve_channel_id(channel_code, session)

    rows = (
        await session.execute(
            select(ChannelMarginTarget, Family.name)
            .join(Family, Family.id == ChannelMarginTarget.family_id)
            .where(ChannelMarginTarget.channel_id == channel_id)
            .order_by(Family.name)
        )
    ).all()

    return [
        MarginTargetRead(
            id=r.ChannelMarginTarget.id,
            channel_id=r.ChannelMarginTarget.channel_id,
            family_id=r.ChannelMarginTarget.family_id,
            family_name=r.name,
            selling_model=SellingModel(r.ChannelMarginTarget.selling_model),
            margin_target_pct=r.ChannelMarginTarget.margin_target_pct,
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# PUT /margin-targets — upsert + clear overrides for family
# ---------------------------------------------------------------------------


@router.put(
    "/margin-targets",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Upsert margin target (clears overrides for family)",
    operation_id="channelPricingUpsertMarginTarget",
)
async def upsert_margin_target(
    channel_code: str,
    body: MarginTargetUpsert,
    _user: Annotated[User, Depends(require_permissions("prices:propose"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    """Upsert margin target. Clears all overrides for this family+selling_model."""
    channel_id = await _resolve_channel_id(channel_code, session)

    await session.execute(
        pg_insert(ChannelMarginTarget)
        .values(
            channel_id=channel_id,
            family_id=body.family_id,
            selling_model=body.selling_model.value,
            margin_target_pct=body.margin_target_pct,
        )
        .on_conflict_do_update(
            constraint="uq_channel_margin_targets",
            set_={"margin_target_pct": body.margin_target_pct},
        )
    )
    # Clear overrides for products in this family (Pricing Desk behavior)
    await session.execute(
        delete(ChannelMarginOverride).where(
            ChannelMarginOverride.channel_id == channel_id,
            ChannelMarginOverride.selling_model == body.selling_model.value,
            ChannelMarginOverride.product_sku.in_(
                select(Product.sku).where(Product.family_id == body.family_id)
            ),
        )
    )
    await session.commit()


# ---------------------------------------------------------------------------
# PUT /margin-overrides/{sku} — upsert per-SKU override
# ---------------------------------------------------------------------------


@router.put(
    "/margin-overrides/{sku}",
    response_model=MarginOverrideRead,
    summary="Upsert per-SKU margin override",
    operation_id="channelPricingUpsertMarginOverride",
)
async def upsert_margin_override(
    channel_code: str,
    sku: str,
    body: MarginOverrideUpsert,
    _user: Annotated[User, Depends(require_permissions("prices:propose"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> MarginOverrideRead:
    """Upsert per-SKU margin override."""
    channel_id = await _resolve_channel_id(channel_code, session)

    await session.execute(
        pg_insert(ChannelMarginOverride)
        .values(
            product_sku=sku,
            channel_id=channel_id,
            selling_model=body.selling_model.value,
            margin_override_pct=body.margin_override_pct,
            reason=body.reason,
        )
        .on_conflict_do_update(
            constraint="uq_channel_margin_overrides",
            set_={
                "margin_override_pct": body.margin_override_pct,
                "reason": body.reason,
            },
        )
    )
    await session.commit()

    row = (
        await session.execute(
            select(ChannelMarginOverride).where(
                ChannelMarginOverride.product_sku == sku,
                ChannelMarginOverride.channel_id == channel_id,
                ChannelMarginOverride.selling_model == body.selling_model.value,
            )
        )
    ).scalars().first()
    return MarginOverrideRead.model_validate(row)


# ---------------------------------------------------------------------------
# DELETE /margin-overrides/{sku} — remove SKU override
# ---------------------------------------------------------------------------


@router.delete(
    "/margin-overrides/{sku}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove per-SKU margin override",
    operation_id="channelPricingDeleteMarginOverride",
)
async def delete_margin_override(
    channel_code: str,
    sku: str,
    _user: Annotated[User, Depends(require_permissions("prices:propose"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    selling_model: SellingModel = Query(default=SellingModel.B2C),
) -> None:
    """Remove a SKU override — product reverts to family margin target."""
    channel_id = await _resolve_channel_id(channel_code, session)

    await session.execute(
        delete(ChannelMarginOverride).where(
            ChannelMarginOverride.product_sku == sku,
            ChannelMarginOverride.channel_id == channel_id,
            ChannelMarginOverride.selling_model == selling_model.value,
        )
    )
    await session.commit()


# ---------------------------------------------------------------------------
# Calculation helpers
# ---------------------------------------------------------------------------


def _price_result_to_dict(r) -> dict:
    """Serialize PriceResult to JSON-friendly dict. Infinity → None."""
    inf = Decimal("Infinity")
    return {
        "sku": r.sku,
        "selling_model": r.selling_model.value,
        "fulfillment_scheme": r.fulfillment_scheme.value,
        "scheme_label": r.scheme_label,
        "margin_pct": float(r.margin_pct),
        "cost_op_aed": float(r.cost_op_aed),
        "selling_price_aed": (
            float(r.selling_price_aed) if r.selling_price_aed != inf else None
        ),
        "ceiling_aed": (
            float(r.ceiling_aed)
            if r.ceiling_aed not in (inf, Decimal("0"))
            else None
        ),
        "benefit_per_unit_aed": float(r.benefit_per_unit_aed),
        "roi_pct": float(r.roi_pct),
        "margin_to_ceiling_pct": float(r.margin_to_ceiling_pct),
        "is_publishable": r.is_publishable,
        "signal": r.signal,
    }


# ---------------------------------------------------------------------------
# GET /product/{sku} — single-SKU price calculation
# ---------------------------------------------------------------------------


@router.get(
    "/product/{sku}",
    operation_id="getProductPrice",
    dependencies=[Depends(require_permissions("prices:read"))],
)
async def get_product_price(
    channel_code: str,
    sku: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    selling_model: SellingModel = Query(default=SellingModel.B2C),
    margin_pct: Optional[float] = None,
) -> dict:
    """Calculate price for one SKU across all schemes + best."""
    channel_id = await _resolve_channel_id(channel_code, session)
    loader = ParameterLoader(session)
    route, fees, schemes = await loader.load_route_and_fees(channel_id)
    products = await loader.load_product_data(channel_id, skus=[sku])
    if not products:
        raise HTTPException(
            status_code=404,
            detail=f"SKU '{sku}' not found or has no logistics data",
        )

    product = products[0]
    effective_margins = await loader.load_effective_margins(
        channel_id, selling_model, [sku]
    )
    m = (
        Decimal(str(margin_pct))
        if margin_pct is not None
        else effective_margins.get(sku, Decimal("12"))
    )

    compute = (
        PricingEngine.compute_b2c
        if selling_model == SellingModel.B2C
        else PricingEngine.compute_b2b
    )
    results = [compute(product, route, fees, s, m) for s in schemes if s.is_available]

    if selling_model == SellingModel.B2C:
        best = ChannelOptimizer.best_scheme_b2c(product, route, fees, schemes, m)
    else:
        best = ChannelOptimizer.best_scheme_b2b(product, route, fees, schemes, m)

    return {
        "sku": sku,
        "effective_margin_pct": float(m),
        "best_scheme": _price_result_to_dict(best) if best else None,
        "all_schemes": [_price_result_to_dict(r) for r in results],
    }


# ---------------------------------------------------------------------------
# GET /catalog — full catalog summary with semáforo + filters
# ---------------------------------------------------------------------------


@router.get(
    "/catalog",
    operation_id="getCatalogSummary",
    dependencies=[Depends(require_permissions("prices:read"))],
)
async def get_catalog_summary(
    channel_code: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    selling_model: SellingModel = Query(default=SellingModel.B2C),
    family_id: Optional[str] = None,
    signal: Optional[str] = None,
) -> dict:
    """Return price analysis for the full catalog with semáforo summary."""
    channel_id = await _resolve_channel_id(channel_code, session)
    loader = ParameterLoader(session)
    route, fees, schemes = await loader.load_route_and_fees(channel_id)
    products = await loader.load_product_data(channel_id)

    if family_id:
        products = [p for p in products if p.family_id == family_id]

    skus = [p.sku for p in products]
    margins = await loader.load_effective_margins(channel_id, selling_model, skus)

    if selling_model == SellingModel.B2C:
        results = ChannelOptimizer.optimize_catalog_b2c(
            products, route, fees, schemes, margins
        )
    else:
        results = ChannelOptimizer.optimize_catalog_b2b(
            products, route, fees, schemes, margins
        )

    if signal:
        results = [r for r in results if r.signal == signal.upper()]

    rows = [_price_result_to_dict(r) for r in results]
    publishable = sum(1 for r in results if r.is_publishable)
    in_loss = sum(1 for r in results if r.signal == "PÉRDIDA")

    return {
        "semaforo": {
            "total": len(results),
            "publishable": publishable,
            "blocked": len(results) - publishable,
            "in_loss": in_loss,
            "by_scheme": {
                scheme.value: sum(
                    1 for r in results if r.fulfillment_scheme == scheme
                )
                for scheme in FulfillmentScheme
            },
        },
        "rows": rows,
    }


# ---------------------------------------------------------------------------
# POST /optimize — optimization preview (does NOT persist)
# ---------------------------------------------------------------------------


@router.post(
    "/optimize",
    operation_id="optimizeCatalog",
    dependencies=[Depends(require_permissions("prices:read"))],
)
async def optimize_catalog(
    channel_code: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    selling_model: SellingModel = Query(default=SellingModel.B2C),
) -> dict:
    """Preview the best scheme+margin per product. Does NOT persist.

    PERFORMANCE: CPU-bound. For catalogs >50 SKUs, consider a Celery task.
    """
    channel_id = await _resolve_channel_id(channel_code, session)
    loader = ParameterLoader(session)
    route, fees, schemes = await loader.load_route_and_fees(channel_id)
    products = await loader.load_product_data(channel_id)

    if selling_model == SellingModel.B2C:
        results = ChannelOptimizer.full_optimize_catalog_b2c(
            products, route, fees, schemes
        )
    else:
        results = ChannelOptimizer.full_optimize_catalog_b2b(
            products, route, fees, schemes
        )

    return {"results": [_price_result_to_dict(r) for r in results]}


# ---------------------------------------------------------------------------
# POST /optimize/apply — persist optimization as overrides
# ---------------------------------------------------------------------------


@router.post(
    "/optimize/apply",
    operation_id="applyOptimization",
    dependencies=[Depends(require_permissions("prices:propose"))],
    status_code=status.HTTP_204_NO_CONTENT,
)
async def apply_optimization(
    channel_code: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    selling_model: SellingModel = Query(default=SellingModel.B2C),
) -> None:
    """Persist optimization result as per-SKU margin overrides."""
    channel_id = await _resolve_channel_id(channel_code, session)
    loader = ParameterLoader(session)
    route, fees, schemes = await loader.load_route_and_fees(channel_id)
    products = await loader.load_product_data(channel_id)

    if selling_model == SellingModel.B2C:
        results = ChannelOptimizer.full_optimize_catalog_b2c(
            products, route, fees, schemes
        )
    else:
        results = ChannelOptimizer.full_optimize_catalog_b2b(
            products, route, fees, schemes
        )

    for r in results:
        await session.execute(
            pg_insert(ChannelMarginOverride)
            .values(
                product_sku=r.sku,
                channel_id=channel_id,
                selling_model=selling_model.value,
                margin_override_pct=r.margin_pct,
                reason="auto-optimized",
            )
            .on_conflict_do_update(
                constraint="uq_channel_margin_overrides",
                set_={
                    "margin_override_pct": r.margin_pct,
                    "reason": "auto-optimized",
                },
            )
        )
    await session.commit()


__all__ = ["router"]

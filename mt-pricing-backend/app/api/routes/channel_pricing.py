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
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_permissions
from app.db.enums import SellingModel
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
    _user: Annotated[User, Depends(require_permissions("prices:propose"))],
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
        raise HTTPException(404, detail="Channel fee params not configured")

    route_row = (
        await session.execute(
            select(TradeRouteParams).where(TradeRouteParams.id == fee_row.route_id)
        )
    ).scalars().first()

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
        raise HTTPException(404, detail="Channel not configured")

    values = {k: v for k, v in body.model_dump().items() if v is not None}
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

    values = {k: v for k, v in body.model_dump().items() if v is not None}
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
    _user: Annotated[User, Depends(require_permissions("prices:propose"))],
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
    selling_model: str = Query(default="b2c"),
) -> None:
    """Remove a SKU override — product reverts to family margin target."""
    channel_id = await _resolve_channel_id(channel_code, session)

    await session.execute(
        delete(ChannelMarginOverride).where(
            ChannelMarginOverride.product_sku == sku,
            ChannelMarginOverride.channel_id == channel_id,
            ChannelMarginOverride.selling_model == selling_model,
        )
    )
    await session.commit()


__all__ = ["router"]

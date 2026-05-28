"""ParameterLoader — loads all pricing params in one JOIN per request."""
from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.db.enums import CeilingBasis, FulfillmentScheme, SellingModel
from app.db.models.channel_pricing import (
    ChannelFeeParams,
    ChannelMarginOverride,
    ChannelMarginTarget,
    ChannelProductLogistics,
    ChannelSchemeParams,
    TradeRouteParams,
)
from app.db.models.product import Product
from app.services.pricing.schemas import (
    ChannelFees,
    ProductLogistics,
    ProductPricingData,
    RouteParams,
    SchemeConfig,
)


class ParameterLoader:
    """Loads all pricing parameters for a channel in one pass."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def load_route_and_fees(
        self, channel_id: uuid.UUID
    ) -> tuple[RouteParams, ChannelFees, list[SchemeConfig]]:
        """Load trade route + channel fees + available schemes for a channel."""
        fee_row = (
            await self._session.execute(
                select(ChannelFeeParams)
                .where(ChannelFeeParams.channel_id == channel_id)
                .options(joinedload(ChannelFeeParams.route))
            )
        ).scalars().first()

        if fee_row is None:
            raise ValueError(
                f"No channel_fee_params found for channel_id={channel_id}. "
                "Run seed_channel_pricing.py first."
            )

        route_row: TradeRouteParams = fee_row.route

        route = RouteParams(
            fx_rate=route_row.fx_rate,
            fx_buffer_pct=route_row.fx_buffer_pct,
            freight_rate_per_kg=route_row.freight_rate_per_kg,
            freight_min_aed=route_row.freight_min_aed,
            import_tariff_pct=route_row.import_tariff_pct,
            local_warehouse_pct=route_row.local_warehouse_pct,
            handling_pct=route_row.handling_pct,
        )
        fees = ChannelFees(
            mt_discount_pct=fee_row.mt_discount_pct,
            commission_pct=fee_row.commission_pct,
            vat_pct=fee_row.vat_pct,
            advertising_pct=fee_row.advertising_pct,
            returns_pct=fee_row.returns_pct,
            storage_multiplier=fee_row.storage_multiplier,
        )

        scheme_rows = (
            await self._session.execute(
                select(ChannelSchemeParams).where(
                    ChannelSchemeParams.channel_id == channel_id,
                    ChannelSchemeParams.is_available.is_(True),
                )
            )
        ).scalars().all()

        schemes = [
            SchemeConfig(
                fulfillment_scheme=FulfillmentScheme(s.fulfillment_scheme),
                scheme_label=s.scheme_label,
                is_available=s.is_available,
                flat_supplement_aed=s.flat_supplement_aed,
                pct_surcharge=s.pct_surcharge,
                max_weight_kg=s.max_weight_kg,
            )
            for s in scheme_rows
        ]
        return route, fees, schemes

    async def load_product_data(
        self,
        channel_id: uuid.UUID,
        skus: Optional[list[str]] = None,
    ) -> list[ProductPricingData]:
        """Load active products with their channel logistics.

        Only includes products with lifecycle_status='active' that have
        both pe_eur and catalog_pvp_eur populated.
        """
        q = (
            select(Product, ChannelProductLogistics)
            .join(
                ChannelProductLogistics,
                (ChannelProductLogistics.product_sku == Product.sku)
                & (ChannelProductLogistics.channel_id == channel_id),
                isouter=True,
            )
            .where(Product.active)
        )
        if skus:
            q = q.where(Product.sku.in_(skus))

        rows = (await self._session.execute(q)).all()

        result = []
        for product, logistics_row in rows:
            if (
                logistics_row is None
                or product.pe_eur is None
                or product.catalog_pvp_eur is None
            ):
                continue

            logistics = ProductLogistics(
                inbound_fee_aed=logistics_row.inbound_fee_aed,
                storage_fee_aed=logistics_row.storage_fee_aed,
                fulfillment_fee_aed=logistics_row.fulfillment_fee_aed,
                default_scheme=FulfillmentScheme(logistics_row.default_scheme),
            )

            # ceiling_basis is stored as a PG enum string — coerce to CeilingBasis
            cb = product.ceiling_basis
            if isinstance(cb, str):
                cb = CeilingBasis(cb)

            result.append(
                ProductPricingData(
                    sku=product.sku,
                    family_id=str(product.family_id),
                    pe_eur=product.pe_eur,
                    catalog_pvp_eur=product.catalog_pvp_eur,
                    units_per_box=product.units_per_box or 1,
                    weight_kg=product.weight or Decimal("0"),
                    b2c_labeling_aed=product.b2c_labeling_aed or Decimal("0"),
                    ceiling_basis=cb,
                    logistics=logistics,
                )
            )
        return result

    async def load_effective_margins(
        self,
        channel_id: uuid.UUID,
        selling_model: SellingModel,
        skus: list[str],
    ) -> dict[str, Decimal]:
        """Return {sku: effective_margin_pct}.

        Priority: SKU override > family target > default 12%.
        """
        target_rows = (
            await self._session.execute(
                select(ChannelMarginTarget).where(
                    ChannelMarginTarget.channel_id == channel_id,
                    ChannelMarginTarget.selling_model == selling_model.value,
                )
            )
        ).scalars().all()
        family_targets: dict[str, Decimal] = {
            str(r.family_id): r.margin_target_pct for r in target_rows
        }

        override_rows = (
            await self._session.execute(
                select(ChannelMarginOverride).where(
                    ChannelMarginOverride.channel_id == channel_id,
                    ChannelMarginOverride.selling_model == selling_model.value,
                    ChannelMarginOverride.product_sku.in_(skus) if skus else True,
                )
            )
        ).scalars().all()
        overrides: dict[str, Decimal] = {
            r.product_sku: r.margin_override_pct for r in override_rows
        }

        # Note: SKUs that don't exist in products table are omitted from the result.
        product_rows = (
            await self._session.execute(
                select(Product.sku, Product.family_id).where(Product.sku.in_(skus))
            )
        ).all() if skus else []

        result: dict[str, Decimal] = {}
        for sku, family_id in product_rows:
            if sku in overrides:
                result[sku] = overrides[sku]
            elif str(family_id) in family_targets:
                result[sku] = family_targets[str(family_id)]
            else:
                result[sku] = Decimal("12")
        return result

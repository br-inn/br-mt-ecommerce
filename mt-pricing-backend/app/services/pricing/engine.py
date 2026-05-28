# app/services/pricing/engine.py
"""PricingEngine — pure function, no I/O.

All inputs arrive as frozen dataclasses. All outputs are PriceResult.
No database access, no side effects, fully unit-testable.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from app.db.enums import CeilingBasis, FulfillmentScheme, SellingModel
from app.services.pricing.schemas import (
    ChannelFees,
    CostBreakdown,
    PriceResult,
    ProductLogistics,
    ProductPricingData,
    RouteParams,
    SchemeConfig,
)


class PricingEngine:
    """Static methods only — instantiation not needed."""

    @staticmethod
    def compute_b2c(
        product: ProductPricingData,
        route: RouteParams,
        fees: ChannelFees,
        scheme: SchemeConfig,
        margin_pct: Decimal,
    ) -> PriceResult:
        """Calculate selling price for one unit on a B2C marketplace channel."""
        # Weight limit check (e.g. FBA: no products > 25 kg)
        if scheme.max_weight_kg is not None and product.weight_kg > scheme.max_weight_kg:
            cost_op = PricingEngine._landed_b2c(product, route, fees)
            return PriceResult.infeasible(
                product.sku, SellingModel.B2C, scheme, cost_op, margin_pct
            )

        landed = PricingEngine._landed_b2c(product, route, fees)
        freight = PricingEngine._freight_per_unit(product, route)
        labeling = product.b2c_labeling_aed
        channel_logistics = PricingEngine._logistics_cost(product.logistics, scheme, fees)
        cost_op = landed + labeling + channel_logistics

        return PricingEngine._build_result(
            sku=product.sku,
            selling_model=SellingModel.B2C,
            scheme=scheme,
            margin_pct=margin_pct,
            cost_op=cost_op,
            fees=fees,
            ceiling=PricingEngine._ceiling_b2c(product, route),
            breakdown=CostBreakdown(
                net_eur=product.pe_eur * (1 - fees.mt_discount_pct / 100),
                fx_applied=route.fx_rate * (1 + route.fx_buffer_pct / 100),
                aed_before_freight=product.pe_eur
                * (1 - fees.mt_discount_pct / 100)
                * route.fx_rate
                * (1 + route.fx_buffer_pct / 100),
                freight_aed=freight,
                landed_aed=landed,
                labeling_aed=labeling,
                channel_logistics_aed=channel_logistics,
                cost_op_aed=cost_op,
                fees_frac=fees.total_fees_frac,
                scheme=scheme.scheme_label,
            ),
        )

    @staticmethod
    def compute_b2b(
        product: ProductPricingData,
        route: RouteParams,
        fees: ChannelFees,
        scheme: SchemeConfig,
        margin_pct: Decimal,
    ) -> PriceResult:
        """Calculate selling price for one box on a B2B channel."""
        n = Decimal(str(product.units_per_box))
        landed = PricingEngine._landed_b2b(product, route, fees)
        freight = PricingEngine._freight_per_box(product, route)
        # B2B: no per-unit labeling cost — MT ships in original boxes
        channel_logistics = PricingEngine._logistics_cost(product.logistics, scheme, fees) * n
        cost_op = landed + channel_logistics

        return PricingEngine._build_result(
            sku=product.sku,
            selling_model=SellingModel.B2B,
            scheme=scheme,
            margin_pct=margin_pct,
            cost_op=cost_op,
            fees=fees,
            ceiling=PricingEngine._ceiling_b2b(product, route),
            breakdown=CostBreakdown(
                net_eur=product.pe_eur * n * (1 - fees.mt_discount_pct / 100),
                fx_applied=route.fx_rate * (1 + route.fx_buffer_pct / 100),
                aed_before_freight=product.pe_eur
                * n
                * (1 - fees.mt_discount_pct / 100)
                * route.fx_rate
                * (1 + route.fx_buffer_pct / 100),
                freight_aed=freight,
                landed_aed=landed,
                labeling_aed=Decimal("0"),
                channel_logistics_aed=channel_logistics,
                cost_op_aed=cost_op,
                fees_frac=fees.total_fees_frac,
                scheme=scheme.scheme_label,
            ),
        )

    # ── Private helpers ────────────────────────────────────────────────

    @staticmethod
    def _freight_per_unit(product: ProductPricingData, route: RouteParams) -> Decimal:
        """Freight cost per unit in AED. Splits shipment minimum across box units."""
        units = max(product.units_per_box, 1)
        per_kg = route.freight_rate_per_kg * product.weight_kg * route.fx_rate
        per_min = route.freight_min_aed / Decimal(str(units))
        return max(per_min, per_kg)

    @staticmethod
    def _freight_per_box(product: ProductPricingData, route: RouteParams) -> Decimal:
        """Freight cost per box in AED."""
        n = Decimal(str(product.units_per_box))
        per_kg = route.freight_rate_per_kg * product.weight_kg * n * route.fx_rate
        return max(route.freight_min_aed, per_kg)

    @staticmethod
    def _import_factor(route: RouteParams) -> Decimal:
        return (
            Decimal("1")
            + route.import_tariff_pct / 100
            + route.local_warehouse_pct / 100
            + route.handling_pct / 100
        )

    @staticmethod
    def _landed_b2c(product: ProductPricingData, route: RouteParams, fees: ChannelFees) -> Decimal:
        """Cost of one unit landed in Dubai warehouse (layers 1-3)."""
        net_eur = product.pe_eur * (1 - fees.mt_discount_pct / 100)
        fx = route.fx_rate * (1 + route.fx_buffer_pct / 100)
        aed = net_eur * fx
        freight = PricingEngine._freight_per_unit(product, route)
        return (aed + freight) * PricingEngine._import_factor(route)

    @staticmethod
    def _landed_b2b(product: ProductPricingData, route: RouteParams, fees: ChannelFees) -> Decimal:
        """Cost of one box landed in Dubai warehouse (layers 1-3)."""
        n = Decimal(str(product.units_per_box))
        net_eur_box = product.pe_eur * n * (1 - fees.mt_discount_pct / 100)
        fx = route.fx_rate * (1 + route.fx_buffer_pct / 100)
        aed_box = net_eur_box * fx
        freight = PricingEngine._freight_per_box(product, route)
        return (aed_box + freight) * PricingEngine._import_factor(route)

    @staticmethod
    def _logistics_cost(
        logistics: ProductLogistics,
        scheme: SchemeConfig,
        fees: ChannelFees,
    ) -> Decimal:
        """Channel logistics cost per unit for the given fulfillment scheme."""
        ff = logistics.fulfillment_fee_aed
        if scheme.fulfillment_scheme == FulfillmentScheme.CANAL_FULL:
            return (
                logistics.inbound_fee_aed + logistics.storage_fee_aed * fees.storage_multiplier + ff
            )
        elif scheme.fulfillment_scheme == FulfillmentScheme.CANAL_LASTMILE:
            return ff + scheme.flat_supplement_aed
        else:  # MERCHANT_MANAGED
            return (ff + scheme.flat_supplement_aed) * (1 + scheme.pct_surcharge / 100)

    @staticmethod
    def _ceiling_b2c(product: ProductPricingData, route: RouteParams) -> Decimal:
        if product.ceiling_basis == CeilingBasis.MARGIN_FLOOR:
            # No PVP in MT catalog — optimizer handles this differently
            return Decimal("Infinity")
        pvp_aed = product.catalog_pvp_eur * route.fx_rate
        freight = PricingEngine._freight_per_unit(product, route)
        return (pvp_aed + freight) * PricingEngine._import_factor(route) + product.b2c_labeling_aed

    @staticmethod
    def _ceiling_b2b(product: ProductPricingData, route: RouteParams) -> Decimal:
        if product.ceiling_basis == CeilingBasis.MARGIN_FLOOR:
            return Decimal("Infinity")
        n = Decimal(str(product.units_per_box))
        pvp_aed_box = product.catalog_pvp_eur * n * route.fx_rate
        freight = PricingEngine._freight_per_box(product, route)
        return (pvp_aed_box + freight) * PricingEngine._import_factor(route)

    @staticmethod
    def _signal(margin_pct: Decimal) -> str:
        if margin_pct < 0:
            return "PÉRDIDA"
        if margin_pct < Decimal("5"):
            return "FRÁGIL"
        if margin_pct < Decimal("15"):
            return "FINO"
        if margin_pct <= Decimal("25"):
            return "ÓPTIMO"
        return "EXCELENTE"

    @staticmethod
    def _build_result(
        sku: str,
        selling_model: SellingModel,
        scheme: SchemeConfig,
        margin_pct: Decimal,
        cost_op: Decimal,
        fees: ChannelFees,
        ceiling: Decimal,
        breakdown: CostBreakdown,
    ) -> PriceResult:
        k = Decimal("1") - fees.total_fees_frac - margin_pct / 100
        if k <= Decimal("0"):
            return PriceResult.infeasible(sku, selling_model, scheme, cost_op, margin_pct)

        price = (cost_op / k).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        benefit = price * (Decimal("1") - fees.total_fees_frac) - cost_op
        roi = (benefit / cost_op * 100) if cost_op > 0 else Decimal("0")
        publishable = price <= ceiling if ceiling != Decimal("Infinity") else True
        margin_to_ceil = (
            (ceiling - price) / ceiling * 100
            if ceiling not in (Decimal("0"), Decimal("Infinity"))
            else Decimal("0")
        )

        return PriceResult(
            sku=sku,
            selling_model=selling_model,
            fulfillment_scheme=scheme.fulfillment_scheme,
            scheme_label=scheme.scheme_label,
            margin_pct=margin_pct,
            cost_op_aed=cost_op.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
            selling_price_aed=price,
            ceiling_aed=(
                ceiling.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                if ceiling != Decimal("Infinity")
                else ceiling
            ),
            benefit_per_unit_aed=benefit.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            roi_pct=roi.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP),
            margin_to_ceiling_pct=margin_to_ceil.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP),
            is_publishable=publishable,
            signal=PricingEngine._signal(margin_pct),
            breakdown=breakdown,
        )

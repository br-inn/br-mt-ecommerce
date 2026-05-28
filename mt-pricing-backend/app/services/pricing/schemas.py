# app/services/pricing/schemas.py
"""Immutable dataclasses used by PricingEngine.

These are NOT ORM models — they carry the exact data the engine needs
without touching the database. ParameterLoader builds them from DB rows.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Optional

from app.db.enums import CeilingBasis, FulfillmentScheme, SellingModel


@dataclass(frozen=True)
class RouteParams:
    """Trade route cost parameters (Layer 2 + 3 of cost stack)."""

    fx_rate: Decimal
    fx_buffer_pct: Decimal
    freight_rate_per_kg: Decimal
    freight_min_aed: Decimal
    import_tariff_pct: Decimal
    local_warehouse_pct: Decimal
    handling_pct: Decimal


@dataclass(frozen=True)
class ChannelFees:
    """Channel-level financial parameters (Layer 1 + 5 of cost stack)."""

    mt_discount_pct: Decimal
    commission_pct: Decimal
    vat_pct: Decimal
    advertising_pct: Decimal
    returns_pct: Decimal
    storage_multiplier: Decimal

    @property
    def total_fees_frac(self) -> Decimal:
        """Sum of all marketplace fees as a fraction (0..1)."""
        return (
            self.commission_pct + self.vat_pct + self.advertising_pct + self.returns_pct
        ) / Decimal("100")


@dataclass(frozen=True)
class SchemeConfig:
    """Fulfillment scheme configuration for one (channel, scheme) pair."""

    fulfillment_scheme: FulfillmentScheme
    scheme_label: str
    is_available: bool
    flat_supplement_aed: Decimal
    pct_surcharge: Decimal
    max_weight_kg: Optional[Decimal]


@dataclass(frozen=True)
class ProductLogistics:
    """Per-SKU fulfillment fees for a specific channel (Layer 4)."""

    inbound_fee_aed: Decimal
    storage_fee_aed: Decimal
    fulfillment_fee_aed: Decimal
    default_scheme: FulfillmentScheme


@dataclass(frozen=True)
class ProductPricingData:
    """All product-level data needed for price calculation."""

    sku: str
    family_id: str
    pe_eur: Decimal
    catalog_pvp_eur: Decimal
    units_per_box: int
    weight_kg: Decimal
    b2c_labeling_aed: Decimal
    ceiling_basis: CeilingBasis
    logistics: ProductLogistics

    def __post_init__(self) -> None:
        if self.units_per_box < 1:
            raise ValueError(
                f"units_per_box must be >= 1, got {self.units_per_box} for sku={self.sku}"
            )


@dataclass(frozen=True)
class CostBreakdown:
    """Detailed cost breakdown — stored in prices.breakdown JSONB."""

    net_eur: Decimal
    fx_applied: Decimal
    aed_before_freight: Decimal
    freight_aed: Decimal
    landed_aed: Decimal
    labeling_aed: Decimal
    channel_logistics_aed: Decimal
    cost_op_aed: Decimal
    fees_frac: Decimal
    scheme: str

    def to_dict(self) -> dict[str, str]:
        return {k: str(v) for k, v in self.__dict__.items()}


@dataclass(frozen=True)
class PriceResult:
    """Output of PricingEngine.compute_*. All amounts in AED."""

    sku: str
    selling_model: SellingModel
    fulfillment_scheme: FulfillmentScheme
    scheme_label: str
    margin_pct: Decimal
    cost_op_aed: Decimal
    selling_price_aed: Decimal
    ceiling_aed: Decimal
    benefit_per_unit_aed: Decimal
    roi_pct: Decimal
    margin_to_ceiling_pct: Decimal
    is_publishable: bool
    signal: str
    breakdown: CostBreakdown

    @classmethod
    def infeasible(
        cls,
        sku: str,
        selling_model: SellingModel,
        scheme: SchemeConfig,
        cost_op: Decimal,
        margin_pct: Decimal,
    ) -> "PriceResult":
        zero = Decimal("0")
        return cls(
            sku=sku,
            selling_model=selling_model,
            fulfillment_scheme=scheme.fulfillment_scheme,
            scheme_label=scheme.scheme_label,
            margin_pct=margin_pct,
            cost_op_aed=cost_op,
            selling_price_aed=Decimal("Infinity"),
            ceiling_aed=zero,
            benefit_per_unit_aed=-cost_op,
            roi_pct=Decimal("-100"),
            margin_to_ceiling_pct=Decimal("-100"),
            is_publishable=False,
            signal="PÉRDIDA",
            breakdown=CostBreakdown(
                net_eur=zero,
                fx_applied=zero,
                aed_before_freight=zero,
                freight_aed=zero,
                landed_aed=cost_op,
                labeling_aed=zero,
                channel_logistics_aed=zero,
                cost_op_aed=cost_op,
                fees_frac=zero,
                scheme=scheme.scheme_label,
            ),
        )

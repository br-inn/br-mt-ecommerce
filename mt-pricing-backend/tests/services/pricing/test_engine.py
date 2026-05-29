# tests/services/pricing/test_engine.py
"""Unit tests for PricingEngine — pure function, no DB required."""

from decimal import Decimal

import pytest

from app.db.enums import CeilingBasis, FulfillmentScheme, SellingModel
from app.services.pricing.engine import PricingEngine
from app.services.pricing.schemas import (
    ChannelFees,
    ProductLogistics,
    ProductPricingData,
    RouteParams,
    SchemeConfig,
)


@pytest.fixture
def route() -> RouteParams:
    return RouteParams(
        fx_rate=Decimal("4.28"),
        fx_buffer_pct=Decimal("2"),
        freight_rate_per_kg=Decimal("0"),
        freight_min_aed=Decimal("0"),
        import_tariff_pct=Decimal("4.14"),
        local_warehouse_pct=Decimal("2"),
        handling_pct=Decimal("1.5"),
    )


@pytest.fixture
def fees() -> ChannelFees:
    return ChannelFees(
        mt_discount_pct=Decimal("15"),
        commission_pct=Decimal("11"),
        vat_pct=Decimal("5"),
        advertising_pct=Decimal("8"),
        returns_pct=Decimal("2"),
        storage_multiplier=Decimal("1.0"),
    )


@pytest.fixture
def fba_scheme() -> SchemeConfig:
    return SchemeConfig(
        fulfillment_scheme=FulfillmentScheme.CANAL_FULL,
        scheme_label="FBA",
        is_available=True,
        flat_supplement_aed=Decimal("0"),
        pct_surcharge=Decimal("0"),
        max_weight_kg=Decimal("25"),
    )


@pytest.fixture
def easy_ship_scheme() -> SchemeConfig:
    return SchemeConfig(
        fulfillment_scheme=FulfillmentScheme.CANAL_LASTMILE,
        scheme_label="Easy Ship",
        is_available=True,
        flat_supplement_aed=Decimal("6"),
        pct_surcharge=Decimal("0"),
        max_weight_kg=None,
    )


@pytest.fixture
def self_ship_scheme() -> SchemeConfig:
    return SchemeConfig(
        fulfillment_scheme=FulfillmentScheme.MERCHANT_MANAGED,
        scheme_label="Self-Ship",
        is_available=True,
        flat_supplement_aed=Decimal("0"),
        pct_surcharge=Decimal("15"),
        max_weight_kg=None,
    )


@pytest.fixture
def brass_valve_logistics() -> ProductLogistics:
    return ProductLogistics(
        inbound_fee_aed=Decimal("1.5"),
        storage_fee_aed=Decimal("0.028"),
        fulfillment_fee_aed=Decimal("7.2"),
        default_scheme=FulfillmentScheme.CANAL_FULL,
    )


@pytest.fixture
def brass_valve(brass_valve_logistics) -> ProductPricingData:
    return ProductPricingData(
        sku="4222015",
        family_id="dummy-family-uuid",
        pe_eur=Decimal("3.07"),
        catalog_pvp_eur=Decimal("9.77"),
        units_per_box=1,
        weight_kg=Decimal("0.21"),
        b2c_labeling_aed=Decimal("0"),
        ceiling_basis=CeilingBasis.CATALOG_PVP,
        logistics=brass_valve_logistics,
    )


def test_fees_frac(fees):
    """Total fees fraction = (11+5+8+2)/100 = 0.26."""
    assert fees.total_fees_frac == Decimal("0.26")


def test_compute_b2c_margin_12_fba(brass_valve, route, fees, fba_scheme):
    """Brass valve at 12% margin FBA must be publishable."""
    result = PricingEngine.compute_b2c(brass_valve, route, fees, fba_scheme, Decimal("12"))
    assert result.sku == "4222015"
    assert result.selling_model == SellingModel.B2C
    assert result.fulfillment_scheme == FulfillmentScheme.CANAL_FULL
    assert result.margin_pct == Decimal("12")
    assert result.is_publishable is True
    assert result.signal in ("FINO", "ÓPTIMO", "EXCELENTE", "FRÁGIL")
    assert result.cost_op_aed < result.selling_price_aed <= result.ceiling_aed


def test_compute_b2c_cost_op_breakdown(brass_valve, route, fees, fba_scheme):
    """FBA cost = landed + inbound + storage×multiplier + fulfillment."""
    result = PricingEngine.compute_b2c(brass_valve, route, fees, fba_scheme, Decimal("12"))
    net_eur = Decimal("3.07") * Decimal("0.85")
    fx_adj = Decimal("4.28") * Decimal("1.02")
    aed = net_eur * fx_adj
    landed = aed * (Decimal("1") + Decimal("0.0414") + Decimal("0.02") + Decimal("0.015"))
    channel_logistics = Decimal("1.5") + Decimal("0.028") * Decimal("1.0") + Decimal("7.2")
    expected_cost_op = landed + channel_logistics
    assert abs(result.cost_op_aed - expected_cost_op) < Decimal("0.01")


def test_compute_b2c_easy_ship_higher_cost(brass_valve, route, fees, fba_scheme, easy_ship_scheme):
    """Easy Ship cost > FBA cost for this small product."""
    r_fba = PricingEngine.compute_b2c(brass_valve, route, fees, fba_scheme, Decimal("12"))
    r_es = PricingEngine.compute_b2c(brass_valve, route, fees, easy_ship_scheme, Decimal("12"))
    assert r_es.cost_op_aed > r_fba.cost_op_aed


def test_compute_b2c_negative_margin_signal(brass_valve, route, fees, fba_scheme):
    result = PricingEngine.compute_b2c(brass_valve, route, fees, fba_scheme, Decimal("-5"))
    assert result.signal == "PÉRDIDA"


def test_compute_b2c_high_margin_signal(brass_valve, route, fees, fba_scheme):
    result = PricingEngine.compute_b2c(brass_valve, route, fees, fba_scheme, Decimal("30"))
    assert result.signal == "EXCELENTE"


def test_compute_b2c_infeasible_when_fees_exceed_100(brass_valve, route, fba_scheme):
    """margin=80 with high fees makes (1 - fees - margin) <= 0."""
    very_high_fees = ChannelFees(
        mt_discount_pct=Decimal("15"),
        commission_pct=Decimal("50"),
        vat_pct=Decimal("5"),
        advertising_pct=Decimal("8"),
        returns_pct=Decimal("2"),
        storage_multiplier=Decimal("1.0"),
    )
    result = PricingEngine.compute_b2c(
        brass_valve, route, very_high_fees, fba_scheme, Decimal("80")
    )
    assert result.is_publishable is False
    assert result.signal == "PÉRDIDA"


def test_compute_b2b_uses_box_quantity(brass_valve, route, fees, fba_scheme):
    """B2B cost is N times B2C single-unit cost (minus labeling)."""
    from dataclasses import replace

    product_box = replace(brass_valve, units_per_box=10)
    result_b2b = PricingEngine.compute_b2b(product_box, route, fees, fba_scheme, Decimal("12"))
    result_b2c = PricingEngine.compute_b2c(brass_valve, route, fees, fba_scheme, Decimal("12"))
    assert result_b2b.cost_op_aed > result_b2c.cost_op_aed
    assert result_b2b.selling_model == SellingModel.B2B


def test_fba_weight_limit_respected(route, fees):
    """Product >25kg returns infeasible for canal_full (FBA weight limit)."""
    heavy_logistics = ProductLogistics(
        inbound_fee_aed=Decimal("5"),
        storage_fee_aed=Decimal("3"),
        fulfillment_fee_aed=Decimal("19.5"),
        default_scheme=FulfillmentScheme.CANAL_FULL,
    )
    heavy_product = ProductPricingData(
        sku="HEAVY001",
        family_id="dummy",
        pe_eur=Decimal("200"),
        catalog_pvp_eur=Decimal("2000"),
        units_per_box=1,
        weight_kg=Decimal("30"),
        b2c_labeling_aed=Decimal("0"),
        ceiling_basis=CeilingBasis.CATALOG_PVP,
        logistics=heavy_logistics,
    )
    fba_scheme = SchemeConfig(
        fulfillment_scheme=FulfillmentScheme.CANAL_FULL,
        scheme_label="FBA",
        is_available=True,
        flat_supplement_aed=Decimal("0"),
        pct_surcharge=Decimal("0"),
        max_weight_kg=Decimal("25"),
    )
    result = PricingEngine.compute_b2c(heavy_product, route, fees, fba_scheme, Decimal("15"))
    assert result.is_publishable is False


def test_ceiling_catalog_pvp(brass_valve, route, fees, fba_scheme):
    """Ceiling ≈ catalog_pvp_eur × fx_rate × (1 + tariff + wh + handling)."""
    result = PricingEngine.compute_b2c(brass_valve, route, fees, fba_scheme, Decimal("0"))
    assert Decimal("40") < result.ceiling_aed < Decimal("50")


def test_ceiling_basis_margin_floor_returns_infinity(brass_valve, route, fees, fba_scheme):
    """Products with MARGIN_FLOOR basis have an infinite ceiling (optimizer handles)."""
    from dataclasses import replace

    product = replace(brass_valve, ceiling_basis=CeilingBasis.MARGIN_FLOOR)
    result = PricingEngine.compute_b2c(product, route, fees, fba_scheme, Decimal("20"))
    assert result.ceiling_aed == Decimal("Infinity")
    assert result.is_publishable is True


def test_product_pricing_data_rejects_zero_units_per_box(brass_valve_logistics):
    """units_per_box < 1 must raise at construction time."""
    with pytest.raises(ValueError, match="units_per_box must be >= 1"):
        ProductPricingData(
            sku="ZERO001",
            family_id="dummy",
            pe_eur=Decimal("1"),
            catalog_pvp_eur=Decimal("10"),
            units_per_box=0,
            weight_kg=Decimal("0.1"),
            b2c_labeling_aed=Decimal("0"),
            ceiling_basis=CeilingBasis.CATALOG_PVP,
            logistics=brass_valve_logistics,
        )


# ── F0: real landed cost override ──────────────────────────────────────────


def test_product_pricing_data_accepts_landed_cost_override(brass_valve_logistics):
    p = ProductPricingData(
        sku="TEST1",
        family_id="fam-1",
        pe_eur=Decimal("10"),
        catalog_pvp_eur=Decimal("40"),
        units_per_box=10,
        weight_kg=Decimal("0.5"),
        b2c_labeling_aed=Decimal("0"),
        ceiling_basis=CeilingBasis.CATALOG_PVP,
        logistics=brass_valve_logistics,
        landed_cost_aed=Decimal("47.5"),
    )
    assert p.landed_cost_aed == Decimal("47.5")


def test_product_pricing_data_landed_cost_defaults_none(brass_valve_logistics):
    p = ProductPricingData(
        sku="TEST2",
        family_id="fam-1",
        pe_eur=Decimal("10"),
        catalog_pvp_eur=Decimal("40"),
        units_per_box=1,
        weight_kg=Decimal("0"),
        b2c_labeling_aed=Decimal("0"),
        ceiling_basis=CeilingBasis.CATALOG_PVP,
        logistics=brass_valve_logistics,
    )
    assert p.landed_cost_aed is None


def _product_with(landed, logistics, **kw):
    base = dict(
        sku="OVR1",
        family_id="fam-1",
        pe_eur=Decimal("10"),
        catalog_pvp_eur=Decimal("40"),
        units_per_box=10,
        weight_kg=Decimal("0.5"),
        b2c_labeling_aed=Decimal("0"),
        ceiling_basis=CeilingBasis.CATALOG_PVP,
        logistics=logistics,
        landed_cost_aed=landed,
    )
    base.update(kw)
    return ProductPricingData(**base)


def test_b2c_uses_landed_override_when_present(route, fees, fba_scheme, brass_valve_logistics):
    product = _product_with(Decimal("47.5"), brass_valve_logistics)
    r = PricingEngine.compute_b2c(product, route, fees, fba_scheme, Decimal("12"))
    expected_logistics = PricingEngine._logistics_cost(brass_valve_logistics, fba_scheme, fees)
    assert r.breakdown.landed_aed == Decimal("47.5")
    assert r.cost_op_aed == (Decimal("47.5") + expected_logistics).quantize(Decimal("0.0001"))


def test_b2b_scales_landed_override_by_units_per_box(
    route, fees, fba_scheme, brass_valve_logistics
):
    product = _product_with(Decimal("47.5"), brass_valve_logistics, units_per_box=10)
    r = PricingEngine.compute_b2b(product, route, fees, fba_scheme, Decimal("12"))
    assert r.breakdown.landed_aed == Decimal("475.0")


def test_landed_override_none_keeps_pe_eur_derivation(
    route, fees, fba_scheme, brass_valve_logistics
):
    """Regression: no override → engine derives landed from pe_eur exactly as before."""
    product = _product_with(None, brass_valve_logistics)
    r = PricingEngine.compute_b2c(product, route, fees, fba_scheme, Decimal("12"))
    expected_landed = PricingEngine._landed_b2c(product, route, fees)
    assert r.breakdown.landed_aed == expected_landed
    assert r.breakdown.landed_aed != Decimal("47.5")

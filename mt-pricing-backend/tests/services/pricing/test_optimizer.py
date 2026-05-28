# tests/services/pricing/test_optimizer.py
from decimal import Decimal
import pytest

from app.db.enums import CeilingBasis, FulfillmentScheme, SellingModel
from app.services.pricing.optimizer import ChannelOptimizer
from app.services.pricing.schemas import (
    ChannelFees, ProductLogistics, ProductPricingData, RouteParams, SchemeConfig,
)


@pytest.fixture
def standard_route():
    return RouteParams(
        fx_rate=Decimal("4.28"), fx_buffer_pct=Decimal("2"),
        freight_rate_per_kg=Decimal("0"), freight_min_aed=Decimal("0"),
        import_tariff_pct=Decimal("4.14"), local_warehouse_pct=Decimal("2"),
        handling_pct=Decimal("1.5"),
    )


@pytest.fixture
def standard_fees():
    return ChannelFees(
        mt_discount_pct=Decimal("15"), commission_pct=Decimal("11"),
        vat_pct=Decimal("5"), advertising_pct=Decimal("8"),
        returns_pct=Decimal("2"), storage_multiplier=Decimal("1.0"),
    )


@pytest.fixture
def all_schemes():
    return [
        SchemeConfig(FulfillmentScheme.CANAL_FULL, "FBA", True, Decimal("0"), Decimal("0"), Decimal("25")),
        SchemeConfig(FulfillmentScheme.CANAL_LASTMILE, "Easy Ship", True, Decimal("6"), Decimal("0"), None),
        SchemeConfig(FulfillmentScheme.MERCHANT_MANAGED, "Self-Ship", True, Decimal("0"), Decimal("15"), None),
    ]


@pytest.fixture
def standard_product():
    return ProductPricingData(
        sku="TEST001", family_id="fam1",
        pe_eur=Decimal("3.07"), catalog_pvp_eur=Decimal("9.77"),
        units_per_box=1, weight_kg=Decimal("0.21"),
        b2c_labeling_aed=Decimal("0"), ceiling_basis=CeilingBasis.CATALOG_PVP,
        logistics=ProductLogistics(
            inbound_fee_aed=Decimal("1.5"), storage_fee_aed=Decimal("0.028"),
            fulfillment_fee_aed=Decimal("7.2"),
            default_scheme=FulfillmentScheme.CANAL_FULL,
        ),
    )


def test_best_scheme_b2c_picks_publishable(standard_product, standard_route, standard_fees, all_schemes):
    """Returns publishable scheme with best benefit."""
    result = ChannelOptimizer.best_scheme_b2c(
        standard_product, standard_route, standard_fees, all_schemes, Decimal("12")
    )
    assert result is not None
    assert result.is_publishable


def test_best_scheme_b2c_returns_none_if_no_schemes(standard_product, standard_route, standard_fees):
    """No schemes → returns None."""
    result = ChannelOptimizer.best_scheme_b2c(
        standard_product, standard_route, standard_fees, [], Decimal("12")
    )
    assert result is None


def test_optimize_catalog_returns_one_result_per_sku(
    standard_product, standard_route, standard_fees, all_schemes
):
    """One result per product in input list."""
    results = ChannelOptimizer.optimize_catalog_b2c(
        [standard_product], standard_route, standard_fees, all_schemes,
        margins={"TEST001": Decimal("12")},
    )
    assert len(results) == 1
    assert results[0].sku == "TEST001"


def test_optimal_margin_finds_highest_publishable(standard_product, standard_route, standard_fees, all_schemes):
    """Finds maximum margin that stays under ceiling."""
    result = ChannelOptimizer.optimal_margin_b2c(
        standard_product, standard_route, standard_fees, all_schemes
    )
    assert result is not None
    assert result.is_publishable
    # margin should be relatively high (the product can support a high margin under ceiling)
    assert result.margin_pct > Decimal("5")


def test_full_optimize_catalog(standard_product, standard_route, standard_fees, all_schemes):
    """Full catalog optimization runs without errors."""
    results = ChannelOptimizer.full_optimize_catalog_b2c(
        [standard_product], standard_route, standard_fees, all_schemes
    )
    assert len(results) == 1
    assert results[0].is_publishable

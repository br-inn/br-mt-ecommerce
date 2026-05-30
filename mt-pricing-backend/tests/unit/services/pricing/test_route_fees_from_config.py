from decimal import Decimal

from app.services.pricing.scenarios import route_fees_from_config


def test_rebuild_route_fees_from_config() -> None:
    cfg = {
        "route": {
            "fx_rate": "3.90",
            "fx_buffer_pct": "2.00",
            "freight_rate_per_kg": "0.05",
            "freight_min_aed": "50.00",
            "import_tariff_pct": "4.14",
            "local_warehouse_pct": "2.00",
            "handling_pct": "1.50",
        },
        "fees": {
            "mt_discount_pct": "15.00",
            "commission_pct": "11.00",
            "vat_pct": "5.00",
            "advertising_pct": "8.00",
            "returns_pct": "2.00",
            "storage_multiplier": "1.0",
        },
    }
    result = route_fees_from_config(cfg)
    assert result is not None
    route, fees = result
    assert route.fx_rate == Decimal("3.90") and route.import_tariff_pct == Decimal("4.14")
    assert fees.commission_pct == Decimal("11.00")


def test_rebuild_returns_none_when_empty() -> None:
    assert route_fees_from_config({"route": {}, "fees": {}}) is None

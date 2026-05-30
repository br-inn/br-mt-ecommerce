from decimal import Decimal

from app.services.procurement.cost_builder import build_actual_breakdown


def test_breakdown_sums_commercial_plus_duty():
    bd = build_actual_breakdown(
        commercial_eur=Decimal("34.804"),
        import_value_eur=Decimal("30.0"),
        tariff_pct=Decimal("5"),
    )
    assert bd == {"commercial_eur": "34.804", "import_duty_eur": "1.5000"}


def test_breakdown_has_only_summable_keys():
    bd = build_actual_breakdown(Decimal("10"), Decimal("10"), Decimal("5"))
    assert set(bd.keys()) == {"commercial_eur", "import_duty_eur"}

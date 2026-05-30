from decimal import Decimal

from app.core.config import get_settings


def test_drift_settings_defaults() -> None:
    s = get_settings()
    assert s.DRIFT_MIN_SKUS == 1
    assert s.FX_DRIFT_PCT == Decimal("0.5")
    assert s.COMMISSION_DRIFT_PP == Decimal("1.0")
    assert s.TARIFF_DRIFT_PP == Decimal("1.0")
    assert "1" in s.AUTO_OPTIMIZE_CHECK_CRON

from decimal import Decimal

from app.core.config import get_settings


def test_fx_settings_defaults() -> None:
    s = get_settings()
    assert s.FX_USD_AED_PEG == Decimal("3.6725")
    assert "ecb.europa.eu" in s.ECB_FX_URL
    assert s.AUTO_SNAPSHOT_RETENTION_DAYS == 90

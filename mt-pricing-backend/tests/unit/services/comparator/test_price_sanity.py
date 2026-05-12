"""Tests unitarios para PriceSanityCheckService (US-F15-02-04).

AC#6 verificados:
- test_price_normal_passes     — precio en rango → reason="ok"
- test_price_too_low_rejected  — precio < 30% P10 → reason="price_too_low", passed=False
- test_price_too_high_rejected — precio > 300% P90 → reason="price_too_high", passed=False
- test_no_calibration_skips    — sin rango → reason="skipped", passed=True

Mock AsyncSession para no requerir DB real.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.comparator.price_sanity import PriceSanityCheckService

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session(calibration_obj):
    """Construye un AsyncSession mock que devuelve ``calibration_obj`` como scalar."""
    session = AsyncMock()
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = calibration_obj
    session.execute.return_value = execute_result
    return session


def _make_calibration(p10: str, p90: str):
    """Crea un objeto PriceCalibrationRange mock con los valores dados."""
    cal = MagicMock()
    cal.expected_min_p10 = Decimal(p10)
    cal.expected_max_p90 = Decimal(p90)
    return cal


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_price_normal_passes() -> None:
    """Precio dentro del rango P10/P90 (sin multiplicadores) → reason='ok'."""
    # P10=100, P90=1000 → low_threshold=30, high_threshold=3000
    # candidate=500 → ok
    calibration = _make_calibration("100.0000", "1000.0000")
    session = _make_session(calibration)

    service = PriceSanityCheckService()
    result = await service.check(
        session=session,
        candidate_price=Decimal("500.00"),
        category_id="electronics",
        currency="AED",
    )

    assert result.passed is True
    assert result.reason == "ok"
    assert result.price_too_low is False
    assert result.price_too_high is False
    assert result.sanity_check_skipped is False


@pytest.mark.asyncio
async def test_price_too_low_rejected() -> None:
    """Precio por debajo del 30% de P10 → reason='price_too_low', passed=False."""
    # P10=100 → low_threshold=30; candidate=25 (< 30) → rejected
    calibration = _make_calibration("100.0000", "1000.0000")
    session = _make_session(calibration)

    service = PriceSanityCheckService()

    with patch(
        "app.services.comparator.price_sanity.price_sanity_rejections_total"
    ) as mock_counter:
        mock_counter.labels.return_value = MagicMock()
        result = await service.check(
            session=session,
            candidate_price=Decimal("25.00"),
            category_id="electronics",
            currency="AED",
        )

    assert result.passed is False
    assert result.reason == "price_too_low"
    assert result.price_too_low is True
    assert result.price_too_high is False
    assert result.sanity_check_skipped is False
    mock_counter.labels.assert_called_once_with(reason="price_too_low")
    mock_counter.labels.return_value.inc.assert_called_once()


@pytest.mark.asyncio
async def test_price_too_high_rejected() -> None:
    """Precio por encima del 300% de P90 → reason='price_too_high', passed=False."""
    # P90=1000 → high_threshold=3000; candidate=5000 (> 3000) → rejected
    calibration = _make_calibration("100.0000", "1000.0000")
    session = _make_session(calibration)

    service = PriceSanityCheckService()

    with patch(
        "app.services.comparator.price_sanity.price_sanity_rejections_total"
    ) as mock_counter:
        mock_counter.labels.return_value = MagicMock()
        result = await service.check(
            session=session,
            candidate_price=Decimal("5000.00"),
            category_id="electronics",
            currency="AED",
        )

    assert result.passed is False
    assert result.reason == "price_too_high"
    assert result.price_too_high is True
    assert result.price_too_low is False
    assert result.sanity_check_skipped is False
    mock_counter.labels.assert_called_once_with(reason="price_too_high")
    mock_counter.labels.return_value.inc.assert_called_once()


@pytest.mark.asyncio
async def test_no_calibration_skips() -> None:
    """Sin rango calibrado para la categoría → reason='skipped', passed=True."""
    session = _make_session(None)

    service = PriceSanityCheckService()
    result = await service.check(
        session=session,
        candidate_price=Decimal("999.00"),
        category_id="unknown_category",
        currency="AED",
    )

    assert result.passed is True
    assert result.reason == "skipped"
    assert result.sanity_check_skipped is True
    assert result.price_too_low is False
    assert result.price_too_high is False


@pytest.mark.asyncio
async def test_price_at_exact_low_boundary_passes() -> None:
    """Precio exactamente en el límite inferior (30% de P10) → ok (no rechazado)."""
    # P10=100 → low_threshold=30; candidate=30 (== 30) → ok (< no se cumple)
    calibration = _make_calibration("100.0000", "1000.0000")
    session = _make_session(calibration)

    service = PriceSanityCheckService()
    result = await service.check(
        session=session,
        candidate_price=Decimal("30.00"),
        category_id="electronics",
        currency="AED",
    )

    assert result.passed is True
    assert result.reason == "ok"


@pytest.mark.asyncio
async def test_price_at_exact_high_boundary_passes() -> None:
    """Precio exactamente en el límite superior (300% de P90) → ok (no rechazado)."""
    # P90=1000 → high_threshold=3000; candidate=3000 (== 3000) → ok (> no se cumple)
    calibration = _make_calibration("100.0000", "1000.0000")
    session = _make_session(calibration)

    service = PriceSanityCheckService()
    result = await service.check(
        session=session,
        candidate_price=Decimal("3000.00"),
        category_id="electronics",
        currency="AED",
    )

    assert result.passed is True
    assert result.reason == "ok"

"""Unit tests `app.services.costs.cost_service` — sin DB.

Cobertura de la lógica que NO requiere triggers ni FK:
- ``compute_landed_aed`` aplica conversión correcta para ``*_aed``, ``*_eur`` y
  ``*_pct`` (US-1A-04-02 trigger spec).
- ``compute_landed_aed`` con currency_origin='AED' no aplica FX (rate 1).
- ``compute_landed_aed`` con FX rate manualmente inyectado (mock fx_rates).
- ``compute_landed_aed`` retorna None si no hay FX (no rompe).
- ``_snapshot`` y ``_compute_diff`` producen el shape esperado.
- ``_maybe_remap_fx_error`` re-lanza FXRateNotFoundAtEffectiveAt cuando el
  IntegrityError contiene el código semántico del trigger.

La interacción `create_cost`/`update_cost` con DB real se cubre en
`tests/data/test_costs_fx_trigger.py` (testcontainer).
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.services.costs.cost_service import (
    CostService,
    FXRateNotFoundAtEffectiveAt,
    _compute_diff,
    _snapshot,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------
class _FakeFX:
    def __init__(self, rate: str | float) -> None:
        self.rate = Decimal(str(rate))


class _FakeCost:
    def __init__(self, **kw: Any) -> None:
        self.id = kw.get("id", uuid4())
        self.sku = kw.get("sku", "MT-V-038")
        self.scheme_code = kw.get("scheme_code", "FBA")
        self.supplier_code = kw.get("supplier_code")
        self.currency_origin = kw.get("currency_origin", "EUR")
        self.fx_rate_id = kw.get("fx_rate_id")
        self.effective_at = kw.get(
            "effective_at", datetime(2026, 6, 12, tzinfo=timezone.utc)
        )
        self.breakdown = kw.get("breakdown", {})
        self.scheme_landed_aed = kw.get("scheme_landed_aed")
        self.status = kw.get("status", "active")
        self.version = kw.get("version", 1)
        self.fx_inferred = kw.get("fx_inferred", False)
        self.created_by = kw.get("created_by")
        self.updated_by = kw.get("updated_by")
        self.created_at = kw.get(
            "created_at", datetime(2026, 5, 7, tzinfo=timezone.utc)
        )
        self.updated_at = kw.get(
            "updated_at", datetime(2026, 5, 7, tzinfo=timezone.utc)
        )


def _session_with_fx(rate: str | float | None) -> Any:
    """Build a fake session whose execute() returns a FakeFX (or None)."""
    sess = MagicMock()
    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none = MagicMock(
        return_value=_FakeFX(rate) if rate is not None else None
    )
    sess.execute = AsyncMock(return_value=scalar_result)
    return sess


# ---------------------------------------------------------------------------
# compute_landed_aed
# ---------------------------------------------------------------------------
async def test_compute_landed_aed_origin_aed_skips_fx() -> None:
    sess = _session_with_fx(None)  # no FX even queried
    svc = CostService(sess)
    res = await svc.compute_landed_aed(
        breakdown={"fob_aed": "10.00", "freight_aed": "2.50"},
        currency_origin="AED",
        effective_at=datetime(2026, 6, 12, tzinfo=timezone.utc),
    )
    assert res == Decimal("12.5000")


async def test_compute_landed_aed_eur_components_use_fx() -> None:
    """fob_eur=12.40, freight_eur=1.80, FX 4.29 → (12.40+1.80)*4.29 = 60.918."""
    sess = _session_with_fx("4.29")
    svc = CostService(sess)
    res = await svc.compute_landed_aed(
        breakdown={"fob_eur": "12.40", "freight_eur": "1.80"},
        currency_origin="EUR",
        effective_at=datetime(2026, 6, 12, tzinfo=timezone.utc),
    )
    expected = (Decimal("12.40") + Decimal("1.80")) * Decimal("4.29")
    assert res == expected.quantize(Decimal("0.0001"))


async def test_compute_landed_aed_mixed_aed_and_eur() -> None:
    """fob_eur=10 * 4.29 + customs_aed=5 = 47.90"""
    sess = _session_with_fx("4.29")
    svc = CostService(sess)
    res = await svc.compute_landed_aed(
        breakdown={"fob_eur": "10", "customs_aed": "5"},
        currency_origin="EUR",
        effective_at=datetime(2026, 6, 12, tzinfo=timezone.utc),
    )
    assert res == Decimal("47.9000")


async def test_compute_landed_aed_pct_applies_on_subtotal() -> None:
    """fob_eur=10 * 4.29 + customs_aed=5 = 47.90 ; payment_fees_pct=10 → +4.79 = 52.69"""
    sess = _session_with_fx("4.29")
    svc = CostService(sess)
    res = await svc.compute_landed_aed(
        breakdown={
            "fob_eur": "10",
            "customs_aed": "5",
            "payment_fees_pct": "10",
        },
        currency_origin="EUR",
        effective_at=datetime(2026, 6, 12, tzinfo=timezone.utc),
    )
    expected = Decimal("47.90") + (Decimal("47.90") * Decimal("10") / Decimal("100"))
    assert res == expected.quantize(Decimal("0.0001"))


async def test_compute_landed_aed_returns_none_when_fx_missing_for_non_aed() -> None:
    """No FX rate in DB and currency_origin != AED → returns None (caller decides)."""
    sess = _session_with_fx(None)
    svc = CostService(sess)
    res = await svc.compute_landed_aed(
        breakdown={"fob_eur": "10"},
        currency_origin="EUR",
        effective_at=datetime(2026, 6, 12, tzinfo=timezone.utc),
    )
    assert res is None


async def test_compute_landed_aed_ignores_non_numeric_values() -> None:
    sess = _session_with_fx("4.29")
    svc = CostService(sess)
    # "abc" should be silently ignored, not crash.
    res = await svc.compute_landed_aed(
        breakdown={"fob_eur": "10", "comment_str": "abc"},
        currency_origin="EUR",
        effective_at=datetime(2026, 6, 12, tzinfo=timezone.utc),
    )
    assert res == (Decimal("10") * Decimal("4.29")).quantize(Decimal("0.0001"))


# ---------------------------------------------------------------------------
# _snapshot / _compute_diff
# ---------------------------------------------------------------------------
def test_snapshot_includes_canonical_fields() -> None:
    cost = _FakeCost(
        sku="MT-V-038",
        scheme_code="FBA",
        currency_origin="EUR",
        breakdown={"fob_eur": 12.40},
        scheme_landed_aed=Decimal("53.196"),
        version=1,
    )
    snap = _snapshot(cost)
    assert snap["sku"] == "MT-V-038"
    assert snap["scheme_code"] == "FBA"
    assert snap["currency_origin"] == "EUR"
    assert snap["breakdown"] == {"fob_eur": 12.40}
    assert snap["scheme_landed_aed"] == "53.196"
    assert snap["version"] == 1
    assert snap["status"] == "active"


def test_compute_diff_only_emits_changed_keys() -> None:
    before = {"a": 1, "b": 2, "c": 3}
    after = {"a": 1, "b": 99, "c": 3, "d": 4}
    diff = _compute_diff(before, after)
    assert diff == {
        "b": {"before": 2, "after": 99},
        "d": {"before": None, "after": 4},
    }


def test_compute_diff_handles_removed_keys() -> None:
    before = {"a": 1, "b": 2}
    after = {"a": 1}
    diff = _compute_diff(before, after)
    assert diff == {"b": {"before": 2, "after": None}}


# ---------------------------------------------------------------------------
# FX error remap
# ---------------------------------------------------------------------------
def test_remap_fx_error_recognises_trigger_message() -> None:
    """The DB trigger raises with 'fx_rate_not_found_at_effective_at: ...'."""
    fake_orig = Exception(
        "fx_rate_not_found_at_effective_at: EUR -> AED at 2026-06-12 00:00:00+00"
    )
    err = IntegrityError(statement="INSERT", params=None, orig=fake_orig)
    with pytest.raises(FXRateNotFoundAtEffectiveAt):
        CostService._maybe_remap_fx_error(err)


def test_remap_fx_error_passes_through_other_errors() -> None:
    """Non-FX integrity errors are NOT remapped."""
    fake_orig = Exception("duplicate key value violates unique constraint")
    err = IntegrityError(statement="INSERT", params=None, orig=fake_orig)
    # Should NOT raise — just returns None silently.
    result = CostService._maybe_remap_fx_error(err)
    assert result is None

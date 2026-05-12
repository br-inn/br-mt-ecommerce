"""Unit tests para `app.services.pricing.exception_evaluator` — US-1B-02-03.

Cubre ExceptionEvaluator.evaluate() con 9 escenarios, sin IO ni DB.
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services.pricing.exception_evaluator import ExceptionEvaluator
from app.services.pricing.rule_engine import PricingResult

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CHANNEL_ID = uuid4()
SCHEME_CODE = "b2c"


def make_exception_rule(
    *,
    margin_threshold_pct: Decimal | None = None,
    fx_swing_threshold_pct: Decimal | None = None,
    min_margin_pct: Decimal | None = None,
    channel_id=None,
    scheme_code: str | None = None,
    active: bool = True,
) -> SimpleNamespace:
    """Crea un objeto ExceptionRule mínimo (sin DB) con los atributos evaluados."""
    return SimpleNamespace(
        id=uuid4(),
        active=active,
        channel_id=channel_id,
        scheme_code=scheme_code,
        margin_threshold_pct=margin_threshold_pct,
        fx_swing_threshold_pct=fx_swing_threshold_pct,
        min_margin_pct=min_margin_pct,
    )


def make_pricing_result(
    *,
    margin_pct: Decimal = Decimal("0.20"),
    rule_applied: str = "rule_a",
    alerts: list | None = None,
) -> PricingResult:
    """Crea un PricingResult mínimo para pruebas."""
    return PricingResult(
        amount=Decimal("100.00"),
        pvp_min=None,
        margin_pct=margin_pct,
        rule_applied=rule_applied,
        formula="test_formula",
        alerts=alerts or [],
    )


def make_prev_price(
    *,
    margin_pct: Decimal = Decimal("0.20"),
    rule_applied: str = "rule_a",
) -> SimpleNamespace:
    """Simula un Price ORM anterior con los atributos que lee ExceptionEvaluator."""
    return SimpleNamespace(
        margin_pct=margin_pct,
        rule_applied=rule_applied,
    )


# ---------------------------------------------------------------------------
# Escenario 1: Sin reglas activas → auto_approved
# ---------------------------------------------------------------------------


def test_no_active_rules_returns_auto_approved() -> None:
    """Sin reglas activas la lista está vacía → auto_approved (default)."""
    new_price = make_pricing_result()
    prev_price = make_prev_price()

    status, reasons = ExceptionEvaluator.evaluate(
        new_price=new_price,
        prev_price=prev_price,
        channel_id=CHANNEL_ID,
        scheme_code=SCHEME_CODE,
        active_rules=[],
    )

    assert status == "auto_approved"
    assert any(r["code"] == "auto_approved_default" for r in reasons)


# ---------------------------------------------------------------------------
# Escenario 2: Primera vez (prev_price=None) → auto_approved / first_price
# ---------------------------------------------------------------------------


def test_first_price_no_prev_returns_auto_approved() -> None:
    """Sin precio anterior → auto_approved con reason first_price."""
    new_price = make_pricing_result(margin_pct=Decimal("0.30"))

    status, reasons = ExceptionEvaluator.evaluate(
        new_price=new_price,
        prev_price=None,
        channel_id=CHANNEL_ID,
        scheme_code=SCHEME_CODE,
        active_rules=[],
    )

    assert status == "auto_approved"
    assert any(r["code"] == "first_price" for r in reasons)


def test_first_price_with_rules_but_above_min_margin() -> None:
    """Primera vez + margen suficiente → auto_approved con first_price."""
    rule = make_exception_rule(min_margin_pct=Decimal("5.0"))  # 5% threshold
    new_price = make_pricing_result(margin_pct=Decimal("0.30"))  # 30% → bien sobre umbral

    status, reasons = ExceptionEvaluator.evaluate(
        new_price=new_price,
        prev_price=None,
        channel_id=CHANNEL_ID,
        scheme_code=SCHEME_CODE,
        active_rules=[rule],
    )

    assert status == "auto_approved"
    assert any(r["code"] == "first_price" for r in reasons)


# ---------------------------------------------------------------------------
# Escenario 3: min_margin dispara → pending_review / below_min_margin
# ---------------------------------------------------------------------------


def test_below_min_margin_triggers_pending_review() -> None:
    """margin_pct*100 < min_margin_pct → pending_review con below_min_margin."""
    rule = make_exception_rule(min_margin_pct=Decimal("15.0"))  # requiere 15%
    new_price = make_pricing_result(margin_pct=Decimal("0.10"))  # 10% → por debajo

    status, reasons = ExceptionEvaluator.evaluate(
        new_price=new_price,
        prev_price=None,
        channel_id=CHANNEL_ID,
        scheme_code=SCHEME_CODE,
        active_rules=[rule],
    )

    assert status == "pending_review"
    assert any(r["code"] == "below_min_margin" for r in reasons)


def test_min_margin_exact_boundary_is_auto_approved() -> None:
    """margin_pct*100 == min_margin_pct (no menor) → no dispara → auto_approved."""
    rule = make_exception_rule(min_margin_pct=Decimal("10.0"))
    new_price = make_pricing_result(margin_pct=Decimal("0.10"))  # 10% == 10% → no dispara

    status, reasons = ExceptionEvaluator.evaluate(
        new_price=new_price,
        prev_price=None,
        channel_id=CHANNEL_ID,
        scheme_code=SCHEME_CODE,
        active_rules=[rule],
    )

    assert status == "auto_approved"


# ---------------------------------------------------------------------------
# Escenario 4: fx_swing dispara → pending_review / fx_swing_exceeded
# ---------------------------------------------------------------------------


def test_fx_swing_exceeded_triggers_pending_review() -> None:
    """FX swing > umbral → pending_review con fx_swing_exceeded."""
    rule = make_exception_rule(fx_swing_threshold_pct=Decimal("3.0"))
    new_price = make_pricing_result()
    prev_price = make_prev_price()

    status, reasons = ExceptionEvaluator.evaluate(
        new_price=new_price,
        prev_price=prev_price,
        channel_id=CHANNEL_ID,
        scheme_code=SCHEME_CODE,
        active_rules=[rule],
        prev_fx_rate=Decimal("4.00"),
        current_fx_rate=Decimal("4.20"),  # swing = 5% > 3%
    )

    assert status == "pending_review"
    assert any(r["code"] == "fx_swing_exceeded" for r in reasons)


def test_fx_swing_below_threshold_is_auto_approved() -> None:
    """FX swing <= umbral → no dispara → auto_approved."""
    rule = make_exception_rule(fx_swing_threshold_pct=Decimal("5.0"))
    new_price = make_pricing_result()
    prev_price = make_prev_price()

    status, reasons = ExceptionEvaluator.evaluate(
        new_price=new_price,
        prev_price=prev_price,
        channel_id=CHANNEL_ID,
        scheme_code=SCHEME_CODE,
        active_rules=[rule],
        prev_fx_rate=Decimal("4.00"),
        current_fx_rate=Decimal("4.10"),  # swing = 2.5% < 5%
    )

    assert status == "auto_approved"


# ---------------------------------------------------------------------------
# Escenario 5: Ninguna regla dispara → auto_approved / auto_approved_default
# ---------------------------------------------------------------------------


def test_no_exception_fires_returns_auto_approved_default() -> None:
    """Con reglas configuradas pero nada supera umbrales → auto_approved_default."""
    rule = make_exception_rule(
        margin_threshold_pct=Decimal("20.0"),
        fx_swing_threshold_pct=Decimal("10.0"),
        min_margin_pct=Decimal("5.0"),
    )
    new_price = make_pricing_result(margin_pct=Decimal("0.25"))  # 25% > 5% min, delta=0%
    prev_price = make_prev_price(margin_pct=Decimal("0.25"), rule_applied="rule_a")

    status, reasons = ExceptionEvaluator.evaluate(
        new_price=new_price,
        prev_price=prev_price,
        channel_id=CHANNEL_ID,
        scheme_code=SCHEME_CODE,
        active_rules=[rule],
        prev_fx_rate=Decimal("4.00"),
        current_fx_rate=Decimal("4.02"),  # swing = 0.5% < 10%
    )

    assert status == "auto_approved"
    assert any(r["code"] == "auto_approved_default" for r in reasons)


# ---------------------------------------------------------------------------
# Escenario 6 (bonus): margin_delta dispara → pending_review
# ---------------------------------------------------------------------------


def test_margin_delta_exceeded_triggers_pending_review() -> None:
    """Delta de margen > margin_threshold_pct → pending_review / margin_delta_exceeded."""
    rule = make_exception_rule(margin_threshold_pct=Decimal("5.0"))  # 5% max delta
    new_price = make_pricing_result(margin_pct=Decimal("0.30"))   # 30%
    prev_price = make_prev_price(margin_pct=Decimal("0.20"))       # 20% → delta = 10% > 5%

    status, reasons = ExceptionEvaluator.evaluate(
        new_price=new_price,
        prev_price=prev_price,
        channel_id=CHANNEL_ID,
        scheme_code=SCHEME_CODE,
        active_rules=[rule],
    )

    assert status == "pending_review"
    assert any(r["code"] == "margin_delta_exceeded" for r in reasons)


# ---------------------------------------------------------------------------
# Escenario 7 (bonus): Alertas críticas → pending_review / critical_alerts
# ---------------------------------------------------------------------------


def test_critical_alert_triggers_pending_review() -> None:
    """Alerta severity=critical en PricingResult → pending_review con critical_alerts."""
    new_price = make_pricing_result(
        alerts=[{"severity": "critical", "message": "precio bajo cero neto"}]
    )

    status, reasons = ExceptionEvaluator.evaluate(
        new_price=new_price,
        prev_price=None,
        channel_id=CHANNEL_ID,
        scheme_code=SCHEME_CODE,
        active_rules=[],
    )

    assert status == "pending_review"
    reason = next(r for r in reasons if r["code"] == "critical_alerts")
    assert len(reason["alerts"]) == 1


def test_warning_alert_does_not_trigger_pending_review() -> None:
    """Alerta severity=warning (no critical) no dispara pending_review."""
    new_price = make_pricing_result(
        alerts=[{"severity": "warning", "message": "margen ajustado"}]
    )

    status, reasons = ExceptionEvaluator.evaluate(
        new_price=new_price,
        prev_price=None,
        channel_id=CHANNEL_ID,
        scheme_code=SCHEME_CODE,
        active_rules=[],
    )

    assert status == "auto_approved"
    assert not any(r["code"] == "critical_alerts" for r in reasons)


# ---------------------------------------------------------------------------
# Escenario 8 (bonus): Regla inactiva ignorada
# ---------------------------------------------------------------------------


def test_inactive_rule_is_ignored() -> None:
    """Regla con active=False no se evalúa aunque tenga thresholds bajos."""
    rule = make_exception_rule(
        min_margin_pct=Decimal("99.0"),  # dispararía si estuviera activa
        active=False,
    )
    new_price = make_pricing_result(margin_pct=Decimal("0.10"))  # 10% << 99%

    status, reasons = ExceptionEvaluator.evaluate(
        new_price=new_price,
        prev_price=None,
        channel_id=CHANNEL_ID,
        scheme_code=SCHEME_CODE,
        active_rules=[rule],
    )

    # La regla inactiva no debe haber disparado below_min_margin
    assert status == "auto_approved"
    assert not any(r["code"] == "below_min_margin" for r in reasons)


# ---------------------------------------------------------------------------
# Escenario 9 (bonus): Regla de canal diferente ignorada
# ---------------------------------------------------------------------------


def test_rule_for_different_channel_is_ignored() -> None:
    """Regla con channel_id distinto no aplica al canal evaluado."""
    other_channel = uuid4()
    rule = make_exception_rule(
        channel_id=other_channel,
        min_margin_pct=Decimal("50.0"),  # dispararía si aplicara
    )
    new_price = make_pricing_result(margin_pct=Decimal("0.10"))  # 10% << 50%

    status, reasons = ExceptionEvaluator.evaluate(
        new_price=new_price,
        prev_price=None,
        channel_id=CHANNEL_ID,  # canal distinto al de la regla
        scheme_code=SCHEME_CODE,
        active_rules=[rule],
    )

    assert status == "auto_approved"
    assert not any(r["code"] == "below_min_margin" for r in reasons)

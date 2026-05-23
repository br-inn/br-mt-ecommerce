"""Smoke tests del motor de pricing v5.1 ported (Wave 2).

Sólo verifica:
- imports OK (no errores de sintaxis / referencias rotas)
- reglas puras devuelven valores con tipos correctos
- state machine valida transiciones
- exception evaluator devuelve dos branches válidos
"""

from __future__ import annotations

from decimal import Decimal

import pytest

pytestmark = pytest.mark.unit


def test_pricing_module_imports() -> None:
    """Verifica que todos los módulos públicos importan sin error."""
    from app.services.pricing import (  # noqa: F401
        ALLOWED_TRANSITIONS,
        ExceptionEvaluator,
        InvalidTransition,
        PricingResult,
        PricingRuleEngine,
        PricingService,
    )
    from app.api.routes.pricing import router  # noqa: F401
    from app.db.models.pricing import (  # noqa: F401
        Channel,
        Cost,
        ExceptionRule,
        FXRate,
        Price,
        PriceApprovalEvent,
    )
    from app.schemas.pricing import (  # noqa: F401
        ChannelResponse,
        FXRateResponse,
        PriceResponse,
        PricingResultResponse,
    )


def test_calculate_median() -> None:
    from app.services.pricing import PricingRuleEngine

    e = PricingRuleEngine()
    assert e.calculate_median([10, 20, 30]) == Decimal("20.00")
    assert e.calculate_median([]) is None
    assert e.calculate_median([0, 0]) is None


def test_calc_margin_pct() -> None:
    from app.services.pricing import PricingRuleEngine

    assert PricingRuleEngine.calc_margin_pct(Decimal("100"), Decimal("70")) == Decimal("0.3000")
    assert PricingRuleEngine.calc_margin_pct(Decimal("0"), Decimal("70")) == Decimal("0")


def test_fba_fee_fallback_bands() -> None:
    from app.services.pricing import PricingRuleEngine

    assert PricingRuleEngine.get_fba_fee_fallback(Decimal("0.1"), "G1") == Decimal("8.0")
    assert PricingRuleEngine.get_fba_fee_fallback(Decimal("1.0"), "G1") == Decimal("14.0")
    assert PricingRuleEngine.get_fba_fee_fallback(Decimal("3.0"), "G1") == Decimal("35.0")
    # G2 sin peso → asume HEAVY
    assert PricingRuleEngine.get_fba_fee_fallback(None, "G2") == Decimal("35.0")


def test_state_machine_legal_transition() -> None:
    from app.services.pricing import is_valid_transition

    assert is_valid_transition("draft", "auto_approved")
    assert is_valid_transition("draft", "pending_review")
    assert is_valid_transition("pending_review", "approved")
    # ilegales
    assert not is_valid_transition("draft", "exported")
    assert not is_valid_transition("approved", "rejected")
    assert not is_valid_transition("exported", "draft")  # terminal


def test_calculate_full_pipeline_no_market() -> None:
    """Caso sin candidates ni master_data — debe caer a fallback global."""
    from app.services.pricing import PricingRuleEngine

    engine = PricingRuleEngine()

    product = {
        "sku": "TEST123",
        "family": "HIDROSANITARIO",
        "subfamily": None,
        "material": "brass",
        "weight": Decimal("0.5"),
        "name_en": "Test valve",
    }
    channel = {"code": "amazon_uae"}
    scheme = {"code": "FBA"}
    cost = {"total": Decimal("20"), "breakdown": {}}

    result = engine.calculate(
        product=product,
        channel=channel,
        scheme=scheme,
        cost=cost,
        fx_rate=Decimal("4.29"),
    )
    assert result.amount > 0
    assert result.pvp_min is not None and result.pvp_min > 0
    # Sin match — esperamos g1_no_match
    assert result.rule_applied in {
        "aggressive_g1_no_match",
        "aggressive_g2_no_match_default",
    }
    # PVP final >= PVP_MIN (regla floor)
    assert result.amount >= result.pvp_min


def test_exception_evaluator_first_price_auto_approved() -> None:
    from app.services.pricing import ExceptionEvaluator
    from app.services.pricing.rule_engine import PricingResult

    new_price = PricingResult(
        amount=Decimal("100"),
        pvp_min=Decimal("80"),
        margin_pct=Decimal("0.20"),
        rule_applied="aggressive_g1_no_match",
        formula="dummy",
    )
    next_status, reasons = ExceptionEvaluator.evaluate(
        new_price=new_price,
        prev_price=None,
        channel_id="00000000-0000-0000-0000-000000000000",
        scheme_code="FBA",
        active_rules=[],
    )
    assert next_status == "auto_approved"
    assert any(r["code"] == "first_price" for r in reasons)


def test_exception_evaluator_critical_alerts_pending() -> None:
    from app.services.pricing import ExceptionEvaluator
    from app.services.pricing.rule_engine import PricingResult

    new_price = PricingResult(
        amount=Decimal("100"),
        pvp_min=Decimal("80"),
        margin_pct=Decimal("0.20"),
        rule_applied="aggressive_g1_no_match",
        formula="dummy",
        alerts=[{"severity": "critical", "code": "floor_forced", "message": "..."}],
    )
    next_status, _reasons = ExceptionEvaluator.evaluate(
        new_price=new_price,
        prev_price=None,
        channel_id="00000000-0000-0000-0000-000000000000",
        scheme_code="FBA",
        active_rules=[],
    )
    assert next_status == "pending_review"

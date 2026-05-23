"""Unit tests para `app.services.pricing.state_machine_v51`.

US-1B-01-02 — pipeline v5.1: golden numbers + classify alerts + decide status.

≥ 8 tests requeridos. Cubre:
1. golden numbers aplica bundling tier 2 (.95).
2. golden numbers respetan disable_bundling.
3. classify_alerts agrupa critical/warning/info correctamente.
4. critical alerts → pending_review.
5. warnings sólos → auto_approved (con razón anotada).
6. delta_margin > threshold → pending_review.
7. force_pending_review override fuerza el estado.
8. force_auto_approved override fuerza el estado (incluso con criticals).
9. force_pending + force_auto inconsistente → InvalidV51Override.
10. clean (sin alerts) → auto_approved.
11. delta_warn_pct_override custom honored.
12. apply_v51 retorna V51Decision con todos los campos.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.services.pricing.state_machine_v51 import (
    InvalidV51Override,
    V51Decision,
    apply_v51,
    classify_alerts,
    decide_initial_status,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# classify_alerts
# ---------------------------------------------------------------------------
def test_classify_alerts_groups_by_severity() -> None:
    alerts = [
        {"severity": "critical", "code": "floor_forced"},
        {"severity": "warning", "code": "cap_applied"},
        {"severity": "info", "code": "velocity_premium"},
        {"level": "critical", "code": "alt_field"},
        {"code": "no_severity"},  # default → info
    ]
    classified = classify_alerts(alerts)
    assert len(classified["critical"]) == 2
    assert len(classified["warning"]) == 1
    assert len(classified["info"]) == 2


def test_classify_alerts_empty_returns_buckets() -> None:
    classified = classify_alerts(None)
    assert classified == {"critical": [], "warning": [], "info": []}


# ---------------------------------------------------------------------------
# decide_initial_status
# ---------------------------------------------------------------------------
def test_decide_initial_status_critical_pending_review() -> None:
    classified = {"critical": [{"code": "x"}], "warning": [], "info": []}
    status, reasons = decide_initial_status(classified)
    assert status == "pending_review"
    assert "critical_alerts_present" in reasons


def test_decide_initial_status_warnings_only_auto_approved() -> None:
    classified = {"critical": [], "warning": [{"code": "x"}], "info": []}
    status, reasons = decide_initial_status(classified)
    assert status == "auto_approved"
    assert any("warnings_present" in r for r in reasons)


def test_decide_initial_status_clean_auto_approved() -> None:
    classified = {"critical": [], "warning": [], "info": []}
    status, reasons = decide_initial_status(classified)
    assert status == "auto_approved"
    assert "clean_no_alerts" in reasons


def test_decide_initial_status_delta_above_threshold_pending() -> None:
    classified = {"critical": [], "warning": [], "info": []}
    status, reasons = decide_initial_status(classified, delta_margin_pct=Decimal("15.0"))
    assert status == "pending_review"
    assert any("delta_margin_pct_above_threshold" in r for r in reasons)


def test_decide_initial_status_delta_below_threshold_auto_approved() -> None:
    classified = {"critical": [], "warning": [], "info": []}
    status, _ = decide_initial_status(classified, delta_margin_pct=Decimal("5.0"))
    assert status == "auto_approved"


def test_decide_initial_status_force_pending_review() -> None:
    classified = {"critical": [], "warning": [], "info": []}
    status, reasons = decide_initial_status(classified, overrides={"force_pending_review": True})
    assert status == "pending_review"
    assert "override:force_pending_review" in reasons


def test_decide_initial_status_force_auto_overrides_critical() -> None:
    classified = {"critical": [{"code": "x"}], "warning": [], "info": []}
    status, reasons = decide_initial_status(classified, overrides={"force_auto_approved": True})
    assert status == "auto_approved"
    assert "override:force_auto_approved" in reasons


def test_decide_initial_status_conflicting_overrides_raises() -> None:
    classified = {"critical": [], "warning": [], "info": []}
    with pytest.raises(InvalidV51Override):
        decide_initial_status(
            classified,
            overrides={
                "force_pending_review": True,
                "force_auto_approved": True,
            },
        )


def test_decide_initial_status_delta_warn_pct_override() -> None:
    classified = {"critical": [], "warning": [], "info": []}
    # delta=12, default threshold 10 → pending. With override=20 → auto_approved.
    status, _ = decide_initial_status(
        classified,
        delta_margin_pct=Decimal("12.0"),
        delta_warn_pct=Decimal("20.0"),
    )
    assert status == "auto_approved"


# ---------------------------------------------------------------------------
# apply_v51 — pipeline completo
# ---------------------------------------------------------------------------
def test_apply_v51_returns_v51_decision_clean() -> None:
    decision = apply_v51(
        raw_amount=Decimal("95.78"),
        alerts=[],
        channel_code="amazon_uae",
    )
    assert isinstance(decision, V51Decision)
    assert decision.initial_status == "auto_approved"
    # Tier 2 → 95.95.
    assert decision.final_amount == Decimal("95.95")
    assert decision.bundling_info["tier_name"] == "tier_2_medium"
    assert "clean_no_alerts" in decision.decision_reasons


def test_apply_v51_critical_alert_pending_review() -> None:
    decision = apply_v51(
        raw_amount=Decimal("100.00"),
        alerts=[{"severity": "critical", "code": "price_below_pvp_min"}],
        channel_code="amazon_uae",
    )
    assert decision.initial_status == "pending_review"
    assert decision.has_critical
    assert not decision.has_warnings


def test_apply_v51_disable_bundling_override() -> None:
    decision = apply_v51(
        raw_amount=Decimal("145.34"),
        alerts=[],
        channel_code="amazon_uae",
        overrides={"disable_bundling": True},
    )
    assert decision.final_amount == Decimal("145.34")
    assert decision.bundling_info.get("override_disable_bundling") == "true"


def test_apply_v51_force_pending_review_override() -> None:
    decision = apply_v51(
        raw_amount=Decimal("100.00"),
        alerts=[],
        channel_code="amazon_uae",
        overrides={"force_pending_review": True},
    )
    assert decision.initial_status == "pending_review"
    assert decision.overrides_applied.get("force_pending_review") is True


def test_apply_v51_with_warning_only_auto_approved() -> None:
    decision = apply_v51(
        raw_amount=Decimal("85.00"),
        alerts=[{"severity": "warning", "code": "match_low_quality"}],
        channel_code="amazon_uae",
    )
    assert decision.initial_status == "auto_approved"
    assert decision.has_warnings
    assert not decision.has_critical


def test_apply_v51_b2b_disables_bundling_by_default() -> None:
    decision = apply_v51(
        raw_amount=Decimal("145.34"),
        alerts=[],
        channel_code="b2b_direct",
    )
    # b2b_direct default strategy = none → no snap.
    assert decision.final_amount == Decimal("145.34")
    assert decision.bundling_info["applied"] == "false"


def test_apply_v51_delta_margin_triggers_pending_review() -> None:
    decision = apply_v51(
        raw_amount=Decimal("100.00"),
        alerts=[],
        channel_code="amazon_uae",
        delta_margin_pct=Decimal("12.5"),
    )
    assert decision.initial_status == "pending_review"
    assert any("delta_margin" in r for r in decision.decision_reasons)

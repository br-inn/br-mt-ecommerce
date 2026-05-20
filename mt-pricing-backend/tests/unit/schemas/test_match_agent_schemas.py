"""Tests de schemas del agente de validación."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.match_agent import MatchAgentConfigUpdate, MatchAgentMetrics


def test_config_update_rejects_alpha_out_of_range():
    with pytest.raises(ValidationError):
        MatchAgentConfigUpdate(alpha=1.5)


def test_config_update_accepts_partial():
    upd = MatchAgentConfigUpdate(mode="active")
    assert upd.mode == "active"
    assert upd.alpha is None


def test_metrics_shadow_precision_optional():
    m = MatchAgentMetrics(
        golden_labels_total=10,
        min_labels_gate=200,
        gate_reached=False,
        shadow_decisions=0,
        shadow_precision=None,
        calibrator_version=None,
        calibrator_brier=None,
        calibrator_ece=None,
        calibrator_trained_on=None,
        mode="shadow",
    )
    assert m.gate_reached is False

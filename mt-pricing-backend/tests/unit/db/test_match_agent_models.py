"""Tests de los modelos ORM del agente."""
from __future__ import annotations

from app.db.models.match_agent import MatchAgentConfig, MatchAgentDecision


def test_config_tablename():
    assert MatchAgentConfig.__tablename__ == "match_agent_config"


def test_decision_tablename():
    assert MatchAgentDecision.__tablename__ == "match_agent_decisions"


def test_config_columns_present():
    cols = set(MatchAgentConfig.__table__.columns.keys())
    assert {"id", "mode", "alpha", "min_labels_gate", "updated_by", "updated_at"} <= cols


def test_decision_columns_present():
    cols = set(MatchAgentDecision.__table__.columns.keys())
    assert {
        "id", "candidate_id", "product_sku", "verdict", "mode", "applied",
        "signal", "score", "calibrated_confidence", "review_priority",
        "calibrator_version", "human_outcome", "created_at",
    } <= cols

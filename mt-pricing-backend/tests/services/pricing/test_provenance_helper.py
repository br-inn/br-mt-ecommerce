"""Tests for app.services.pricing.provenance — stamp() helper (pure, no DB)."""

from decimal import Decimal
from uuid import uuid4

from app.services.pricing.provenance import stamp


def test_stamp_adds_actor_source_and_observed_at():
    actor = uuid4()
    out = stamp(
        {"fx_rate": Decimal("4.28")},
        actor_id=actor,
        source_op="decision_local",
        updated_field="updated_by",
    )
    assert out["fx_rate"] == Decimal("4.28")
    assert out["updated_by"] == actor
    assert out["source_op"] == "decision_local"
    assert out["observed_at"] is not None


def test_stamp_created_field_variant():
    actor = uuid4()
    out = stamp(
        {"margin_override_pct": Decimal("12")},
        actor_id=actor,
        source_op="decision_local",
        updated_field="created_by",
    )
    assert out["created_by"] == actor


def test_stamp_optional_source_ref():
    out = stamp({"x": 1}, actor_id=None, source_op="master_canal", source_ref="file.pdf")
    assert out["source_ref"] == "file.pdf"
    assert out["source_op"] == "master_canal"

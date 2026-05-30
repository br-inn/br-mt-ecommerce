from datetime import UTC, datetime, timedelta

from app.services.pricing.provenance_query import compute_is_healthy, compute_is_stale


def test_is_healthy_false_when_never_synced():
    assert compute_is_healthy(None, 1440, now=datetime.now(UTC)) is False


def test_is_healthy_true_within_sla():
    now = datetime.now(UTC)
    assert compute_is_healthy(now - timedelta(minutes=10), 1440, now=now) is True


def test_is_healthy_false_past_sla():
    now = datetime.now(UTC)
    assert compute_is_healthy(now - timedelta(minutes=2000), 1440, now=now) is False


def test_is_stale_true_when_valid_until_past():
    now = datetime.now(UTC)
    assert compute_is_stale(now - timedelta(days=1), now - timedelta(hours=1), now=now) is True


def test_is_stale_true_when_no_observed_at():
    assert compute_is_stale(None, None, now=datetime.now(UTC)) is True


def test_is_stale_false_when_valid():
    now = datetime.now(UTC)
    assert compute_is_stale(now - timedelta(hours=1), now + timedelta(days=1), now=now) is False

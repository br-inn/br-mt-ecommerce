"""Unit tests for CircuitBreaker and ProxyPool (app/services/scraper/circuit_breaker.py).

All Redis calls are mocked via AsyncMock so no real Redis instance is needed.
"""

from __future__ import annotations

import time
from unittest.mock import AsyncMock

import pytest

from app.services.scraper.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    ProxyPool,
    ScraperCircuitOpenError,
)

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REDIS_URL = "redis://localhost:6379/0"


def _make_cb(**kwargs) -> CircuitBreaker:
    """Return a CircuitBreaker with a test-friendly default config."""
    defaults = dict(failure_threshold=3, recovery_timeout=60, failure_window=120)
    defaults.update(kwargs)
    return CircuitBreaker(REDIS_URL, **defaults)


def _make_redis_mock(**get_returns) -> AsyncMock:
    """Build a minimal async Redis mock.  Keyword args map method → return_value."""
    r = AsyncMock()
    for method, rv in get_returns.items():
        getattr(r, method).return_value = rv
    return r


# ---------------------------------------------------------------------------
# CircuitBreaker — get_state
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_state_closed_when_no_key() -> None:
    """No Redis key → CLOSED (default state)."""
    cb = _make_cb()
    r = _make_redis_mock(get=None)
    cb._redis = r

    state = await cb.get_state("example.com")

    assert state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_get_state_closed_when_key_is_closed() -> None:
    cb = _make_cb()
    r = _make_redis_mock(get="closed")
    cb._redis = r

    state = await cb.get_state("example.com")

    assert state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_get_state_open_within_recovery_timeout() -> None:
    """OPEN state within recovery window stays OPEN."""
    cb = _make_cb(recovery_timeout=300)
    # Two sequential gets: first for state_key ("open"), then for opened_at_key (recent)
    r = AsyncMock()
    r.get.side_effect = ["open", str(time.time() - 10)]  # only 10 s elapsed
    cb._redis = r

    state = await cb.get_state("example.com")

    assert state == CircuitState.OPEN


@pytest.mark.asyncio
async def test_get_state_transitions_to_half_open_after_timeout() -> None:
    """OPEN state after recovery timeout transitions to HALF_OPEN."""
    cb = _make_cb(recovery_timeout=60)
    r = AsyncMock()
    r.get.side_effect = ["open", str(time.time() - 120)]  # 120 s elapsed > 60
    r.set = AsyncMock()
    cb._redis = r

    state = await cb.get_state("example.com")

    assert state == CircuitState.HALF_OPEN
    r.set.assert_called_once()


@pytest.mark.asyncio
async def test_get_state_half_open_returned_directly() -> None:
    """Stored half_open state is returned as-is."""
    cb = _make_cb()
    r = _make_redis_mock(get="half_open")
    cb._redis = r

    state = await cb.get_state("example.com")

    assert state == CircuitState.HALF_OPEN


@pytest.mark.asyncio
async def test_get_state_fails_open_on_redis_error() -> None:
    """Redis error → fail-open (return CLOSED)."""
    cb = _make_cb()
    r = AsyncMock()
    r.get.side_effect = ConnectionError("redis down")
    cb._redis = r

    state = await cb.get_state("example.com")

    assert state == CircuitState.CLOSED


# ---------------------------------------------------------------------------
# CircuitBreaker — check_and_raise
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_and_raise_does_not_raise_when_closed() -> None:
    cb = _make_cb()
    r = _make_redis_mock(get=None)
    cb._redis = r

    await cb.check_and_raise("example.com")  # no exception


@pytest.mark.asyncio
async def test_check_and_raise_raises_when_open() -> None:
    cb = _make_cb(recovery_timeout=300)
    r = AsyncMock()
    r.get.side_effect = ["open", str(time.time() - 10)]
    cb._redis = r

    with pytest.raises(ScraperCircuitOpenError) as exc_info:
        await cb.check_and_raise("example.com")

    assert exc_info.value.domain == "example.com"
    assert "example.com" in str(exc_info.value)


# ---------------------------------------------------------------------------
# CircuitBreaker — record_failure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_failure_stays_closed_below_threshold() -> None:
    cb = _make_cb(failure_threshold=5)
    r = AsyncMock()
    r.incr.return_value = 3  # below threshold
    r.expire = AsyncMock()
    cb._redis = r

    result = await cb.record_failure("example.com")

    assert result == CircuitState.CLOSED
    r.incr.assert_called_once()


@pytest.mark.asyncio
async def test_record_failure_opens_circuit_at_threshold() -> None:
    cb = _make_cb(failure_threshold=5)
    r = AsyncMock()
    r.incr.return_value = 5  # hits threshold
    r.expire = AsyncMock()
    r.set = AsyncMock()
    cb._redis = r

    result = await cb.record_failure("example.com")

    assert result == CircuitState.OPEN
    # Should have called set twice: one for state, one for opened_at
    assert r.set.call_count == 2


@pytest.mark.asyncio
async def test_record_failure_opens_circuit_above_threshold() -> None:
    cb = _make_cb(failure_threshold=3)
    r = AsyncMock()
    r.incr.return_value = 7  # well above threshold
    r.expire = AsyncMock()
    r.set = AsyncMock()
    cb._redis = r

    result = await cb.record_failure("example.com")

    assert result == CircuitState.OPEN


@pytest.mark.asyncio
async def test_record_failure_fails_gracefully_on_redis_error() -> None:
    cb = _make_cb()
    r = AsyncMock()
    r.incr.side_effect = ConnectionError("redis down")
    cb._redis = r

    result = await cb.record_failure("example.com")

    assert result == CircuitState.CLOSED  # fail-open


# ---------------------------------------------------------------------------
# CircuitBreaker — record_success
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_success_deletes_all_keys() -> None:
    cb = _make_cb()
    r = AsyncMock()
    r.delete = AsyncMock()
    cb._redis = r

    await cb.record_success("example.com")

    r.delete.assert_called_once()
    deleted_keys = r.delete.call_args[0]
    assert any("state" in k for k in deleted_keys)
    assert any("failures" in k for k in deleted_keys)
    assert any("opened_at" in k for k in deleted_keys)


@pytest.mark.asyncio
async def test_record_success_ignores_redis_error() -> None:
    cb = _make_cb()
    r = AsyncMock()
    r.delete.side_effect = ConnectionError("redis down")
    cb._redis = r

    await cb.record_success("example.com")  # should not raise


# ---------------------------------------------------------------------------
# CircuitBreaker — force_open / force_close
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_force_open_sets_state_without_ttl() -> None:
    cb = _make_cb()
    r = AsyncMock()
    r.set = AsyncMock()
    cb._redis = r

    await cb.force_open("example.com")

    # force_open sets state, opened_at, and forced keys
    assert r.set.call_count == 3
    call_args_list = [call[0] for call in r.set.call_args_list]
    state_call = call_args_list[0]
    assert state_call[1] == CircuitState.OPEN


@pytest.mark.asyncio
async def test_force_close_deletes_all_keys() -> None:
    cb = _make_cb()
    r = AsyncMock()
    r.delete = AsyncMock()
    cb._redis = r

    await cb.force_close("example.com")

    r.delete.assert_called_once()


@pytest.mark.asyncio
async def test_force_open_then_check_raises() -> None:
    """After force_open, check_and_raise should raise within recovery window."""
    cb = _make_cb(recovery_timeout=3600)
    r = AsyncMock()
    # force_open writes state=open
    r.set = AsyncMock()
    # get_state will see: state="open", opened_at=recent
    r.get.side_effect = ["open", str(time.time() - 5)]
    cb._redis = r

    with pytest.raises(ScraperCircuitOpenError):
        await cb.check_and_raise("example.com")


# ---------------------------------------------------------------------------
# CircuitBreaker — get_stats
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_stats_returns_closed_defaults() -> None:
    cb = _make_cb(failure_threshold=5, recovery_timeout=60)
    r = AsyncMock()
    r.mget.return_value = [None, None, None]
    cb._redis = r

    stats = await cb.get_stats("example.com")

    assert stats["state"] == "closed"
    assert stats["failures"] == 0
    assert stats["failure_threshold"] == 5
    assert stats["recovery_timeout"] == 60
    assert stats["opened_at"] is None


@pytest.mark.asyncio
async def test_get_stats_returns_open_state_with_failures() -> None:
    cb = _make_cb(failure_threshold=5, recovery_timeout=60)
    r = AsyncMock()
    opened_ts = time.time() - 30
    r.mget.return_value = ["open", "7", str(opened_ts)]
    cb._redis = r

    stats = await cb.get_stats("example.com")

    assert stats["state"] == "open"
    assert stats["failures"] == 7
    assert stats["opened_at"] == opened_ts


# ---------------------------------------------------------------------------
# ProxyPool — get_proxy
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_proxy_pool_returns_none_when_empty() -> None:
    pool = ProxyPool(REDIS_URL)
    r = AsyncMock()
    r.llen.return_value = 0
    pool._redis = r

    proxy = await pool.get_proxy()

    assert proxy is None


@pytest.mark.asyncio
async def test_proxy_pool_returns_proxy_when_available() -> None:
    pool = ProxyPool(REDIS_URL)
    r = AsyncMock()
    r.llen.return_value = 2
    r.rpoplpush.return_value = "http://proxy1:8080"
    r.exists.return_value = False  # no cooldown
    pool._redis = r

    proxy = await pool.get_proxy()

    assert proxy == "http://proxy1:8080"


@pytest.mark.asyncio
async def test_proxy_pool_skips_cooldown_proxy_and_returns_next() -> None:
    pool = ProxyPool(REDIS_URL)
    r = AsyncMock()
    r.llen.return_value = 2
    r.rpoplpush.side_effect = ["http://blocked:8080", "http://good:8080"]
    # First proxy is in cooldown, second is not
    r.exists.side_effect = [True, False]
    pool._redis = r

    proxy = await pool.get_proxy()

    assert proxy == "http://good:8080"


@pytest.mark.asyncio
async def test_proxy_pool_returns_none_when_all_in_cooldown() -> None:
    pool = ProxyPool(REDIS_URL)
    r = AsyncMock()
    r.llen.return_value = 2
    r.rpoplpush.side_effect = ["http://a:8080", "http://b:8080"]
    r.exists.return_value = True  # all in cooldown
    pool._redis = r

    proxy = await pool.get_proxy()

    assert proxy is None


@pytest.mark.asyncio
async def test_proxy_pool_mark_proxy_failed_sets_cooldown_key() -> None:
    pool = ProxyPool(REDIS_URL)
    r = AsyncMock()
    r.set = AsyncMock()
    pool._redis = r

    await pool.mark_proxy_failed("http://proxy1:8080", ttl=1800)

    r.set.assert_called_once()
    call_kwargs = r.set.call_args
    assert call_kwargs[1]["ex"] == 1800 or (len(call_kwargs[0]) >= 3 and call_kwargs[0][2] == 1800)


@pytest.mark.asyncio
async def test_proxy_pool_add_proxy_calls_lpush() -> None:
    pool = ProxyPool(REDIS_URL)
    r = AsyncMock()
    r.lpush.return_value = 1
    pool._redis = r

    result = await pool.add_proxy("http://new:8080")

    r.lpush.assert_called_once()
    assert result == 1


@pytest.mark.asyncio
async def test_proxy_pool_size_returns_llen() -> None:
    pool = ProxyPool(REDIS_URL)
    r = AsyncMock()
    r.llen.return_value = 5
    pool._redis = r

    sz = await pool.size()

    assert sz == 5


@pytest.mark.asyncio
async def test_proxy_pool_get_fails_open_on_redis_error() -> None:
    pool = ProxyPool(REDIS_URL)
    r = AsyncMock()
    r.llen.side_effect = ConnectionError("redis down")
    pool._redis = r

    proxy = await pool.get_proxy()

    assert proxy is None

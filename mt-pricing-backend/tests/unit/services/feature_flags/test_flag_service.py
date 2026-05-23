"""Unit tests para FlagService (cache Redis 60s + DB fallback)."""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import pytest

from app.services.feature_flags.flag_service import (
    CACHE_NS,
    CACHE_TTL_SECONDS,
    FLAG_KILL_SWITCH,
    FLAG_LIVE_NETWORK_AMAZON_UAE,
    KNOWN_FLAGS,
    FlagService,
    clear_local_cache,
    get_default_service,
    is_enabled,
    is_live_network_enabled,
    set_default_service,
    set_local_flag,
    warmup_local_cache,
)
from app.services.feature_flags.kill_switch import disengage, engage

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------
class _FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.set_calls: list[tuple[str, str, int | None]] = []
        self.delete_calls: list[str] = []

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        self.store[key] = value
        self.set_calls.append((key, value, ex))
        return True

    async def delete(self, *keys: str) -> int:
        n = 0
        for k in keys:
            if k in self.store:
                del self.store[k]
                n += 1
            self.delete_calls.append(k)
        return n


class _FakeRepo:
    def __init__(self) -> None:
        self.values: dict[str, bool] = {}
        self.upsert_calls: list[tuple[str, bool, UUID | None]] = []

    async def get_value(self, key: str) -> bool:
        return self.values.get(key, False)

    async def get(self, key: str) -> Any:
        if key not in self.values:
            return None

        class _Row:
            def __init__(self, k: str, v: bool) -> None:
                self.key = k
                self.value_jsonb = {"enabled": v}
                self.updated_by = None
                self.updated_at = None
                self.created_at = None

        return _Row(key, self.values[key])

    async def upsert(self, *, key: str, value: bool, updated_by: UUID | None = None) -> Any:
        self.values[key] = value
        self.upsert_calls.append((key, value, updated_by))
        return await self.get(key)


@pytest.fixture(autouse=True)
def _reset_singleton_state() -> None:
    """Limpia singleton + local cache + kill-switch entre tests."""
    set_default_service(None)
    clear_local_cache()
    disengage()
    yield
    set_default_service(None)
    clear_local_cache()
    disengage()


# ---------------------------------------------------------------------------
# Cache hit / miss / TTL
# ---------------------------------------------------------------------------
async def test_is_enabled_cache_miss_falls_back_to_db_and_caches() -> None:
    repo = _FakeRepo()
    redis = _FakeRedis()
    repo.values[FLAG_LIVE_NETWORK_AMAZON_UAE] = True

    svc = FlagService(flag_repo=repo, redis=redis)
    assert await svc.is_enabled(FLAG_LIVE_NETWORK_AMAZON_UAE) is True
    # Después del miss debe haber un SET con TTL 60s
    keys = [c[0] for c in redis.set_calls]
    assert f"{CACHE_NS}:{FLAG_LIVE_NETWORK_AMAZON_UAE}" in keys
    ttl = redis.set_calls[0][2]
    assert ttl == CACHE_TTL_SECONDS


async def test_is_enabled_cache_hit_skips_db() -> None:
    repo = _FakeRepo()
    redis = _FakeRedis()
    redis.store[f"{CACHE_NS}:{FLAG_LIVE_NETWORK_AMAZON_UAE}"] = "1"

    svc = FlagService(flag_repo=repo, redis=redis)
    assert await svc.is_enabled(FLAG_LIVE_NETWORK_AMAZON_UAE) is True
    assert repo.upsert_calls == []
    # No debería haber escrito el cache de nuevo.
    assert redis.set_calls == []


async def test_is_enabled_returns_false_for_unset_flag() -> None:
    repo = _FakeRepo()
    redis = _FakeRedis()
    svc = FlagService(flag_repo=repo, redis=redis)
    assert await svc.is_enabled(FLAG_LIVE_NETWORK_AMAZON_UAE) is False


async def test_set_flag_invalidates_cache_and_persists() -> None:
    repo = _FakeRepo()
    redis = _FakeRedis()
    redis.store[f"{CACHE_NS}:{FLAG_LIVE_NETWORK_AMAZON_UAE}"] = "0"

    svc = FlagService(flag_repo=repo, redis=redis)
    user_id = uuid4()
    out = await svc.set_flag(FLAG_LIVE_NETWORK_AMAZON_UAE, True, updated_by=user_id)
    assert out is True
    assert repo.upsert_calls == [(FLAG_LIVE_NETWORK_AMAZON_UAE, True, user_id)]
    assert f"{CACHE_NS}:{FLAG_LIVE_NETWORK_AMAZON_UAE}" in redis.delete_calls


async def test_set_flag_rejects_unknown_key() -> None:
    repo = _FakeRepo()
    redis = _FakeRedis()
    svc = FlagService(flag_repo=repo, redis=redis)
    with pytest.raises(ValueError):
        await svc.set_flag("UNKNOWN_FLAG", True)


async def test_get_all_returns_snapshot_for_all_known_flags() -> None:
    repo = _FakeRepo()
    repo.values[FLAG_LIVE_NETWORK_AMAZON_UAE] = True
    svc = FlagService(flag_repo=repo, redis=None)
    snap = await svc.get_all()
    assert set(snap.keys()) == set(KNOWN_FLAGS)
    assert snap[FLAG_LIVE_NETWORK_AMAZON_UAE] is True
    # Resto a False (no estaban en repo.values).
    for k, v in snap.items():
        if k != FLAG_LIVE_NETWORK_AMAZON_UAE:
            assert v is False


async def test_redis_failure_does_not_raise_falls_back_to_db() -> None:
    class _BrokenRedis:
        async def get(self, key: str) -> str | None:
            raise RuntimeError("redis dead")

        async def set(self, key: str, value: str, ex: int | None = None) -> bool:
            raise RuntimeError("redis dead")

        async def delete(self, *keys: str) -> int:
            raise RuntimeError("redis dead")

    repo = _FakeRepo()
    repo.values[FLAG_LIVE_NETWORK_AMAZON_UAE] = True
    svc = FlagService(flag_repo=repo, redis=_BrokenRedis())
    # Debe degradar gracefully — DB tiene la verdad.
    assert await svc.is_enabled(FLAG_LIVE_NETWORK_AMAZON_UAE) is True


# ---------------------------------------------------------------------------
# Sync helpers used by adapter registries
# ---------------------------------------------------------------------------
def test_is_enabled_sync_returns_false_when_no_service_bootstrapped() -> None:
    set_default_service(None)
    assert is_enabled(FLAG_LIVE_NETWORK_AMAZON_UAE) is False


def test_warmup_local_cache_powers_sync_lookup() -> None:
    repo = _FakeRepo()
    svc = FlagService(flag_repo=repo, redis=None)
    set_default_service(svc)
    warmup_local_cache({FLAG_LIVE_NETWORK_AMAZON_UAE: True})
    assert is_enabled(FLAG_LIVE_NETWORK_AMAZON_UAE) is True


def test_set_local_flag_overrides_for_test() -> None:
    repo = _FakeRepo()
    svc = FlagService(flag_repo=repo, redis=None)
    set_default_service(svc)
    set_local_flag(FLAG_LIVE_NETWORK_AMAZON_UAE, True)
    assert is_enabled(FLAG_LIVE_NETWORK_AMAZON_UAE) is True


def test_is_live_network_enabled_blocked_by_kill_switch() -> None:
    repo = _FakeRepo()
    svc = FlagService(flag_repo=repo, redis=None)
    set_default_service(svc)
    set_local_flag(FLAG_LIVE_NETWORK_AMAZON_UAE, True)
    assert is_live_network_enabled("AMAZON_UAE") is True
    engage()
    assert is_live_network_enabled("AMAZON_UAE") is False


def test_singleton_set_get_round_trip() -> None:
    repo = _FakeRepo()
    svc = FlagService(flag_repo=repo, redis=None)
    set_default_service(svc)
    assert get_default_service() is svc
    set_default_service(None)
    assert get_default_service() is None

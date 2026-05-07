"""Unit tests del kill-switch global (US-1A-09-08)."""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import pytest

from app.services.feature_flags.flag_service import (
    FLAG_KILL_SWITCH,
    FlagService,
    clear_local_cache,
    set_default_service,
)
from app.services.feature_flags.kill_switch import (
    KillSwitch,
    disengage,
    engage,
    is_kill_switch_engaged,
    reset,
)

pytestmark = pytest.mark.unit


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

    async def upsert(
        self, *, key: str, value: bool, updated_by: UUID | None = None
    ) -> Any:
        self.values[key] = value
        self.upsert_calls.append((key, value, updated_by))
        return await self.get(key)


@pytest.fixture(autouse=True)
def _reset_state() -> None:
    set_default_service(None)
    clear_local_cache()
    reset()
    yield
    set_default_service(None)
    clear_local_cache()
    reset()


# ---------------------------------------------------------------------------
# Atomic in-memory toggle
# ---------------------------------------------------------------------------
def test_initial_state_is_disengaged() -> None:
    assert is_kill_switch_engaged() is False


def test_engage_sets_flag_to_true() -> None:
    engage()
    assert is_kill_switch_engaged() is True


def test_disengage_resets() -> None:
    engage()
    disengage()
    assert is_kill_switch_engaged() is False


def test_engage_is_idempotent() -> None:
    engage()
    engage()
    assert is_kill_switch_engaged() is True


# ---------------------------------------------------------------------------
# Persistent wrapper over FlagService
# ---------------------------------------------------------------------------
async def test_kill_switch_engage_persists_and_sets_memory() -> None:
    repo = _FakeRepo()
    svc = FlagService(flag_repo=repo, redis=None)
    ks = KillSwitch(svc)

    user = uuid4()
    await ks.engage(updated_by=user, reason="incident-001")
    assert is_kill_switch_engaged() is True
    assert repo.upsert_calls == [(FLAG_KILL_SWITCH, True, user)]


async def test_kill_switch_disengage_persists_and_clears_memory() -> None:
    repo = _FakeRepo()
    svc = FlagService(flag_repo=repo, redis=None)
    ks = KillSwitch(svc)
    await ks.engage()
    await ks.disengage(reason="recovery")
    assert is_kill_switch_engaged() is False
    # Dos upserts: True luego False.
    assert [(c[0], c[1]) for c in repo.upsert_calls] == [
        (FLAG_KILL_SWITCH, True),
        (FLAG_KILL_SWITCH, False),
    ]


async def test_hydrate_from_db_engages_when_persisted_true() -> None:
    repo = _FakeRepo()
    repo.values[FLAG_KILL_SWITCH] = True
    svc = FlagService(flag_repo=repo, redis=None)
    ks = KillSwitch(svc)
    assert is_kill_switch_engaged() is False
    await ks.hydrate_from_db()
    assert is_kill_switch_engaged() is True


async def test_hydrate_from_db_disengages_when_persisted_false() -> None:
    repo = _FakeRepo()
    repo.values[FLAG_KILL_SWITCH] = False
    svc = FlagService(flag_repo=repo, redis=None)
    ks = KillSwitch(svc)
    engage()  # estado memoria pre-existente
    await ks.hydrate_from_db()
    assert is_kill_switch_engaged() is False


async def test_hydrate_from_db_swallows_db_errors() -> None:
    class _BrokenRepo:
        async def get_value(self, key: str) -> bool:
            raise RuntimeError("db down")

        async def get(self, key: str) -> Any:
            return None

        async def upsert(self, **kwargs: Any) -> Any:
            return None

    svc = FlagService(flag_repo=_BrokenRepo(), redis=None)
    ks = KillSwitch(svc)
    # No debería raisar — sólo loggear.
    await ks.hydrate_from_db()
    assert is_kill_switch_engaged() is False

"""Unit tests para `app.workers.tasks.pricing_recalc` (US-1B-01-07).

Sin Celery worker — invocamos la coroutine inner via monkeypatch del
sessionmaker y service.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

pytestmark = pytest.mark.unit


def _mk_user() -> Any:
    user = MagicMock()
    user.id = uuid4()
    user.email = "system@mt.ae"
    return user


# ---------------------------------------------------------------------------
# Task registration smoke
# ---------------------------------------------------------------------------
def test_task_registered_with_correct_name_and_queue() -> None:
    from app.workers.tasks.pricing_recalc import bulk_recalc_task

    assert bulk_recalc_task.name == "mt.pricing.bulk_recalc"
    # Routing por queue: ``mt.pricing.*`` → "pricing".
    queue = getattr(bulk_recalc_task, "queue", None) or bulk_recalc_task.app.conf.task_routes.get(
        "mt.pricing.bulk_recalc", {}
    ).get("queue")
    # El decorator @celery_app.task(queue="pricing") setea el binding directo.
    # Algunas versiones de Celery no exponen `task.queue`; verificamos via
    # router fallback (regex sobre task name → queue 'pricing').
    routes = bulk_recalc_task.app.conf.task_routes
    assert routes.get("mt.pricing.*", {}).get("queue") == "pricing" or queue == "pricing"


# ---------------------------------------------------------------------------
# Inner coroutine — patched session + service
# ---------------------------------------------------------------------------
def test_inner_run_resolves_actor_and_calls_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reemplaza get_sessionmaker + BulkRecalcService + _resolve_actor.

    Test síncrono: ``bulk_recalc_task.run`` usa internamente
    ``loop.run_until_complete``; no podemos llamarlo desde un test async.
    """
    from app.workers.tasks import pricing_recalc as task_mod

    actor = _mk_user()

    async def _fake_resolve_actor(_session: Any) -> Any:
        return actor

    monkeypatch.setattr(task_mod, "_resolve_actor", _fake_resolve_actor)

    fake_session = MagicMock()
    fake_session.commit = AsyncMock()
    fake_session.rollback = AsyncMock()

    class _FakeCM:
        async def __aenter__(self) -> Any:
            return fake_session

        async def __aexit__(self, *exc: Any) -> None:
            return None

    class _FakeMaker:
        def __call__(self) -> _FakeCM:
            return _FakeCM()

    def _fake_get_sessionmaker() -> _FakeMaker:
        return _FakeMaker()

    # patch the symbol used inside the task closure
    import app.db.engine as engine_mod

    monkeypatch.setattr(engine_mod, "get_sessionmaker", _fake_get_sessionmaker)

    # Patch BulkRecalcService.run en el módulo del servicio
    import app.services.pricing.bulk_recalc_service as svc_mod

    fake_result = MagicMock()
    fake_result.to_dict = MagicMock(
        return_value={"skus_total": 3, "skus_processed": 3, "skus_failed": 0}
    )
    fake_run = AsyncMock(return_value=fake_result)
    monkeypatch.setattr(svc_mod.BulkRecalcService, "run", fake_run, raising=True)

    out = task_mod.bulk_recalc_task.run("nightly_beat")
    assert out["skus_total"] == 3
    assert out["skus_processed"] == 3
    fake_run.assert_awaited_once()
    fake_session.commit.assert_awaited_once()


def test_inner_run_returns_skipped_when_no_actor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sync test — ver razón en `test_inner_run_resolves_actor_and_calls_service`."""
    from app.workers.tasks import pricing_recalc as task_mod

    async def _fake_resolve_actor(_session: Any) -> Any:
        return None

    monkeypatch.setattr(task_mod, "_resolve_actor", _fake_resolve_actor)

    fake_session = MagicMock()
    fake_session.commit = AsyncMock()
    fake_session.rollback = AsyncMock()

    class _FakeCM:
        async def __aenter__(self) -> Any:
            return fake_session

        async def __aexit__(self, *exc: Any) -> None:
            return None

    class _FakeMaker:
        def __call__(self) -> _FakeCM:
            return _FakeCM()

    import app.db.engine as engine_mod

    monkeypatch.setattr(engine_mod, "get_sessionmaker", lambda: _FakeMaker())

    out = task_mod.bulk_recalc_task.run("nightly_beat")
    assert out["skipped"] is True
    assert out["skip_reason"] == "no_system_actor"


# ---------------------------------------------------------------------------
# Mutex helper
# ---------------------------------------------------------------------------
async def test_acquire_mutex_returns_true_when_redis_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Si get_redis no está disponible o falla, mutex defaultea a True (no-op)."""
    from app.workers.tasks import pricing_recalc as task_mod

    # Monkeypatch para forzar excepción dentro de _acquire_mutex
    import app.core.redis as redis_mod

    def _boom() -> Any:
        raise RuntimeError("redis offline")

    monkeypatch.setattr(redis_mod, "get_redis", _boom)
    result = await task_mod._acquire_mutex()
    assert result is True


async def test_acquire_mutex_returns_false_when_lock_held(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.workers.tasks import pricing_recalc as task_mod

    fake_redis = MagicMock()
    fake_redis.get = AsyncMock(return_value="locked-by-manual")

    import app.core.redis as redis_mod

    monkeypatch.setattr(redis_mod, "get_redis", lambda: fake_redis)
    result = await task_mod._acquire_mutex()
    assert result is False


async def test_acquire_mutex_returns_true_when_no_lock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.workers.tasks import pricing_recalc as task_mod

    fake_redis = MagicMock()
    fake_redis.get = AsyncMock(return_value=None)

    import app.core.redis as redis_mod

    monkeypatch.setattr(redis_mod, "get_redis", lambda: fake_redis)
    result = await task_mod._acquire_mutex()
    assert result is True

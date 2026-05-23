"""Unit tests para `app.services.pricing.bulk_publish_service` (US-1B-01-04).

Estrategia:
- PricingService mockeado (Protocol) → no toca DB.
- AuditRepository real pero con session mock que captura los add() calls.
- Verifica counts, queue_publisher accept/reject, rollback_on_error.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from app.services.pricing.bulk_publish_service import BulkPublishService
from app.services.pricing.pricing_service import PricingDomainError

pytestmark = pytest.mark.unit


def _mk_user() -> Any:
    user = MagicMock()
    user.id = uuid4()
    user.email = "tester@mt.ae"
    return user


def _mk_session() -> MagicMock:
    """Sesión mock: add/flush son no-op; tracker accesible vía mock."""
    sess = MagicMock()
    sess.add = MagicMock()
    sess.flush = AsyncMock()
    return sess


def _mk_price(*, status: str = "exported") -> Any:
    p = MagicMock()
    p.id = uuid4()
    p.status = status
    return p


async def test_publish_empty_returns_zero() -> None:
    sess = _mk_session()
    pricing = MagicMock()
    pricing.export = AsyncMock()
    svc = BulkPublishService(sess, pricing_service=pricing)
    res = await svc.publish([], _mk_user())
    assert res.total == 0
    assert res.published == []
    pricing.export.assert_not_awaited()


async def test_publish_all_succeed() -> None:
    sess = _mk_session()
    pricing = MagicMock()
    p1 = _mk_price()
    p2 = _mk_price()
    pricing.export = AsyncMock(side_effect=[p1, p2])
    svc = BulkPublishService(sess, pricing_service=pricing)
    res = await svc.publish([uuid4(), uuid4()], _mk_user())
    assert res.total == 2
    assert len(res.published) == 2
    assert str(p1.id) in res.published
    assert str(p2.id) in res.published
    assert res.errors == []
    assert res.queue_failed == []
    assert res.rolled_back is False


async def test_publish_continues_on_domain_error() -> None:
    sess = _mk_session()
    pricing = MagicMock()
    p_ok = _mk_price()
    pricing.export = AsyncMock(
        side_effect=[
            PricingDomainError("invalid_transition", "x", 409),
            p_ok,
        ]
    )
    svc = BulkPublishService(sess, pricing_service=pricing)
    res = await svc.publish([uuid4(), uuid4()], _mk_user())
    assert res.total == 2
    assert len(res.published) == 1
    assert len(res.errors) == 1
    assert res.errors[0]["code"] == "invalid_transition"
    assert res.rolled_back is False


async def test_publish_rolls_back_on_first_domain_error() -> None:
    sess = _mk_session()
    pricing = MagicMock()
    pricing.export = AsyncMock(side_effect=[PricingDomainError("foo", "bar", 409)])
    svc = BulkPublishService(sess, pricing_service=pricing)
    res = await svc.publish([uuid4(), uuid4()], _mk_user(), rollback_on_error=True)
    # Sólo se intenta el primero porque rollback corta.
    assert res.rolled_back is True
    assert len(res.errors) == 1
    assert res.published == []
    assert pricing.export.await_count == 1


async def test_publish_queue_publisher_accept() -> None:
    sess = _mk_session()
    pricing = MagicMock()
    p1 = _mk_price()
    pricing.export = AsyncMock(return_value=p1)

    queue_mock = AsyncMock(return_value=True)
    svc = BulkPublishService(sess, pricing_service=pricing, queue_publisher=queue_mock)
    res = await svc.publish([uuid4()], _mk_user())
    assert len(res.published) == 1
    queue_mock.assert_awaited_once_with(p1.id)


async def test_publish_queue_publisher_rejects() -> None:
    sess = _mk_session()
    pricing = MagicMock()
    p1 = _mk_price()
    pricing.export = AsyncMock(return_value=p1)
    queue_mock = AsyncMock(return_value=False)
    svc = BulkPublishService(sess, pricing_service=pricing, queue_publisher=queue_mock)
    res = await svc.publish([uuid4()], _mk_user())
    assert res.published == []
    assert len(res.queue_failed) == 1
    assert res.queue_failed[0]["reason"] == "queue_rejected"


async def test_publish_queue_publisher_raises() -> None:
    sess = _mk_session()
    pricing = MagicMock()
    p1 = _mk_price()
    pricing.export = AsyncMock(return_value=p1)
    queue_mock = AsyncMock(side_effect=RuntimeError("boom"))
    svc = BulkPublishService(sess, pricing_service=pricing, queue_publisher=queue_mock)
    res = await svc.publish([uuid4()], _mk_user())
    assert res.published == []
    assert len(res.queue_failed) == 1
    assert res.queue_failed[0]["reason"] == "queue_exception"


async def test_publish_unexpected_exception_recorded() -> None:
    sess = _mk_session()
    pricing = MagicMock()
    pricing.export = AsyncMock(side_effect=RuntimeError("oops"))
    svc = BulkPublishService(sess, pricing_service=pricing)
    res = await svc.publish([uuid4()], _mk_user())
    assert res.published == []
    assert len(res.errors) == 1
    assert res.errors[0]["code"] == "internal_error"
    assert "RuntimeError" in res.errors[0]["message"]


async def test_publish_to_dict_serializable() -> None:
    sess = _mk_session()
    pricing = MagicMock()
    p1 = _mk_price()
    pricing.export = AsyncMock(return_value=p1)
    svc = BulkPublishService(sess, pricing_service=pricing)
    res = await svc.publish([uuid4()], _mk_user())
    d = res.to_dict()
    assert d["published_count"] == 1
    assert d["total"] == 1
    assert d["rolled_back"] is False
    assert isinstance(d["published"], list)

"""Unit tests del router `app.api.routes.pricing_engine` (US-1B-01-04).

Sin DB ni JWT — overrides de get_db_session, get_current_user,
require_permissions, get_bulk_publish_service, get_revise_service.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_user, get_db_session, require_permissions
from app.api.routes.pricing_engine import (
    get_bulk_publish_service,
    get_revise_service,
    router as pricing_engine_router,
)
from app.services.pricing.bulk_publish_service import BulkPublishResult
from app.services.pricing.pricing_service import PricingDomainError
from app.services.pricing.revise_service import (
    CounterProposalResult,
)

pytestmark = pytest.mark.unit


class _FakeRole:
    def __init__(self, perms: list[str]) -> None:
        self.code = "tester"
        self.permissions_snapshot = perms


class _FakeUser:
    def __init__(self) -> None:
        self.id: UUID = uuid4()
        self.email = "tester@mt.ae"
        self.is_active = True
        self.role = _FakeRole(
            ["prices:export", "prices:propose", "prices:read", "prices:approve"]
        )


def _build_app(
    *, bulk_service: Any = None, revise_service: Any = None
) -> tuple[FastAPI, _FakeUser]:
    app = FastAPI()
    app.include_router(pricing_engine_router, prefix="/api/v1")

    user = _FakeUser()

    async def _override_db():  # pragma: no cover  — no toca DB
        yield None

    async def _override_user():
        return user

    def _override_perms_factory(*_codes: str):
        async def _ok():
            return user

        return _ok

    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_current_user] = _override_user
    if bulk_service is not None:
        app.dependency_overrides[get_bulk_publish_service] = lambda: bulk_service
    if revise_service is not None:
        app.dependency_overrides[get_revise_service] = lambda: revise_service

    for route in app.routes:
        if hasattr(route, "dependant"):
            for dep in route.dependant.dependencies:
                if dep.call is None:
                    continue
                fn = dep.call
                if (
                    fn.__module__ == require_permissions.__module__
                    and fn.__qualname__.startswith("require_permissions.")
                ):
                    app.dependency_overrides[fn] = _override_perms_factory()

    return app, user


# ---------------------------------------------------------------------------
# bulk-publish
# ---------------------------------------------------------------------------
async def test_bulk_publish_happy() -> None:
    bulk = MagicMock()
    pid = uuid4()
    bulk.publish = AsyncMock(
        return_value=BulkPublishResult(total=1, published=[str(pid)])
    )
    app, _ = _build_app(bulk_service=bulk)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as cli:
        resp = await cli.post(
            "/api/v1/pricing/prices/bulk-publish",
            json={"price_ids": [str(pid)]},
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 1
    assert body["published_count"] == 1
    assert body["rolled_back"] is False


async def test_bulk_publish_with_errors_no_rollback() -> None:
    bulk = MagicMock()
    bulk.publish = AsyncMock(
        return_value=BulkPublishResult(
            total=2,
            published=[str(uuid4())],
            errors=[{"price_id": str(uuid4()), "code": "invalid_transition", "message": "x"}],
        )
    )
    app, _ = _build_app(bulk_service=bulk)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as cli:
        resp = await cli.post(
            "/api/v1/pricing/prices/bulk-publish",
            json={
                "price_ids": [str(uuid4()), str(uuid4())],
                "rollback_on_error": False,
            },
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["published_count"] == 1
    assert len(body["errors"]) == 1


async def test_bulk_publish_validation_empty_list_422() -> None:
    bulk = MagicMock()
    bulk.publish = AsyncMock()
    app, _ = _build_app(bulk_service=bulk)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as cli:
        resp = await cli.post(
            "/api/v1/pricing/prices/bulk-publish",
            json={"price_ids": []},
        )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# revise-counter
# ---------------------------------------------------------------------------
async def test_revise_counter_happy() -> None:
    rev = MagicMock()
    pid = uuid4()
    rev.revise_with_counter = AsyncMock(
        return_value=CounterProposalResult(
            price_id=str(pid),
            new_amount="120",
            old_amount="100",
            margin_pct="0.30",
            reason="negociado",
            status_after="revised",
        )
    )
    app, _ = _build_app(revise_service=rev)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as cli:
        resp = await cli.post(
            f"/api/v1/pricing/prices/{pid}/revise-counter",
            json={"new_amount": "120", "reason": "negociado"},
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["new_amount"] == "120"
    assert body["status_after"] == "revised"


async def test_revise_counter_domain_error_409() -> None:
    rev = MagicMock()
    pid = uuid4()
    rev.revise_with_counter = AsyncMock(
        side_effect=PricingDomainError("invalid_transition", "x", 409)
    )
    app, _ = _build_app(revise_service=rev)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as cli:
        resp = await cli.post(
            f"/api/v1/pricing/prices/{pid}/revise-counter",
            json={"new_amount": "120", "reason": "negociado"},
        )
    assert resp.status_code == 409
    body = resp.json()
    assert body["detail"]["code"] == "invalid_transition"


async def test_revise_counter_validation_invalid_amount() -> None:
    rev = MagicMock()
    rev.revise_with_counter = AsyncMock()
    app, _ = _build_app(revise_service=rev)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as cli:
        resp = await cli.post(
            f"/api/v1/pricing/prices/{uuid4()}/revise-counter",
            json={"new_amount": "-5", "reason": "x"},
        )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# recalc-batch
# ---------------------------------------------------------------------------
async def test_recalc_batch_queues_tasks(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mockea `recalculate_sku_task.delay` para evitar Celery."""
    from app.workers.tasks import pricing as pricing_tasks

    fake_task = MagicMock()
    fake_task.delay = MagicMock(return_value=MagicMock(id="task-1"))
    monkeypatch.setattr(
        pricing_tasks, "recalculate_sku_task", fake_task, raising=True
    )

    app, _ = _build_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as cli:
        resp = await cli.post(
            "/api/v1/pricing/prices/recalc-batch",
            json={"skus": ["MT-V-001", "MT-V-002"], "trigger": "fx_change"},
        )
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["skus_queued"] == 2
    assert body["trigger"] == "fx_change"
    assert fake_task.delay.call_count == 2

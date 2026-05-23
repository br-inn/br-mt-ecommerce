"""Unit tests del router `app.api.routes.costs` (sin DB ni JWT real).

Estrategia (igual a test_matches_api.py):
- Monta una FastAPI ad-hoc con `costs.router` + `products_costs_router`.
- Override `get_cost_service` con un fake que registra llamadas in-memory.
- Override `require_permissions(...)` recorriendo dependencies del router.

Cobertura (US-1A-04-03):
- POST /costs 201 con cost+warnings.
- POST /costs 422 si breakdown required missing.
- POST /costs 422 si FX missing at effective_at.
- PUT /costs/{id} versionado → version+1.
- PUT /costs/{id} 404 si cost no existe.
- GET /products/{sku}/costs lista activos.
- GET /costs/missing?scheme_code=FBA lista SKUs huérfanos.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_user, get_db_session
from app.api.routes.costs import (
    get_cost_service,
    products_costs_router,
    router as costs_router,
)
from app.services.costs.breakdown_validator import MissingRequiredField
from app.services.costs.cost_service import (
    CostNotFound,
    CreateCostResult,
    FXRateNotFoundAtEffectiveAt,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------
class _FakeCost:
    def __init__(self, **kw: Any) -> None:
        self.id: UUID = kw.get("id", uuid4())
        self.sku: str = kw.get("sku", "MT-V-038")
        self.scheme_code: str = kw.get("scheme_code", "FBA")
        self.supplier_code: str | None = kw.get("supplier_code")
        self.currency_origin: str = kw.get("currency_origin", "EUR")
        self.fx_rate_id: UUID | None = kw.get("fx_rate_id")
        self.effective_at: datetime = kw.get(
            "effective_at", datetime(2026, 6, 12, tzinfo=timezone.utc)
        )
        self.breakdown: dict[str, Any] = kw.get("breakdown", {})
        self.scheme_landed_aed: Decimal | None = kw.get("scheme_landed_aed", Decimal("60.918"))
        self.status: str = kw.get("status", "active")
        self.version: int = kw.get("version", 1)
        self.fx_inferred: bool = kw.get("fx_inferred", False)
        self.created_by: UUID | None = kw.get("created_by")
        self.updated_by: UUID | None = kw.get("updated_by")
        now = datetime.now(tz=timezone.utc)
        self.created_at = kw.get("created_at", now)
        self.updated_at = kw.get("updated_at", now)


class _FakeCostService:
    """Implementación in-memory que cumple la API que el router consume.

    Reglas en los tests:
    - `behavior` configura comportamientos específicos: 'missing_required',
      'fx_missing', 'cost_not_found' o None (success).
    """

    def __init__(self) -> None:
        self.created: list[dict[str, Any]] = []
        self.updated: list[dict[str, Any]] = []
        self.costs: dict[UUID, _FakeCost] = {}
        self.behavior: str | None = None

    async def create_cost(self, **kw: Any) -> CreateCostResult:
        if self.behavior == "missing_required":
            raise MissingRequiredField("fob_eur")
        if self.behavior == "fx_missing":
            raise FXRateNotFoundAtEffectiveAt("No FX rate for EUR -> AED at 2026-06-12")
        cost = _FakeCost(
            sku=kw["sku"],
            scheme_code=kw["scheme_code"],
            supplier_code=kw.get("supplier_code"),
            currency_origin=kw["currency_origin"],
            effective_at=kw["effective_at"],
            breakdown=kw["breakdown"],
            version=1,
        )
        self.costs[cost.id] = cost
        self.created.append(kw)
        warnings: list[dict[str, str]] = []
        if "weird_extra" in kw["breakdown"]:
            warnings.append({"code": "unknown_breakdown_field", "field": "weird_extra"})
        return CreateCostResult(cost=cost, warnings=warnings)

    async def update_cost(self, cost_id: UUID, **kw: Any) -> CreateCostResult:
        if self.behavior == "cost_not_found":
            raise CostNotFound(str(cost_id))
        prev = self.costs.get(cost_id)
        if prev is None:
            raise CostNotFound(str(cost_id))
        prev.status = "superseded"
        new = _FakeCost(
            sku=prev.sku,
            scheme_code=prev.scheme_code,
            supplier_code=prev.supplier_code,
            currency_origin=kw.get("currency_origin") or prev.currency_origin,
            effective_at=kw.get("effective_at") or prev.effective_at,
            breakdown=kw.get("breakdown") or prev.breakdown,
            version=prev.version + 1,
        )
        self.costs[new.id] = new
        self.updated.append({"id": str(cost_id), **kw})
        return CreateCostResult(cost=new, warnings=[])

    async def list_for_sku(self, sku: str, *, only_active: bool = False) -> list[_FakeCost]:
        out = [c for c in self.costs.values() if c.sku == sku]
        if only_active:
            out = [c for c in out if c.status == "active"]
        return out

    async def missing_cost_skus(self, scheme_code: str, *, limit: int = 1000) -> list[str]:
        return ["MT-V-001", "MT-V-002"]


class _FakeRole:
    def __init__(self, perms: list[str]) -> None:
        self.code = "tester"
        self.permissions_snapshot = perms


class _FakeUser:
    def __init__(self) -> None:
        self.id: UUID = uuid4()
        self.email = "tester@mt.ae"
        self.is_active = True
        self.role = _FakeRole(["costs:read", "costs:write"])


# ---------------------------------------------------------------------------
# App builder — override deps at router level (mirrors test_matches_api.py)
# ---------------------------------------------------------------------------
def _build_app(svc: _FakeCostService, user: _FakeUser) -> FastAPI:
    app = FastAPI()
    app.include_router(costs_router, prefix="/api/v1")
    app.include_router(products_costs_router, prefix="/api/v1")

    async def _override_db():  # pragma: no cover
        yield None

    async def _override_user():
        return user

    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_cost_service] = lambda: svc

    # Walk through router routes and override require_permissions(...) closures.
    for r in (*costs_router.routes, *products_costs_router.routes):
        dependant = getattr(r, "dependant", None)
        if dependant is None:
            continue
        for dep in dependant.dependencies:
            call = dep.call
            if call is not None and getattr(call, "__name__", "") == "_check":

                async def _allow(_call=call):  # noqa: ARG001
                    return user

                app.dependency_overrides[call] = _allow

    return app


async def _client(app: FastAPI) -> AsyncClient:
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://testserver")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
async def test_post_costs_returns_201_with_cost_and_warnings() -> None:
    svc = _FakeCostService()
    user = _FakeUser()
    app = _build_app(svc, user)
    payload = {
        "sku": "MT-V-038",
        "scheme_code": "FBA",
        "supplier_code": "MT_VALVES_ES",
        "currency_origin": "EUR",
        "effective_at": "2026-06-12T00:00:00Z",
        "breakdown": {"fob_eur": 12.40, "freight_eur": 1.80, "weird_extra": 5.0},
    }
    async with await _client(app) as ac:
        resp = await ac.post("/api/v1/costs", json=payload)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["cost"]["sku"] == "MT-V-038"
    assert body["cost"]["scheme_code"] == "FBA"
    assert body["cost"]["currency_origin"] == "EUR"
    assert body["cost"]["status"] == "active"
    assert body["cost"]["version"] == 1
    # Legacy aliases also present.
    assert body["cost"]["product_sku"] == "MT-V-038"
    assert body["cost"]["currency"] == "EUR"
    # Warning emitted for unknown field.
    assert any(w["field"] == "weird_extra" for w in body["warnings"])


async def test_post_costs_422_missing_required_breakdown_field() -> None:
    svc = _FakeCostService()
    svc.behavior = "missing_required"
    user = _FakeUser()
    app = _build_app(svc, user)
    payload = {
        "sku": "MT-V-038",
        "scheme_code": "FBA",
        "currency_origin": "EUR",
        "effective_at": "2026-06-12T00:00:00Z",
        "breakdown": {},
    }
    async with await _client(app) as ac:
        resp = await ac.post("/api/v1/costs", json=payload)
    assert resp.status_code == 422
    body = resp.json()
    assert body["detail"]["code"] == "missing_required_breakdown_field"
    assert body["detail"]["field"] == "fob_eur"


async def test_post_costs_422_when_fx_rate_missing_at_effective_at() -> None:
    svc = _FakeCostService()
    svc.behavior = "fx_missing"
    user = _FakeUser()
    app = _build_app(svc, user)
    payload = {
        "sku": "MT-V-038",
        "scheme_code": "FBA",
        "currency_origin": "EUR",
        "effective_at": "2026-06-12T00:00:00Z",
        "breakdown": {"fob_eur": 12.40},
    }
    async with await _client(app) as ac:
        resp = await ac.post("/api/v1/costs", json=payload)
    assert resp.status_code == 422
    body = resp.json()
    assert body["detail"]["code"] == "fx_rate_not_found_at_effective_at"


async def test_put_costs_versions_correctly_status_superseded_then_active() -> None:
    svc = _FakeCostService()
    user = _FakeUser()
    # Pre-seed an active cost.
    cost = _FakeCost(version=1, status="active")
    svc.costs[cost.id] = cost
    app = _build_app(svc, user)
    payload = {
        "breakdown": {"fob_eur": 13.00, "freight_eur": 1.80},
        "effective_at": "2026-07-01T00:00:00Z",
    }
    async with await _client(app) as ac:
        resp = await ac.put(f"/api/v1/costs/{cost.id}", json=payload)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["cost"]["version"] == 2
    assert body["cost"]["status"] == "active"
    # Previous one is now superseded.
    assert svc.costs[cost.id].status == "superseded"


async def test_put_costs_404_when_id_unknown() -> None:
    svc = _FakeCostService()
    svc.behavior = "cost_not_found"
    user = _FakeUser()
    app = _build_app(svc, user)
    async with await _client(app) as ac:
        resp = await ac.put(f"/api/v1/costs/{uuid4()}", json={"breakdown": {"fob_eur": 1}})
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "cost_not_found"


async def test_get_products_sku_costs_lists_active() -> None:
    svc = _FakeCostService()
    user = _FakeUser()
    cost1 = _FakeCost(sku="MT-V-038", scheme_code="FBA")
    cost2 = _FakeCost(sku="MT-V-038", scheme_code="DIRECT_B2C")
    cost3 = _FakeCost(sku="MT-V-038", scheme_code="FBM", status="superseded")
    for c in (cost1, cost2, cost3):
        svc.costs[c.id] = c
    app = _build_app(svc, user)
    async with await _client(app) as ac:
        resp = await ac.get("/api/v1/products/MT-V-038/costs?only_active=true")
    assert resp.status_code == 200, resp.text
    items = resp.json()
    assert len(items) == 2
    schemes = {it["scheme_code"] for it in items}
    assert schemes == {"FBA", "DIRECT_B2C"}


async def test_get_costs_missing_returns_orphan_skus() -> None:
    svc = _FakeCostService()
    user = _FakeUser()
    app = _build_app(svc, user)
    async with await _client(app) as ac:
        resp = await ac.get("/api/v1/costs/missing?scheme_code=FBA")
    assert resp.status_code == 200, resp.text
    items = resp.json()
    assert {it["sku"] for it in items} == {"MT-V-001", "MT-V-002"}

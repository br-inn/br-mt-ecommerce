"""Unit tests del router `app.api.routes.costs` (sin DB ni JWT real).

Estrategia (igual a test_matches_api.py):
- Monta una FastAPI ad-hoc con `costs.router` + `products_costs_router`.
- Override `get_cost_service` con un fake que registra llamadas in-memory.
- Override `require_permissions(...)` recorriendo dependencies del router.

Contrato NUEVO (vigencia por rangos — US-1A-04-03):
- POST /costs usa `valid_from: date` (no `effective_at`); schema `extra="forbid"`.
- PUT /costs/{id} corrige IN-PLACE la MISMA fila (no versiona ni supersede).
- `status` es un hybrid derivado: `valid_to IS NULL` ⇒ "active".
- Solape de rangos ⇒ 409 `cost_range_overlap`.

Cobertura:
- POST /costs 201 con cost+warnings.
- POST /costs 422 si breakdown required missing.
- POST /costs 422 si FX missing at valid_from.
- POST /costs 409 si el rango solapa otro existente.
- PUT /costs/{id} corrección in-place → misma fila, sigue active.
- PUT /costs/{id} 404 si cost no existe.
- GET /products/{sku}/costs lista vigentes.
- GET /costs/missing?scheme_code=FBA lista SKUs huérfanos.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_user, get_db_session
from app.api.routes.costs import (
    get_cost_service,
    products_costs_router,
)
from app.api.routes.costs import (
    router as costs_router,
)
from app.services.costs.breakdown_validator import MissingRequiredField
from app.services.costs.cost_service import (
    CostNotFound,
    CostRangeOverlap,
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
        self.valid_from: date = kw.get("valid_from", date(2026, 6, 12))
        self.valid_to: date | None = kw.get("valid_to")
        self.breakdown: dict[str, Any] = kw.get("breakdown", {})
        self.scheme_landed_aed: Decimal | None = kw.get("scheme_landed_aed", Decimal("60.918"))
        self.version: int = kw.get("version", 1)
        self.fx_inferred: bool = kw.get("fx_inferred", False)
        self.created_by: UUID | None = kw.get("created_by")
        self.updated_by: UUID | None = kw.get("updated_by")
        now = datetime.now(tz=UTC)
        self.created_at = kw.get("created_at", now)
        self.updated_at = kw.get("updated_at", now)

    @property
    def status(self) -> str:
        """Hybrid derivado: rango abierto (valid_to NULL) ⇒ active."""
        return "active" if self.valid_to is None else "superseded"


class _FakeCostService:
    """Implementación in-memory que cumple la API que el router consume.

    Reglas en los tests:
    - `behavior` configura comportamientos específicos: 'missing_required',
      'fx_missing', 'cost_not_found', 'overlap' o None (success).
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
        if self.behavior == "overlap":
            raise CostRangeOverlap("MT-V-038/FBA range overlap")
        cost = _FakeCost(
            sku=kw["sku"],
            scheme_code=kw["scheme_code"],
            supplier_code=kw.get("supplier_code"),
            currency_origin=kw["currency_origin"],
            valid_from=kw["valid_from"],
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
        if self.behavior == "overlap":
            raise CostRangeOverlap("MT-V-038/FBA range overlap")
        cost = self.costs.get(cost_id)
        if cost is None:
            raise CostNotFound(str(cost_id))
        # Corrección IN-PLACE: muta la MISMA fila (no versiona ni supersede).
        if kw.get("breakdown") is not None:
            cost.breakdown = kw["breakdown"]
        if kw.get("valid_from") is not None:
            cost.valid_from = kw["valid_from"]
        if kw.get("currency_origin") is not None:
            cost.currency_origin = kw["currency_origin"]
        self.updated.append({"id": str(cost_id), **kw})
        return CreateCostResult(cost=cost, warnings=[])

    async def list_for_sku(
        self, sku: str, *, only_active: bool = False, as_of: date | None = None
    ) -> list[_FakeCost]:
        out = [c for c in self.costs.values() if c.sku == sku]
        if only_active:
            out = [c for c in out if c.valid_to is None]
        return out

    async def missing_cost_skus(
        self, scheme_code: str, *, as_of: date | None = None, limit: int = 1000
    ) -> list[str]:
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

                async def _allow(_call=call):
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
        "valid_from": "2026-06-12",
        "breakdown": {"fob_eur": 12.40, "freight_eur": 1.80, "weird_extra": 5.0},
    }
    async with await _client(app) as ac:
        resp = await ac.post("/api/v1/costs", json=payload)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["cost"]["sku"] == "MT-V-038"
    assert body["cost"]["scheme_code"] == "FBA"
    assert body["cost"]["currency_origin"] == "EUR"
    # Rango abierto ⇒ vigente (status hybrid derivado).
    assert body["cost"]["valid_from"] == "2026-06-12"
    assert body["cost"]["valid_to"] is None
    assert body["cost"]["status"] == "active"
    assert body["cost"]["version"] == 1
    # Legacy aliases also present.
    assert body["cost"]["product_sku"] == "MT-V-038"
    assert body["cost"]["currency"] == "EUR"
    # Warning emitted for unknown field.
    assert any(w["field"] == "weird_extra" for w in body["warnings"])
    # El service recibió valid_from (no effective_at).
    assert svc.created[0]["valid_from"] == date(2026, 6, 12)


async def test_post_costs_422_missing_required_breakdown_field() -> None:
    svc = _FakeCostService()
    svc.behavior = "missing_required"
    user = _FakeUser()
    app = _build_app(svc, user)
    payload = {
        "sku": "MT-V-038",
        "scheme_code": "FBA",
        "currency_origin": "EUR",
        "valid_from": "2026-06-12",
        "breakdown": {},
    }
    async with await _client(app) as ac:
        resp = await ac.post("/api/v1/costs", json=payload)
    assert resp.status_code == 422
    body = resp.json()
    assert body["detail"]["code"] == "missing_required_breakdown_field"
    assert body["detail"]["field"] == "fob_eur"


async def test_post_costs_422_when_fx_rate_missing_at_valid_from() -> None:
    svc = _FakeCostService()
    svc.behavior = "fx_missing"
    user = _FakeUser()
    app = _build_app(svc, user)
    payload = {
        "sku": "MT-V-038",
        "scheme_code": "FBA",
        "currency_origin": "EUR",
        "valid_from": "2026-06-12",
        "breakdown": {"fob_eur": 12.40},
    }
    async with await _client(app) as ac:
        resp = await ac.post("/api/v1/costs", json=payload)
    assert resp.status_code == 422
    body = resp.json()
    assert body["detail"]["code"] == "fx_rate_not_found_at_effective_at"


async def test_post_costs_409_when_range_overlaps() -> None:
    svc = _FakeCostService()
    svc.behavior = "overlap"
    user = _FakeUser()
    app = _build_app(svc, user)
    payload = {
        "sku": "MT-V-038",
        "scheme_code": "FBA",
        "currency_origin": "EUR",
        "valid_from": "2026-06-12",
        "breakdown": {"fob_eur": 12.40},
    }
    async with await _client(app) as ac:
        resp = await ac.post("/api/v1/costs", json=payload)
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "cost_range_overlap"


async def test_post_costs_422_rejects_legacy_effective_at() -> None:
    """El schema es `extra="forbid"`: el campo viejo `effective_at` se rechaza."""
    svc = _FakeCostService()
    user = _FakeUser()
    app = _build_app(svc, user)
    payload = {
        "sku": "MT-V-038",
        "scheme_code": "FBA",
        "currency_origin": "EUR",
        "effective_at": "2026-06-12T00:00:00Z",
        "valid_from": "2026-06-12",
        "breakdown": {"fob_eur": 12.40},
    }
    async with await _client(app) as ac:
        resp = await ac.post("/api/v1/costs", json=payload)
    assert resp.status_code == 422


async def test_put_costs_corrects_in_place_same_row_still_active() -> None:
    svc = _FakeCostService()
    user = _FakeUser()
    # Pre-seed an open (active) cost.
    cost = _FakeCost(version=1, valid_to=None)
    svc.costs[cost.id] = cost
    app = _build_app(svc, user)
    payload = {
        "breakdown": {"fob_eur": 13.00, "freight_eur": 1.80},
        "valid_from": "2026-07-01",
    }
    async with await _client(app) as ac:
        resp = await ac.put(f"/api/v1/costs/{cost.id}", json=payload)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # Corrección IN-PLACE: misma fila (mismo id), sigue vigente, sin versionar.
    assert body["cost"]["id"] == str(cost.id)
    assert body["cost"]["version"] == 1
    assert body["cost"]["status"] == "active"
    assert body["cost"]["valid_from"] == "2026-07-01"
    assert body["cost"]["breakdown"]["fob_eur"] == 13.00


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
    cost1 = _FakeCost(sku="MT-V-038", scheme_code="FBA", valid_to=None)
    cost2 = _FakeCost(sku="MT-V-038", scheme_code="DIRECT_B2C", valid_to=None)
    # Cerrado (rango pasado) ⇒ no vigente.
    cost3 = _FakeCost(sku="MT-V-038", scheme_code="FBM", valid_to=date(2026, 1, 1))
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

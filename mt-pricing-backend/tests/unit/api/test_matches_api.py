"""Unit tests del router `app.api.routes.matches` (sin DB ni JWT real).

Estrategia:
- Se monta una FastAPI ad-hoc (no la app real) que incluye el router de
  matches con prefijo ``/api/v1`` — NO modificamos ``app/main.py`` ni
  ``app/api/__init__.py`` (ver instrucciones del agente).
- Se overridean las dependencias `get_db_session`, `get_current_user`,
  `require_permissions(...)` y la factory `get_match_service` para devolver
  fakes en memoria.
- El servicio fake reusa el mismo MatchService real, pero conectado al
  in-memory repo (truco: no usa la session). Así ejercitamos la lógica
  ENTERA del router (cursor, mapping, transiciones).

Cobertura:
- ``POST /matches/{sku}/refresh`` devuelve 200 + 8 candidatos para SKU canned.
- ``GET /matches`` filtra por sku/status/channel.
- ``GET /matches/{id}`` devuelve detalle con scoring breakdown poblado.
- ``POST /matches/{id}/validate`` cambia status.
- ``POST /matches/{id}/discard`` con reason.
- 404 para SKU desconocido.
- 409 para transición ilegal validated → discard.
- Cursor opaco encode/decode roundtrip.
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

from app.api.deps import get_current_user, get_db_session, require_permissions
from app.api.routes.matches import get_match_service, router as matches_router
from app.services.matching.match_service import MatchService

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# In-memory test doubles
# ---------------------------------------------------------------------------
class _FakeProduct:
    def __init__(self, sku: str) -> None:
        self.sku = sku
        self.name_en = f"Product {sku}"
        self.family = "ball_valve"
        self.subfamily = None
        self.material = "brass"
        self.dn = "DN50"
        self.pn = "PN25"
        self.connection = "BSP"
        self.brand = "Pegler"
        self.specs = {"norma": "EN13828"}


class _FakeMatchRow:
    def __init__(self, **kw: Any) -> None:
        self.id: UUID = kw.get("id", uuid4())
        self.product_sku: str = kw["product_sku"]
        self.channel: str = kw["channel"]
        self.external_id: str = kw["external_id"]
        self.title: str = kw["title"]
        self.brand = kw.get("brand")
        self.price_aed: Decimal | None = kw.get("price_aed")
        self.delivery_text = kw.get("delivery_text")
        self.specs_jsonb: dict[str, Any] = kw.get("specs_jsonb", {})
        self.kind: str = kw.get("kind", "unknown")
        self.score: int = kw.get("score", 0)
        self.status: str = kw.get("status", "pending")
        self.validated_by: UUID | None = None
        self.validated_at: datetime | None = None
        self.discarded_reason: str | None = None
        now = datetime.now(tz=timezone.utc)
        self.created_at = now
        self.updated_at = now


class _InMemoryMatchRepo:
    def __init__(self) -> None:
        self.rows: list[_FakeMatchRow] = []

    async def find_by_external(
        self, product_sku: str, channel: str, external_id: str
    ) -> _FakeMatchRow | None:
        for r in self.rows:
            if (
                r.product_sku == product_sku
                and r.channel == channel
                and r.external_id == external_id
            ):
                return r
        return None

    async def upsert_candidate(self, **kw: Any) -> _FakeMatchRow:
        existing = await self.find_by_external(
            kw["product_sku"], kw["channel"], kw["external_id"]
        )
        if existing:
            for f in (
                "title",
                "brand",
                "price_aed",
                "delivery_text",
                "specs_jsonb",
                "kind",
                "score",
            ):
                if f in kw:
                    setattr(existing, f, kw[f])
            return existing
        row = _FakeMatchRow(**kw, status="pending")
        self.rows.append(row)
        return row

    async def list_with_filters(
        self,
        *,
        sku: str | None = None,
        status: str | None = None,
        channel: str | None = None,
        cursor: UUID | None = None,
        limit: int = 50,
    ) -> tuple[list[_FakeMatchRow], UUID | None]:
        out = sorted(self.rows, key=lambda r: r.id.bytes)
        if sku is not None:
            out = [r for r in out if r.product_sku == sku]
        if status is not None:
            out = [r for r in out if r.status == status]
        if channel is not None:
            out = [r for r in out if r.channel == channel]
        if cursor is not None:
            out = [r for r in out if r.id.bytes > cursor.bytes]
        sliced = out[: limit + 1]
        if len(sliced) > limit:
            return sliced[:limit], sliced[limit - 1].id
        return sliced, None

    async def get(self, candidate_id: UUID) -> _FakeMatchRow | None:
        for r in self.rows:
            if r.id == candidate_id:
                return r
        return None

    async def mark_validated(
        self, candidate_id: UUID, *, user_id: UUID | None
    ) -> _FakeMatchRow | None:
        row = await self.get(candidate_id)
        if row is None:
            return None
        row.status = "validated"
        row.validated_by = user_id
        row.validated_at = datetime.now(tz=timezone.utc)
        row.discarded_reason = None
        return row

    async def mark_discarded(
        self, candidate_id: UUID, *, reason: str | None = None
    ) -> _FakeMatchRow | None:
        row = await self.get(candidate_id)
        if row is None:
            return None
        row.status = "discarded"
        row.discarded_reason = reason
        return row


class _InMemoryProductRepo:
    def __init__(self, products: dict[str, _FakeProduct]) -> None:
        self._by_sku = products

    async def get_by_sku(self, sku: str) -> _FakeProduct | None:
        return self._by_sku.get(sku)


class _FakeRole:
    """Stand-in para `User.role` esperado por `require_permissions`."""

    def __init__(self, perms: list[str]) -> None:
        self.code = "tester"
        self.permissions_snapshot = perms


class _FakeUser:
    def __init__(self) -> None:
        self.id: UUID = uuid4()
        self.email = "tester@mt.ae"
        self.is_active = True
        # `permissions_snapshot` cubre el path de `require_permissions`.
        self.role = _FakeRole(["products:read", "products:write"])


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
def _make_service_for_router(
    *, products: dict[str, _FakeProduct] | None = None
) -> tuple[MatchService, _InMemoryMatchRepo]:
    products = products or {"MTBR4001050": _FakeProduct("MTBR4001050")}
    fake_session = MagicMock()
    svc = MatchService(fake_session)
    repo = _InMemoryMatchRepo()
    svc._matches_repo = repo  # type: ignore[assignment]
    svc._products_repo = _InMemoryProductRepo(products)  # type: ignore[assignment]
    return svc, repo


def _build_app(
    service: MatchService, user: _FakeUser
) -> FastAPI:
    app = FastAPI()
    app.include_router(matches_router, prefix="/api/v1")

    async def _override_db():  # pragma: no cover — dummy
        yield None

    async def _override_user():
        return user

    def _override_perms(*_codes: str):
        async def _ok():
            return user

        return _ok

    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_current_user] = _override_user
    # require_permissions(...) returns a fresh callable per call site; we
    # need to override the *result* function used at registration time. The
    # simplest path is to override `get_current_user` and patch
    # `require_permissions` factory by replacing the dependency at runtime.
    # FastAPI lets us inject by callable identity — `require_permissions`
    # returns a closure each time. We instead override its *output* via the
    # same trick used in other tests: register the closure used by each
    # endpoint. Since closures are unique per call, we walk the router
    # dependencies and override them.
    for route in matches_router.routes:
        for dependency in getattr(route, "dependant", None).dependencies if getattr(route, "dependant", None) else []:
            call = dependency.call
            if call is not None and getattr(call, "__name__", "") == "_check":
                async def _allow(_call=call):  # noqa: ARG001
                    return user

                app.dependency_overrides[call] = _allow
    app.dependency_overrides[get_match_service] = lambda: service
    return app


async def _client(app: FastAPI) -> AsyncClient:
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://testserver")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
async def test_refresh_returns_8_candidates_for_canned_sku() -> None:
    svc, repo = _make_service_for_router()
    user = _FakeUser()
    app = _build_app(svc, user)
    async with await _client(app) as ac:
        resp = await ac.post("/api/v1/matches/MTBR4001050/refresh")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["sku"] == "MTBR4001050"
    assert body["refreshed_count"] == 8
    assert len(body["candidates"]) == 8
    assert len(repo.rows) == 8


async def test_refresh_unknown_sku_returns_404() -> None:
    svc, _ = _make_service_for_router(products={})
    user = _FakeUser()
    app = _build_app(svc, user)
    async with await _client(app) as ac:
        resp = await ac.post("/api/v1/matches/UNKNOWN/refresh")
    assert resp.status_code == 404
    body = resp.json()
    assert body["detail"]["code"] == "match_sku_not_found"


async def test_list_matches_filters_by_sku_and_status() -> None:
    svc, _ = _make_service_for_router()
    user = _FakeUser()
    app = _build_app(svc, user)
    async with await _client(app) as ac:
        await ac.post("/api/v1/matches/MTBR4001050/refresh")
        resp = await ac.get(
            "/api/v1/matches?sku=MTBR4001050&status=pending&channel=amazon_uae"
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert all(c["channel"] == "amazon_uae" for c in body["items"])
    assert all(c["status"] == "pending" for c in body["items"])
    assert all(c["product_sku"] == "MTBR4001050" for c in body["items"])


async def test_get_detail_includes_scoring_breakdown() -> None:
    svc, repo = _make_service_for_router()
    user = _FakeUser()
    app = _build_app(svc, user)
    async with await _client(app) as ac:
        await ac.post("/api/v1/matches/MTBR4001050/refresh")
        target_id = repo.rows[0].id
        resp = await ac.get(f"/api/v1/matches/{target_id}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == str(target_id)
    assert body["scoring"] is not None
    assert "breakdown" in body["scoring"]
    assert "weights" in body["scoring"]


async def test_get_detail_unknown_id_returns_404() -> None:
    svc, _ = _make_service_for_router()
    user = _FakeUser()
    app = _build_app(svc, user)
    async with await _client(app) as ac:
        resp = await ac.get(f"/api/v1/matches/{uuid4()}")
    assert resp.status_code == 404


async def test_validate_endpoint_changes_status() -> None:
    svc, repo = _make_service_for_router()
    user = _FakeUser()
    app = _build_app(svc, user)
    async with await _client(app) as ac:
        await ac.post("/api/v1/matches/MTBR4001050/refresh")
        target_id = repo.rows[0].id
        resp = await ac.post(f"/api/v1/matches/{target_id}/validate")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "validated"
    assert body["validated_by"] == str(user.id)


async def test_discard_endpoint_records_reason() -> None:
    svc, repo = _make_service_for_router()
    user = _FakeUser()
    app = _build_app(svc, user)
    async with await _client(app) as ac:
        await ac.post("/api/v1/matches/MTBR4001050/refresh")
        target_id = repo.rows[-1].id
        resp = await ac.post(
            f"/api/v1/matches/{target_id}/discard",
            json={"reason": "wrong DN"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "discarded"
    assert body["discarded_reason"] == "wrong DN"


async def test_validate_then_discard_returns_409() -> None:
    svc, repo = _make_service_for_router()
    user = _FakeUser()
    app = _build_app(svc, user)
    async with await _client(app) as ac:
        await ac.post("/api/v1/matches/MTBR4001050/refresh")
        target_id = repo.rows[0].id
        await ac.post(f"/api/v1/matches/{target_id}/validate")
        resp = await ac.post(f"/api/v1/matches/{target_id}/discard")
    assert resp.status_code == 409
    body = resp.json()
    assert body["detail"]["code"] == "match_invalid_transition"


async def test_list_matches_with_pagination_cursor() -> None:
    svc, _ = _make_service_for_router()
    user = _FakeUser()
    app = _build_app(svc, user)
    async with await _client(app) as ac:
        await ac.post("/api/v1/matches/MTBR4001050/refresh")
        # limit=3 → debe haber un cursor para la siguiente página.
        r1 = await ac.get("/api/v1/matches?limit=3")
        assert r1.status_code == 200
        body1 = r1.json()
        assert len(body1["items"]) == 3
        next_cursor = body1["cursor"]["next"]
        assert next_cursor is not None
        # Segunda página: debe traer items distintos.
        r2 = await ac.get(f"/api/v1/matches?limit=3&cursor={next_cursor}")
        assert r2.status_code == 200
        body2 = r2.json()
        ids_p1 = {c["id"] for c in body1["items"]}
        ids_p2 = {c["id"] for c in body2["items"]}
        assert ids_p1.isdisjoint(ids_p2)


async def test_list_matches_invalid_cursor_returns_400() -> None:
    svc, _ = _make_service_for_router()
    user = _FakeUser()
    app = _build_app(svc, user)
    async with await _client(app) as ac:
        resp = await ac.get("/api/v1/matches?cursor=!!not-base64!!")
    assert resp.status_code == 400
    body = resp.json()
    assert body["detail"]["code"] == "invalid_cursor"

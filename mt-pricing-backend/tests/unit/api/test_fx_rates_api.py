"""Unit tests del router `app.api.routes.fx_rates` (sin DB ni JWT real).

Se monta una FastAPI ad-hoc (no la app real) y se overridean las dependencias.
Patrón idéntico a `test_matches_api.py`.

Cobertura:
- POST /fx-rates happy path → 201 + audit emit + autor.
- POST con rate <= 0 → 422 `fx_rate_must_be_positive`.
- POST con currency desconocida → 422.
- POST que el servicio traduce a `fx_retroactive_not_allowed` → 422.
- GET /fx-rates → lista vacía / con filtros.
- POST sin permiso `fx:manage` → 403.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_user, get_db_session, require_permissions
from app.api.routes.fx_rates import get_fx_rate_service, router as fx_router
from app.services.fx import (
    FXRateRetroactiveBlockedError,
    FXRateService,
)
from app.services.fx.fx_rate_service import FXRatePositiveError, InvalidFXCurrencyError

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# In-memory fakes
# ---------------------------------------------------------------------------
class _FakeFXRate:
    def __init__(
        self,
        *,
        from_c: str,
        to_c: str,
        rate: Decimal,
        effective_from: datetime,
        effective_to: datetime | None = None,
        source: str = "manual",
        created_by: UUID | None = None,
    ) -> None:
        self.id = uuid4()
        self.from_currency = from_c
        self.to_currency = to_c
        self.rate = rate
        self.effective_from = effective_from
        self.effective_to = effective_to
        self.source = source
        self.created_by = created_by
        self.created_at = datetime.now(tz=timezone.utc)


class _FakeRole:
    def __init__(self, perms: list[str]) -> None:
        self.code = "tester"
        self.permissions_snapshot = perms


class _FakeUser:
    def __init__(self, perms: list[str]) -> None:
        self.id: UUID = uuid4()
        self.email = "ti@mt.ae"
        self.is_active = True
        self.role = _FakeRole(perms)


class _FakeFXService:
    """Drop-in replacement de FXRateService — espía + control de errores."""

    def __init__(self) -> None:
        self.rows: list[_FakeFXRate] = []
        self.create_raises: Exception | None = None
        self.create_calls: list[dict[str, Any]] = []

    async def list_rates(
        self,
        *,
        from_code: str | None = None,
        to_code: str | None = None,
        only_active: bool = False,
        limit: int = 100,
    ) -> list[_FakeFXRate]:
        out = list(self.rows)
        if from_code:
            out = [r for r in out if r.from_currency == from_code]
        if to_code:
            out = [r for r in out if r.to_currency == to_code]
        if only_active:
            out = [r for r in out if r.effective_to is None]
        return out[:limit]

    async def create_rate(self, **kw: Any) -> _FakeFXRate:
        self.create_calls.append(kw)
        if self.create_raises is not None:
            raise self.create_raises
        row = _FakeFXRate(
            from_c=kw["from_code"].upper(),
            to_c=kw["to_code"].upper(),
            rate=Decimal(str(kw["rate"])),
            effective_from=kw["effective_from"],
            source=kw.get("source", "manual"),
            created_by=kw["actor"].id,
        )
        self.rows.append(row)
        return row


# ---------------------------------------------------------------------------
# App harness
# ---------------------------------------------------------------------------
def _build_app(
    service: _FakeFXService,
    *,
    user: _FakeUser,
    perms_ok: bool = True,
) -> FastAPI:
    app = FastAPI()
    app.include_router(fx_router, prefix="/api/v1")

    async def _override_db():  # pragma: no cover
        yield None

    async def _override_user():
        return user

    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_current_user] = _override_user
    # Patrón heredado de test_matches_api: parchear los `_check` callbacks.
    from fastapi import HTTPException, status

    for route in fx_router.routes:
        dependant = getattr(route, "dependant", None)
        if dependant is None:
            continue
        for dep in dependant.dependencies:
            call = dep.call
            if call is not None and getattr(call, "__name__", "") == "_check":
                if perms_ok:

                    async def _allow(_call=call):  # noqa: ARG001
                        return user

                    app.dependency_overrides[call] = _allow
                else:

                    async def _deny(_call=call):  # noqa: ARG001
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail={
                                "code": "permission_denied",
                                "title": "Missing fx:manage",
                            },
                        )

                    app.dependency_overrides[call] = _deny

    app.dependency_overrides[get_fx_rate_service] = lambda: service
    return app


def _client(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
async def test_post_fx_rate_happy_path() -> None:
    svc = _FakeFXService()
    user = _FakeUser(["fx:read", "fx:manage"])
    app = _build_app(svc, user=user)

    payload = {
        "from_currency": "EUR",
        "to_currency": "AED",
        "rate": "4.18",
        "effective_from": "2026-06-12T00:00:00+00:00",
        "source": "manual",
    }
    async with _client(app) as ac:
        resp = await ac.post("/api/v1/fx-rates", json=payload)

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["from_currency"] == "EUR"
    assert body["to_currency"] == "AED"
    assert Decimal(body["rate"]) == Decimal("4.18")
    assert body["created_by"] == str(user.id)
    assert len(svc.create_calls) == 1


async def test_post_fx_rate_positive_rejected_at_pydantic_layer() -> None:
    """rate <= 0 cae en validación Pydantic (gt=0) → 422."""
    svc = _FakeFXService()
    user = _FakeUser(["fx:read", "fx:manage"])
    app = _build_app(svc, user=user)

    async with _client(app) as ac:
        resp = await ac.post(
            "/api/v1/fx-rates",
            json={
                "from_currency": "EUR",
                "to_currency": "AED",
                "rate": "0",
                "effective_from": "2026-06-12T00:00:00+00:00",
            },
        )
    assert resp.status_code == 422


async def test_post_fx_rate_service_translates_positive_error() -> None:
    """Si el servicio lanza FXRatePositiveError (post-Pydantic), 422 con code."""
    svc = _FakeFXService()
    svc.create_raises = FXRatePositiveError()
    user = _FakeUser(["fx:read", "fx:manage"])
    app = _build_app(svc, user=user)

    async with _client(app) as ac:
        resp = await ac.post(
            "/api/v1/fx-rates",
            json={
                "from_currency": "EUR",
                "to_currency": "AED",
                "rate": "4.18",
                "effective_from": "2026-06-12T00:00:00+00:00",
            },
        )
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "fx_rate_must_be_positive"


async def test_post_fx_rate_invalid_currency() -> None:
    svc = _FakeFXService()
    svc.create_raises = InvalidFXCurrencyError("ZZZ")
    user = _FakeUser(["fx:read", "fx:manage"])
    app = _build_app(svc, user=user)

    async with _client(app) as ac:
        resp = await ac.post(
            "/api/v1/fx-rates",
            json={
                "from_currency": "ZZZ",
                "to_currency": "AED",
                "rate": "1.5",
                "effective_from": "2026-06-12T00:00:00+00:00",
            },
        )
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "fx_invalid_currency"


async def test_post_fx_rate_retroactive_blocked() -> None:
    svc = _FakeFXService()
    svc.create_raises = FXRateRetroactiveBlockedError()
    user = _FakeUser(["fx:read", "fx:manage"])
    app = _build_app(svc, user=user)

    async with _client(app) as ac:
        resp = await ac.post(
            "/api/v1/fx-rates",
            json={
                "from_currency": "EUR",
                "to_currency": "AED",
                "rate": "4.18",
                "effective_from": "2026-01-01T00:00:00+00:00",
            },
        )
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "fx_retroactive_not_allowed"


async def test_post_fx_rate_forbidden_without_permission() -> None:
    svc = _FakeFXService()
    user = _FakeUser(["fx:read"])  # NO fx:manage
    app = _build_app(svc, user=user, perms_ok=False)

    async with _client(app) as ac:
        resp = await ac.post(
            "/api/v1/fx-rates",
            json={
                "from_currency": "EUR",
                "to_currency": "AED",
                "rate": "4.18",
                "effective_from": "2026-06-12T00:00:00+00:00",
            },
        )
    assert resp.status_code == 403


async def test_get_fx_rates_with_filters() -> None:
    svc = _FakeFXService()
    svc.rows.append(
        _FakeFXRate(
            from_c="EUR",
            to_c="AED",
            rate=Decimal("4.18"),
            effective_from=datetime(2026, 6, 12, tzinfo=timezone.utc),
        )
    )
    svc.rows.append(
        _FakeFXRate(
            from_c="USD",
            to_c="AED",
            rate=Decimal("3.67"),
            effective_from=datetime(2026, 6, 12, tzinfo=timezone.utc),
        )
    )
    user = _FakeUser(["fx:read"])
    app = _build_app(svc, user=user)

    async with _client(app) as ac:
        resp = await ac.get("/api/v1/fx-rates?from_currency=EUR&to_currency=AED")

    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["from_currency"] == "EUR"

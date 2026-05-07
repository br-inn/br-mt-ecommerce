"""Unit tests del router `app.api.routes.currencies` (sin DB ni JWT real).

Cobertura:
- GET /currencies → lista con todas (incluye inactivas).
- PATCH /currencies/{code}/active happy path.
- PATCH sobre AED (is_base) → 422 ``cannot_deactivate_base_currency``.
- PATCH sobre code inexistente → 404.
- PATCH sin permiso ``currencies:manage`` → 403.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_user, get_db_session
from app.api.routes.currencies import (
    get_currency_service,
    router as currencies_router,
)
from app.services.currencies import (
    CannotDeactivateBaseCurrencyError,
    CurrencyNotFoundError,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------
class _FakeCurrency:
    def __init__(
        self,
        code: str,
        name: str,
        symbol: str | None = None,
        decimals: int = 2,
        is_base: bool = False,
        active: bool = True,
    ) -> None:
        self.code = code
        self.name = name
        self.symbol = symbol
        self.decimals = decimals
        self.is_base = is_base
        self.active = active
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


class _FakeCurrencyService:
    def __init__(self, currencies: dict[str, _FakeCurrency]) -> None:
        self.currencies = currencies
        self.set_active_calls: list[dict[str, Any]] = []

    async def list_all(self, *, only_active: bool = False) -> list[_FakeCurrency]:
        rows = sorted(self.currencies.values(), key=lambda c: c.code)
        if only_active:
            rows = [r for r in rows if r.active]
        return rows

    async def get_by_code(self, code: str) -> _FakeCurrency:
        normalized = code.strip().upper()
        if normalized not in self.currencies:
            raise CurrencyNotFoundError(normalized)
        return self.currencies[normalized]

    async def set_active(
        self,
        code: str,
        *,
        active: bool,
        actor: Any,
        reason: str | None = None,
    ) -> _FakeCurrency:
        self.set_active_calls.append(
            {"code": code, "active": active, "actor": actor, "reason": reason}
        )
        normalized = code.strip().upper()
        if normalized not in self.currencies:
            raise CurrencyNotFoundError(normalized)
        c = self.currencies[normalized]
        if not active and c.is_base:
            raise CannotDeactivateBaseCurrencyError(c.code)
        c.active = active
        return c


def _build_app(
    service: _FakeCurrencyService,
    *,
    user: _FakeUser,
    perms_ok: bool = True,
) -> FastAPI:
    app = FastAPI()
    app.include_router(currencies_router, prefix="/api/v1")

    async def _override_db():  # pragma: no cover
        yield None

    async def _override_user():
        return user

    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_current_user] = _override_user

    from fastapi import HTTPException, status

    for route in currencies_router.routes:
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
                            detail={"code": "permission_denied", "title": "denied"},
                        )

                    app.dependency_overrides[call] = _deny

    app.dependency_overrides[get_currency_service] = lambda: service
    return app


def _client(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def _seed_currencies() -> dict[str, _FakeCurrency]:
    return {
        "AED": _FakeCurrency("AED", "Dirham", symbol="د.إ", is_base=True),
        "EUR": _FakeCurrency("EUR", "Euro", symbol="€"),
        "USD": _FakeCurrency("USD", "Dollar", symbol="$", active=False),
        "SAR": _FakeCurrency("SAR", "Saudi Riyal", symbol="ر.س"),
    }


async def test_list_currencies_returns_all_including_inactive() -> None:
    svc = _FakeCurrencyService(_seed_currencies())
    user = _FakeUser(["fx:read"])
    app = _build_app(svc, user=user)

    async with _client(app) as ac:
        resp = await ac.get("/api/v1/currencies")

    assert resp.status_code == 200
    rows = resp.json()
    assert {r["code"] for r in rows} == {"AED", "EUR", "USD", "SAR"}
    inactive = [r for r in rows if not r["active"]]
    assert any(r["code"] == "USD" for r in inactive)


async def test_patch_active_deactivate_non_base() -> None:
    svc = _FakeCurrencyService(_seed_currencies())
    user = _FakeUser(["fx:read", "currencies:manage"])
    app = _build_app(svc, user=user)

    async with _client(app) as ac:
        resp = await ac.patch(
            "/api/v1/currencies/SAR/active",
            json={"active": False, "reason": "no longer trading"},
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["code"] == "SAR"
    assert body["active"] is False
    assert len(svc.set_active_calls) == 1
    assert svc.set_active_calls[0]["reason"] == "no longer trading"


async def test_patch_active_blocks_deactivating_base_currency() -> None:
    svc = _FakeCurrencyService(_seed_currencies())
    user = _FakeUser(["fx:read", "currencies:manage"])
    app = _build_app(svc, user=user)

    async with _client(app) as ac:
        resp = await ac.patch(
            "/api/v1/currencies/AED/active",
            json={"active": False},
        )

    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "cannot_deactivate_base_currency"


async def test_patch_active_unknown_currency_returns_404() -> None:
    svc = _FakeCurrencyService(_seed_currencies())
    user = _FakeUser(["fx:read", "currencies:manage"])
    app = _build_app(svc, user=user)

    async with _client(app) as ac:
        resp = await ac.patch(
            "/api/v1/currencies/XYZ/active",
            json={"active": True},
        )

    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "currency_not_found"


async def test_patch_active_forbidden_without_permission() -> None:
    svc = _FakeCurrencyService(_seed_currencies())
    user = _FakeUser(["fx:read"])  # NO currencies:manage
    app = _build_app(svc, user=user, perms_ok=False)

    async with _client(app) as ac:
        resp = await ac.patch(
            "/api/v1/currencies/SAR/active",
            json={"active": False},
        )

    assert resp.status_code == 403

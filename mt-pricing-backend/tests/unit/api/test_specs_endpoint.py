"""Unit tests for GET /api/v1/products/specs/schema endpoint.

Pattern: mount only the products router in an ad-hoc FastAPI app, override
DI for session / current_user / require_permissions.  No real DB.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_user, get_db_session
from app.api.routes.products import router as products_router

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeRole:
    def __init__(self, perms: list[str]) -> None:
        self.code = "tester"
        self.permissions_snapshot = perms


class _FakeUser:
    def __init__(self, perms: list[str] | None = None) -> None:
        self.id = uuid4()
        self.email = "tester@mt.ae"
        self.is_active = True
        self.role = _FakeRole(perms or ["products:read", "products:write"])


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def _build_app(user: _FakeUser) -> FastAPI:
    app = FastAPI()
    app.include_router(products_router, prefix="/api/v1")

    fake_session = MagicMock()

    async def _override_db() -> Any:  # pragma: no cover
        yield fake_session

    async def _override_user() -> _FakeUser:
        return user

    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_current_user] = _override_user

    # Override every require_permissions(_check) closure on the router.
    for route in products_router.routes:
        dependant = getattr(route, "dependant", None)
        if dependant is None:
            continue
        for dependency in dependant.dependencies:
            call = dependency.call
            if call is not None and getattr(call, "__name__", "") == "_check":

                async def _allow(_call=call) -> _FakeUser:
                    return user

                app.dependency_overrides[call] = _allow

    return app


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_specs_schema_valve_ball() -> None:
    """GET /products/specs/schema?family=valve&subfamily=ball returns valve_ball schema."""
    app = _build_app(_FakeUser())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/products/specs/schema?family=valve&subfamily=ball")

    assert resp.status_code == 200
    data = resp.json()
    assert data.get("title") == "Ball Valve Specs"
    assert "properties" in data
    assert "dn" in data["properties"]


@pytest.mark.asyncio
async def test_get_specs_schema_filter() -> None:
    """GET /products/specs/schema?family=filter returns filter schema."""
    app = _build_app(_FakeUser())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/products/specs/schema?family=filter")

    assert resp.status_code == 200
    data = resp.json()
    assert data.get("title") == "Y-Strainer / Filter Specs"
    assert "materials_screen" in data["properties"]


@pytest.mark.asyncio
async def test_get_specs_schema_unknown_family_returns_default() -> None:
    """Unknown family falls back to _default schema (permissive)."""
    app = _build_app(_FakeUser())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/products/specs/schema?family=unknown_xyz")

    assert resp.status_code == 200
    data = resp.json()
    assert data.get("title") == "Default Product Specs"
    # Default schema allows additional properties
    assert data.get("additionalProperties") is True


@pytest.mark.asyncio
async def test_get_specs_schema_missing_family_returns_422() -> None:
    """GET without required `family` query param returns 422."""
    app = _build_app(_FakeUser())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/products/specs/schema")

    assert resp.status_code == 422

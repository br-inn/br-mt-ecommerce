"""Unit tests — Brand Extractor endpoints (US-SCR-05-03).

Estrategia:
- FastAPI ad-hoc con los routers montados sin tocar app/main.py.
- Se overridean get_db_session y get_current_user (+ todas las closures _check
  de require_permissions).
- La sesión se reemplaza por AsyncMock que devuelve filas sintéticas.
- No DB real, no Redis, no Celery.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_user, get_db_session
from app.api.routes.competitor_brands import router as competitor_brands_router
from app.api.routes.scraper import router as scraper_router

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
        self.id: UUID = uuid4()
        self.email = "tester@mt.ae"
        self.is_active = True
        self.role = _FakeRole(perms or ["scraper:read"])


def _make_extractor(
    *,
    brand_id: UUID | None = None,
    marketplace: str = "amazon_uae",
    hit_rate: Decimal = Decimal("0.8500"),
    sample_asins: list[str] | None = None,
    attribute_map: dict[str, Any] | None = None,
    generated_by: str = "claude-haiku-4-5-20251001",
    generated_at: datetime | None = None,
    last_used_at: datetime | None = None,
) -> MagicMock:
    ext = MagicMock()
    ext.brand_id = brand_id or uuid4()
    ext.marketplace = marketplace
    ext.hit_rate = hit_rate
    ext.sample_asins = sample_asins or ["B09ABC1234", "B09XYZ5678"]
    ext.attribute_map = attribute_map or {
        "Brand": {"field": "brand", "type": "str"},
        "Weight": {"field": "weight_kg", "type": "float"},
    }
    ext.generated_by = generated_by
    ext.generated_at = generated_at or datetime(2025, 6, 1, tzinfo=UTC)
    ext.last_used_at = last_used_at
    return ext


def _scalar_one_or_none(value: Any) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _all_rows(rows: list[Any]) -> MagicMock:
    result = MagicMock()
    result.all.return_value = rows
    return result


# ---------------------------------------------------------------------------
# App builders
# ---------------------------------------------------------------------------


def _build_competitor_brands_app(
    fake_session: AsyncMock,
    user: _FakeUser | None = None,
) -> FastAPI:
    app = FastAPI()
    app.include_router(competitor_brands_router, prefix="/api/v1")

    the_user = user or _FakeUser()

    async def _override_db():
        yield fake_session

    async def _override_user():
        return the_user

    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_current_user] = _override_user

    for route in competitor_brands_router.routes:
        dependant = getattr(route, "dependant", None)
        if dependant is None:
            continue
        for dep in dependant.dependencies:
            call = dep.call
            if call is not None and getattr(call, "__name__", "") == "_check":

                async def _allow(_call=call):  # noqa: ARG001
                    return the_user

                app.dependency_overrides[call] = _allow

    return app


def _build_scraper_app(
    fake_session: AsyncMock,
    user: _FakeUser | None = None,
) -> FastAPI:
    app = FastAPI()
    app.include_router(scraper_router, prefix="/api/v1")

    the_user = user or _FakeUser()

    async def _override_db():
        yield fake_session

    async def _override_user():
        return the_user

    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_current_user] = _override_user

    for route in scraper_router.routes:
        dependant = getattr(route, "dependant", None)
        if dependant is None:
            continue
        for dep in dependant.dependencies:
            call = dep.call
            if call is not None and getattr(call, "__name__", "") == "_check":

                async def _allow(_call=call):  # noqa: ARG001
                    return the_user

                app.dependency_overrides[call] = _allow

    return app


async def _client(app: FastAPI) -> AsyncClient:
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://testserver")


# ---------------------------------------------------------------------------
# Tests — GET /competitor-brands/{brand_id}/extractor
# ---------------------------------------------------------------------------


async def test_get_extractor_returns_404_when_not_found() -> None:
    """GET /competitor-brands/{brand_id}/extractor → 404 si no existe extractor."""
    session = AsyncMock()
    session.execute.return_value = _scalar_one_or_none(None)

    app = _build_competitor_brands_app(session)
    brand_id = uuid4()

    async with await _client(app) as ac:
        resp = await ac.get(
            f"/api/v1/competitor-brands/{brand_id}/extractor",
            params={"marketplace": "amazon_uae"},
        )

    assert resp.status_code == 404, resp.text
    body = resp.json()
    assert body["detail"] == "No extractor found"


async def test_get_extractor_returns_data_when_found() -> None:
    """GET /competitor-brands/{brand_id}/extractor → 200 con datos correctos."""
    brand_id = uuid4()
    extractor = _make_extractor(
        brand_id=brand_id,
        marketplace="amazon_uae",
        hit_rate=Decimal("0.9200"),
        attribute_map={
            "Brand": {"field": "brand", "type": "str"},
            "Material": {"field": "material", "type": "str"},
            "Weight (kg)": {"field": "weight_kg", "type": "float"},
        },
        sample_asins=["B001", "B002"],
        generated_by="claude-haiku-4-5-20251001",
        generated_at=datetime(2025, 5, 15, tzinfo=UTC),
        last_used_at=datetime(2025, 6, 1, tzinfo=UTC),
    )

    session = AsyncMock()
    session.execute.return_value = _scalar_one_or_none(extractor)

    app = _build_competitor_brands_app(session)

    async with await _client(app) as ac:
        resp = await ac.get(
            f"/api/v1/competitor-brands/{brand_id}/extractor",
            params={"marketplace": "amazon_uae"},
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["brand_id"] == str(brand_id)
    assert body["marketplace"] == "amazon_uae"
    assert body["hit_rate"] == pytest.approx(0.92)
    assert body["attribute_count"] == 3
    assert body["sample_asins"] == ["B001", "B002"]
    assert body["generated_by"] == "claude-haiku-4-5-20251001"
    assert body["last_used_at"] is not None


async def test_get_extractor_uses_default_marketplace() -> None:
    """GET /competitor-brands/{brand_id}/extractor sin ?marketplace usa 'amazon_uae'."""
    brand_id = uuid4()
    extractor = _make_extractor(brand_id=brand_id, marketplace="amazon_uae")

    session = AsyncMock()
    session.execute.return_value = _scalar_one_or_none(extractor)

    app = _build_competitor_brands_app(session)

    async with await _client(app) as ac:
        resp = await ac.get(f"/api/v1/competitor-brands/{brand_id}/extractor")

    assert resp.status_code == 200, resp.text
    assert resp.json()["marketplace"] == "amazon_uae"


# ---------------------------------------------------------------------------
# Tests — GET /scraper/extractor-stats
# ---------------------------------------------------------------------------


async def _make_stat_row(
    brand_id: UUID | None = None,
    brand_name: str = "Grundfos",
    marketplace: str = "amazon_uae",
    hit_rate: Decimal = Decimal("0.7500"),
    generated_at: datetime | None = None,
    attribute_map: dict[str, Any] | None = None,
) -> MagicMock:
    row = MagicMock()
    row.brand_id = brand_id or uuid4()
    row.brand_name = brand_name
    row.marketplace = marketplace
    row.hit_rate = hit_rate
    row.generated_at = generated_at or datetime(2025, 5, 20, tzinfo=UTC)
    row.attribute_map = attribute_map or {"Brand": {"field": "brand", "type": "str"}}
    return row


async def test_extractor_stats_returns_sorted_list() -> None:
    """GET /scraper/extractor-stats → lista ordenada por hit_rate ASC."""
    brand_a = uuid4()
    brand_b = uuid4()

    row_low = await _make_stat_row(
        brand_id=brand_a,
        brand_name="Grundfos",
        hit_rate=Decimal("0.4500"),
        attribute_map={"Brand": {}, "Model": {}},
    )
    row_high = await _make_stat_row(
        brand_id=brand_b,
        brand_name="Flowserve",
        hit_rate=Decimal("0.9100"),
        attribute_map={"Brand": {}},
    )

    session = AsyncMock()
    session.execute.return_value = _all_rows([row_low, row_high])

    app = _build_scraper_app(session)

    async with await _client(app) as ac:
        resp = await ac.get("/api/v1/scraper/extractor-stats")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) == 2

    # Primer elemento: hit_rate más bajo (Grundfos)
    assert body[0]["brand_name"] == "Grundfos"
    assert body[0]["hit_rate"] == pytest.approx(0.45)
    assert body[0]["attribute_count"] == 2
    assert body[0]["marketplace"] == "amazon_uae"

    # Segundo elemento: hit_rate más alto (Flowserve)
    assert body[1]["brand_name"] == "Flowserve"
    assert body[1]["hit_rate"] == pytest.approx(0.91)
    assert body[1]["attribute_count"] == 1


async def test_extractor_stats_returns_empty_list_when_no_extractors() -> None:
    """GET /scraper/extractor-stats → [] cuando no hay extractores."""
    session = AsyncMock()
    session.execute.return_value = _all_rows([])

    app = _build_scraper_app(session)

    async with await _client(app) as ac:
        resp = await ac.get("/api/v1/scraper/extractor-stats")

    assert resp.status_code == 200, resp.text
    assert resp.json() == []

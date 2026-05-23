"""Unit tests del router `app.api.routes.competitor_brands` (US-SCR-03-02).

Patrón análogo a test_admin_flags_api:
- FastAPI ad-hoc con el router montado en ``/api/v1`` (sin tocar app/main.py).
- Overrides para ``get_db_session``, ``get_current_user`` y las closures de
  ``require_permissions`` generadas por el router al importarse.
- Repositorio en memoria — sin DB real.

Cobertura objetivo (≥ 80 %):
  - POST /competitor-brands/       → 201, 409, 422
  - GET  /competitor-brands/       → 200 paginación/filtro active_only
  - PATCH /competitor-brands/{id}  → 200, 404
  - POST /competitor-brands/run    → 202 con brand_ids, 202 sin brand_ids,
                                      202 nothing_to_do cuando lista vacía
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_user, get_db_session
from app.api.routes.competitor_brands import router as brands_router

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Helpers / fakes
# ---------------------------------------------------------------------------

_NOW = datetime.now(tz=UTC)


def _brand(
    *,
    name: str = "Nibco",
    amazon_dept: str = "industrial",
    amazon_search_term: str | None = None,
    amazon_category_node: str | None = None,
    is_active: bool = True,
    notes: str | None = None,
) -> MagicMock:
    b = MagicMock()
    b.id = uuid4()
    b.name = name
    b.amazon_search_term = amazon_search_term
    b.amazon_dept = amazon_dept
    b.amazon_category_node = amazon_category_node
    b.is_active = is_active
    b.notes = notes
    b.last_scraped_at = None
    b.created_at = _NOW
    b.updated_at = _NOW
    return b


class _FakeRole:
    def __init__(self, perms: list[str]) -> None:
        self.code = "tester"
        self.permissions_snapshot = perms


class _FakeUser:
    def __init__(self, perms: list[str] | None = None) -> None:
        self.id: UUID = uuid4()
        self.email = "tester@mt.ae"
        self.is_active = True
        self.role = _FakeRole(perms or ["products:read", "products:write"])


# ---------------------------------------------------------------------------
# App builder
# ---------------------------------------------------------------------------


def _build_app(user: _FakeUser, repo_mock: Any) -> FastAPI:
    """Monta el router en una FastAPI ad-hoc con dependencias overrideadas."""
    app = FastAPI()
    app.include_router(brands_router, prefix="/api/v1")

    fake_session = AsyncMock()
    fake_session.commit = AsyncMock()

    async def _override_db():  # pragma: no cover
        yield fake_session

    async def _override_user():
        return user

    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_current_user] = _override_user

    # Override require_permissions closures (ver patrón en test_admin_flags_api)
    for route in brands_router.routes:
        dependant = getattr(route, "dependant", None)
        if dependant is None:
            continue
        for dep in dependant.dependencies:
            call = dep.call
            if call is not None and getattr(call, "__name__", "") == "_check":

                async def _allow(_call=call):
                    return user

                app.dependency_overrides[call] = _allow

    return app


def _make_client(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


# ---------------------------------------------------------------------------
# Tests — POST /competitor-brands/
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_brand_returns_201() -> None:
    user = _FakeUser()
    brand = _brand(name="Nibco")
    repo = MagicMock()
    repo.get_by_name = AsyncMock(return_value=None)
    repo.create = AsyncMock(return_value=brand)

    app = _build_app(user, repo)

    with patch("app.api.routes.competitor_brands.CompetitorBrandRepository", return_value=repo):
        async with _make_client(app) as ac:
            resp = await ac.post(
                "/api/v1/competitor-brands/",
                json={"name": "Nibco", "amazon_dept": "industrial"},
            )

    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["name"] == "Nibco"
    assert data["amazon_dept"] == "industrial"


@pytest.mark.asyncio
async def test_create_brand_duplicate_name_returns_409() -> None:
    user = _FakeUser()
    existing = _brand(name="Nibco")
    repo = MagicMock()
    repo.get_by_name = AsyncMock(return_value=existing)

    app = _build_app(user, repo)

    with patch("app.api.routes.competitor_brands.CompetitorBrandRepository", return_value=repo):
        async with _make_client(app) as ac:
            resp = await ac.post(
                "/api/v1/competitor-brands/",
                json={"name": "Nibco", "amazon_dept": "industrial"},
            )

    assert resp.status_code == 409, resp.text
    assert "duplicate_name" in resp.text


@pytest.mark.asyncio
async def test_create_brand_missing_name_returns_422() -> None:
    user = _FakeUser()
    repo = MagicMock()

    app = _build_app(user, repo)

    with patch("app.api.routes.competitor_brands.CompetitorBrandRepository", return_value=repo):
        async with _make_client(app) as ac:
            resp = await ac.post(
                "/api/v1/competitor-brands/",
                json={"amazon_dept": "industrial"},  # name ausente
            )

    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_create_brand_empty_name_returns_422() -> None:
    user = _FakeUser()
    repo = MagicMock()

    app = _build_app(user, repo)

    with patch("app.api.routes.competitor_brands.CompetitorBrandRepository", return_value=repo):
        async with _make_client(app) as ac:
            resp = await ac.post(
                "/api/v1/competitor-brands/",
                json={"name": "", "amazon_dept": "industrial"},
            )

    assert resp.status_code == 422, resp.text


# ---------------------------------------------------------------------------
# Tests — GET /competitor-brands/
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_brands_returns_all() -> None:
    user = _FakeUser()
    brands = [_brand(name="Nibco"), _brand(name="Kitz"), _brand(name="Crane")]
    repo = MagicMock()
    repo.list_all = AsyncMock(return_value=brands)

    app = _build_app(user, repo)

    with patch("app.api.routes.competitor_brands.CompetitorBrandRepository", return_value=repo):
        async with _make_client(app) as ac:
            resp = await ac.get("/api/v1/competitor-brands/")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) == 3
    names = {b["name"] for b in body}
    assert names == {"Nibco", "Kitz", "Crane"}


@pytest.mark.asyncio
async def test_list_brands_active_only_filter() -> None:
    user = _FakeUser()
    active_brands = [_brand(name="Nibco", is_active=True)]
    repo = MagicMock()
    repo.list_active = AsyncMock(return_value=active_brands)

    app = _build_app(user, repo)

    with patch("app.api.routes.competitor_brands.CompetitorBrandRepository", return_value=repo):
        async with _make_client(app) as ac:
            resp = await ac.get("/api/v1/competitor-brands/?active_only=true")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) == 1
    assert body[0]["name"] == "Nibco"
    repo.list_active.assert_called_once()


@pytest.mark.asyncio
async def test_list_brands_empty_returns_empty_list() -> None:
    user = _FakeUser()
    repo = MagicMock()
    repo.list_all = AsyncMock(return_value=[])

    app = _build_app(user, repo)

    with patch("app.api.routes.competitor_brands.CompetitorBrandRepository", return_value=repo):
        async with _make_client(app) as ac:
            resp = await ac.get("/api/v1/competitor-brands/")

    assert resp.status_code == 200, resp.text
    assert resp.json() == []


# ---------------------------------------------------------------------------
# Tests — PATCH /competitor-brands/{id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_brand_partial_update() -> None:
    user = _FakeUser()
    brand = _brand(name="Kitz", amazon_category_node=None)
    updated = _brand(name="Kitz", amazon_category_node="16118159031", is_active=False)
    repo = MagicMock()
    repo.get = AsyncMock(return_value=brand)
    repo.update = AsyncMock(return_value=updated)

    app = _build_app(user, repo)

    with patch("app.api.routes.competitor_brands.CompetitorBrandRepository", return_value=repo):
        async with _make_client(app) as ac:
            resp = await ac.patch(
                f"/api/v1/competitor-brands/{brand.id}",
                json={"amazon_category_node": "16118159031", "is_active": False},
            )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["amazon_category_node"] == "16118159031"
    assert data["is_active"] is False


@pytest.mark.asyncio
async def test_patch_brand_not_found_returns_404() -> None:
    user = _FakeUser()
    repo = MagicMock()
    repo.get = AsyncMock(return_value=None)

    app = _build_app(user, repo)

    with patch("app.api.routes.competitor_brands.CompetitorBrandRepository", return_value=repo):
        async with _make_client(app) as ac:
            resp = await ac.patch(
                f"/api/v1/competitor-brands/{uuid4()}",
                json={"is_active": False},
            )

    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# Tests — POST /competitor-brands/run
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_with_brand_ids_queues_specific_brands() -> None:
    """POST /run con brand_ids específicos encola exactamente esas marcas."""
    user = _FakeUser()
    brand1 = _brand(name="Nibco")
    brand2 = _brand(name="Kitz")
    repo = MagicMock()
    repo.get = AsyncMock(side_effect=[brand1, brand2])

    mock_group_result = MagicMock()
    mock_group_result.id = "test-group-id"
    mock_group_result.save = MagicMock()

    app = _build_app(user, repo)

    mock_task = MagicMock()
    mock_task.s = MagicMock(return_value=MagicMock())
    mock_group = MagicMock()
    mock_group.return_value.apply_async.return_value = mock_group_result

    with (
        patch("app.api.routes.competitor_brands.CompetitorBrandRepository", return_value=repo),
        # Los imports locales dentro de run_brand_scrape necesitan ser parcheados
        # en el módulo celery y app.workers.tasks.scraper respectivamente
        patch("celery.group", mock_group),
        patch("app.workers.tasks.scraper.scrape_brand_task", mock_task),
    ):
        async with _make_client(app) as ac:
            resp = await ac.post(
                "/api/v1/competitor-brands/run",
                json={"brand_ids": [str(brand1.id), str(brand2.id)]},
            )

    assert resp.status_code == 202, resp.text
    data = resp.json()
    assert data["total_brands"] == 2
    assert data["status"] == "queued"
    assert data["job_id"] == "test-group-id"


@pytest.mark.asyncio
async def test_run_without_brand_ids_uses_all_active() -> None:
    """POST /run sin brand_ids usa todas las marcas activas."""
    user = _FakeUser()
    active_brands = [_brand(name="Nibco"), _brand(name="Kitz"), _brand(name="Crane")]
    repo = MagicMock()
    repo.list_active = AsyncMock(return_value=active_brands)

    mock_group_result = MagicMock()
    mock_group_result.id = "batch-group-id"
    mock_group_result.save = MagicMock()

    app = _build_app(user, repo)

    mock_task = MagicMock()
    mock_task.s = MagicMock(return_value=MagicMock())
    mock_group = MagicMock()
    mock_group.return_value.apply_async.return_value = mock_group_result

    with (
        patch("app.api.routes.competitor_brands.CompetitorBrandRepository", return_value=repo),
        patch("celery.group", mock_group),
        patch("app.workers.tasks.scraper.scrape_brand_task", mock_task),
    ):
        async with _make_client(app) as ac:
            resp = await ac.post("/api/v1/competitor-brands/run", json={})

    assert resp.status_code == 202, resp.text
    data = resp.json()
    assert data["total_brands"] == 3
    assert data["status"] == "queued"
    repo.list_active.assert_called_once()


@pytest.mark.asyncio
async def test_run_nothing_to_do_when_no_active_brands() -> None:
    user = _FakeUser()
    repo = MagicMock()
    repo.list_active = AsyncMock(return_value=[])

    app = _build_app(user, repo)

    with patch("app.api.routes.competitor_brands.CompetitorBrandRepository", return_value=repo):
        async with _make_client(app) as ac:
            resp = await ac.post("/api/v1/competitor-brands/run", json={})

    assert resp.status_code == 202, resp.text
    data = resp.json()
    assert data["total_brands"] == 0
    assert data["status"] == "nothing_to_do"
    assert data["job_id"] is None

"""Unit tests para app.api.routes.translations (sin DB, sin LLM).

Estrategia (idéntica a test_translations_workflow_api.py):
- Monta FastAPI ad-hoc con SOLO el router de translations.
- Override de get_db_session, get_current_user y los closures _check de
  require_permissions para evitar JWT real y consultas a BD.
- TranslationCompletionService.complete() mockeado con AsyncMock.

Cobertura:
- POST /complete → 200, devuelve CompletionResultResponse con campos correctos.
- POST /complete con SKUs vacíos → 200, completed=0.
- GET /coverage → 200, shape correcta (total_products, coverage, missing_by_lang).
- GET /coverage con 0 productos → 200, pct=0 y missing = total para todos los langs.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.api.routes.translations import router as translations_router
from app.services.translations.completion_service import CompletionResult

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Fake user
# ---------------------------------------------------------------------------

class _Role:
    def __init__(self) -> None:
        self.code = "admin"
        self.permissions_snapshot: list[str] = ["products:read", "products:write"]


class _FakeUser:
    def __init__(self) -> None:
        self.id = uuid4()
        self.email = "tester@mt.ae"
        self.is_active = True
        self.deleted_at = None
        self.role = _Role()


# ---------------------------------------------------------------------------
# App builder
# ---------------------------------------------------------------------------

def _build_app(session_override: Any) -> FastAPI:
    app = FastAPI()
    app.include_router(translations_router, prefix="/api/v1")

    user = _FakeUser()

    async def _override_db() -> Any:
        yield session_override

    async def _override_user() -> _FakeUser:
        return user

    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_current_user] = _override_user

    # Override every require_permissions _check closure so auth is bypassed.
    for route in translations_router.routes:
        dep = getattr(route, "dependant", None)
        if dep is None:
            continue
        for d in dep.dependencies:
            call = d.call
            if call is not None and getattr(call, "__name__", "") == "_check":
                async def _allow(_call: Any = call) -> _FakeUser:  # noqa: ARG001
                    return user
                app.dependency_overrides[call] = _allow

    return app


def _async_client(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


# ---------------------------------------------------------------------------
# Helpers — mock DB session for coverage endpoint
# ---------------------------------------------------------------------------

def _make_coverage_session(
    total: int,
    lang_counts: list[tuple[str, int]],
) -> AsyncSession:
    """Returns an AsyncSession mock that answers the two coverage queries."""
    session = MagicMock(spec=AsyncSession)

    total_result = MagicMock()
    total_result.scalar_one.return_value = total

    coverage_result = MagicMock()
    coverage_result.all.return_value = lang_counts

    # execute called twice: first for total, then for per-lang counts.
    session.execute = AsyncMock(side_effect=[total_result, coverage_result])
    return session  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Tests — POST /complete
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_complete_endpoint_returns_completion_result() -> None:
    fake_result = CompletionResult(completed=3, skipped=0, errors=0, details=[
        {"sku": "MT-001", "lang": "es", "status": "ai_generated"},
        {"sku": "MT-001", "lang": "fr", "status": "ai_generated"},
        {"sku": "MT-002", "lang": "es", "status": "ai_generated"},
    ])
    fake_session = MagicMock(spec=AsyncSession)
    app = _build_app(fake_session)

    with patch(
        "app.api.routes.translations.TranslationCompletionService"
    ) as MockSvc:
        mock_instance = MockSvc.return_value
        mock_instance.complete = AsyncMock(return_value=fake_result)

        async with _async_client(app) as ac:
            resp = await ac.post(
                "/api/v1/products/translations/complete",
                json={
                    "skus": ["MT-001", "MT-002"],
                    "target_langs": ["es", "fr"],
                    "source_lang": "en",
                },
            )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["completed"] == 3
    assert body["skipped"] == 0
    assert body["errors"] == 0
    assert len(body["details"]) == 3


@pytest.mark.asyncio
async def test_complete_endpoint_passes_source_lang() -> None:
    """Verifies that source_lang is forwarded to the service."""
    fake_result = CompletionResult()
    fake_session = MagicMock(spec=AsyncSession)
    app = _build_app(fake_session)

    with patch(
        "app.api.routes.translations.TranslationCompletionService"
    ) as MockSvc:
        mock_instance = MockSvc.return_value
        mock_instance.complete = AsyncMock(return_value=fake_result)

        async with _async_client(app) as ac:
            await ac.post(
                "/api/v1/products/translations/complete",
                json={
                    "skus": ["MT-001"],
                    "target_langs": ["ar"],
                    "source_lang": "fr",
                },
            )

        mock_instance.complete.assert_awaited_once_with(
            skus=["MT-001"],
            target_langs=["ar"],
            source_lang="fr",
            actor_id=None,
        )


@pytest.mark.asyncio
async def test_complete_endpoint_empty_skus_returns_zero() -> None:
    fake_result = CompletionResult(completed=0, skipped=0, errors=0)
    fake_session = MagicMock(spec=AsyncSession)
    app = _build_app(fake_session)

    with patch(
        "app.api.routes.translations.TranslationCompletionService"
    ) as MockSvc:
        mock_instance = MockSvc.return_value
        mock_instance.complete = AsyncMock(return_value=fake_result)

        async with _async_client(app) as ac:
            resp = await ac.post(
                "/api/v1/products/translations/complete",
                json={"skus": [], "target_langs": ["es"]},
            )

    assert resp.status_code == 200
    assert resp.json()["completed"] == 0


@pytest.mark.asyncio
async def test_complete_endpoint_missing_body_returns_422() -> None:
    fake_session = MagicMock(spec=AsyncSession)
    app = _build_app(fake_session)

    async with _async_client(app) as ac:
        resp = await ac.post("/api/v1/products/translations/complete", json={})

    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Tests — GET /coverage
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_coverage_endpoint_returns_expected_shape() -> None:
    session = _make_coverage_session(
        total=100,
        lang_counts=[("en", 100), ("es", 80), ("ar", 60)],
    )
    app = _build_app(session)

    async with _async_client(app) as ac:
        resp = await ac.get("/api/v1/products/translations/coverage")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total_products"] == 100
    assert isinstance(body["coverage"], list)
    assert isinstance(body["missing_by_lang"], dict)
    # en has 100 → 100% coverage
    en_entry = next((c for c in body["coverage"] if c["lang"] == "en"), None)
    assert en_entry is not None
    assert en_entry["count"] == 100
    assert en_entry["pct"] == 100.0
    # es has 80 → 80% coverage
    es_entry = next((c for c in body["coverage"] if c["lang"] == "es"), None)
    assert es_entry["pct"] == 80.0
    # missing_by_lang["fr"] should be 100 (no fr data)
    assert body["missing_by_lang"]["fr"] == 100
    assert body["missing_by_lang"]["ar"] == 40


@pytest.mark.asyncio
async def test_coverage_endpoint_zero_products() -> None:
    session = _make_coverage_session(total=0, lang_counts=[])
    app = _build_app(session)

    async with _async_client(app) as ac:
        resp = await ac.get("/api/v1/products/translations/coverage")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total_products"] == 0
    assert body["coverage"] == []
    # All supported langs should show 0 missing (total is 0)
    for v in body["missing_by_lang"].values():
        assert v == 0


@pytest.mark.asyncio
async def test_coverage_missing_by_lang_contains_all_supported_langs() -> None:
    session = _make_coverage_session(total=50, lang_counts=[("en", 50)])
    app = _build_app(session)

    async with _async_client(app) as ac:
        resp = await ac.get("/api/v1/products/translations/coverage")

    body = resp.json()
    supported = {"en", "es", "fr", "de", "it", "pt", "ar"}
    assert supported == set(body["missing_by_lang"].keys())

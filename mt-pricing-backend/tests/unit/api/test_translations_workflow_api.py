"""Unit tests del router `app.api.routes.translations_workflow` (sin DB).

Estrategia (alineada con `test_matches_api.py`):

- Monta una FastAPI ad-hoc con SOLO el router de translations_workflow
  (no toca `app/main.py` ni `app/api/__init__.py`).
- Override de `get_current_user`, `get_db_session` y los closures de
  `require_permissions("products:write")` resueltos en cada ruta.
- Override de `get_translation_workflow_service` con un servicio cuyo
  state in-memory es fácil de inspeccionar.

Cobertura:
- request-review: 200 (draft→pending_review).
- request-review: 409 cuando origen es approved.
- reject: 200 (pending_review→draft con reason).
- reject: 422 si `reason` ausente / muy corto (Pydantic).
- mark-stale: 200, devuelve affected y NO toca traducciones EN.
- 404 si la traducción no existe.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_user, get_db_session
from app.api.routes.translations_workflow import (
    get_translation_workflow_service,
)
from app.api.routes.translations_workflow import (
    router as workflow_router,
)
from app.services.products.translation_audit import TranslationAuditEmitter
from app.services.products.translation_workflow import (
    STATE_APPROVED,
    STATE_DRAFT,
    STATE_PENDING_REVIEW,
    STATE_STALE,
    TranslationWorkflowService,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fakes (compartidos en stencil con test_translation_workflow.py — duplicados
# minimales aquí para no acoplar tests entre sí)
# ---------------------------------------------------------------------------
class _FakeProduct:
    def __init__(self, sku: str) -> None:
        self.sku = sku
        self.deleted_at: datetime | None = None


class _FakeTranslation:
    def __init__(
        self,
        sku: str,
        lang: str,
        status: str = STATE_DRAFT,
        translated_by: UUID | None = None,
    ) -> None:
        self.sku = sku
        self.lang = lang
        self.status = status
        self.name = f"name_{lang}_{sku}"
        self.description: str | None = None
        self.marketing_copy: str | None = None
        self.translated_by = translated_by
        self.translated_at: datetime | None = None
        self.reviewed_by: UUID | None = None
        self.reviewed_at: datetime | None = None
        self.staleness_reason: str | None = None
        self.rejection_reason: str | None = None
        now = datetime.now(tz=UTC)
        self.created_at = now
        self.updated_at = now


class _ProductsRepo:
    def __init__(self, products: dict[str, _FakeProduct]) -> None:
        self._by_sku = products

    async def get_by_sku(self, sku: str) -> _FakeProduct | None:
        return self._by_sku.get(sku)


class _TranslationsRepo:
    def __init__(self, rows: list[_FakeTranslation]) -> None:
        self.rows = rows

    async def get_one(self, sku: str, lang: str) -> _FakeTranslation | None:
        for r in self.rows:
            if r.sku == sku and r.lang == lang:
                return r
        return None

    async def get_for_sku(self, sku: str) -> list[_FakeTranslation]:
        return [r for r in self.rows if r.sku == sku]


class _AuditRepo:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def record(self, **kw: Any) -> Any:
        self.calls.append(kw)
        return MagicMock(id=uuid4())


class _Role:
    def __init__(self, perms: list[str]) -> None:
        self.code = "comercial"
        self.permissions_snapshot = perms


class _FakeUser:
    def __init__(self) -> None:
        self.id: UUID = uuid4()
        self.email = "tester@mt.ae"
        self.is_active = True
        self.role = _Role(["products:write", "products:read"])


# ---------------------------------------------------------------------------
# Service factory + app builder
# ---------------------------------------------------------------------------
def _make_service(
    *,
    products: list[str] | None = None,
    rows: list[_FakeTranslation] | None = None,
) -> TranslationWorkflowService:
    products = products or ["MTBR4001050"]
    rows = rows or []
    fake_session = MagicMock()

    async def _flush() -> None:
        return None

    fake_session.flush = _flush

    svc = TranslationWorkflowService(fake_session)
    svc.products = _ProductsRepo({sku: _FakeProduct(sku) for sku in products})  # type: ignore[assignment]
    svc.translations = _TranslationsRepo(list(rows))  # type: ignore[assignment]
    audit = _AuditRepo()
    svc.audit = audit  # type: ignore[assignment]
    svc.audit_emitter = TranslationAuditEmitter(audit)  # type: ignore[arg-type]
    return svc


def _build_app(service: TranslationWorkflowService, user: _FakeUser) -> FastAPI:
    app = FastAPI()
    app.include_router(workflow_router, prefix="/api/v1")

    async def _override_db() -> Any:  # pragma: no cover — dummy
        yield None

    async def _override_user() -> _FakeUser:
        return user

    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_current_user] = _override_user
    # Override de cada cierre `_check` generado por require_permissions.
    for route in workflow_router.routes:
        dep = getattr(route, "dependant", None)
        if dep is None:
            continue
        for d in dep.dependencies:
            call = d.call
            if call is not None and getattr(call, "__name__", "") == "_check":

                async def _allow(_call: Any = call) -> _FakeUser:
                    return user

                app.dependency_overrides[call] = _allow
    app.dependency_overrides[get_translation_workflow_service] = lambda: service
    return app


async def _client(app: FastAPI) -> AsyncClient:
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://testserver")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
async def test_request_review_endpoint_200() -> None:
    row = _FakeTranslation("MTBR4001050", "es", status=STATE_DRAFT)
    svc = _make_service(rows=[row])
    user = _FakeUser()
    app = _build_app(svc, user)
    async with await _client(app) as ac:
        resp = await ac.post("/api/v1/products/MTBR4001050/translations/es/request-review")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == STATE_PENDING_REVIEW
    assert body["sku"] == "MTBR4001050"
    assert body["lang"] == "es"


async def test_request_review_invalid_state_returns_409() -> None:
    row = _FakeTranslation("MTBR4001050", "es", status=STATE_APPROVED)
    svc = _make_service(rows=[row])
    user = _FakeUser()
    app = _build_app(svc, user)
    async with await _client(app) as ac:
        resp = await ac.post("/api/v1/products/MTBR4001050/translations/es/request-review")
    assert resp.status_code == 409, resp.text
    body = resp.json()
    assert body["detail"]["code"] == "invalid_translation_state_transition"


async def test_request_review_unknown_translation_404() -> None:
    svc = _make_service(rows=[])
    user = _FakeUser()
    app = _build_app(svc, user)
    async with await _client(app) as ac:
        resp = await ac.post("/api/v1/products/MTBR4001050/translations/es/request-review")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "translation_not_found"


async def test_reject_endpoint_200_with_reason() -> None:
    row = _FakeTranslation("MTBR4001050", "es", status=STATE_PENDING_REVIEW)
    svc = _make_service(rows=[row])
    user = _FakeUser()
    app = _build_app(svc, user)
    async with await _client(app) as ac:
        resp = await ac.post(
            "/api/v1/products/MTBR4001050/translations/es/reject",
            json={"reason": "vocabulario PIM no coincide"},
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == STATE_DRAFT
    assert body["rejection_reason"] == "vocabulario PIM no coincide"


async def test_reject_missing_reason_returns_422() -> None:
    row = _FakeTranslation("MTBR4001050", "es", status=STATE_PENDING_REVIEW)
    svc = _make_service(rows=[row])
    user = _FakeUser()
    app = _build_app(svc, user)
    async with await _client(app) as ac:
        resp = await ac.post(
            "/api/v1/products/MTBR4001050/translations/es/reject",
            json={},
        )
    # FastAPI/Pydantic validation = 422.
    assert resp.status_code == 422


async def test_reject_short_reason_returns_422() -> None:
    row = _FakeTranslation("MTBR4001050", "es", status=STATE_PENDING_REVIEW)
    svc = _make_service(rows=[row])
    user = _FakeUser()
    app = _build_app(svc, user)
    async with await _client(app) as ac:
        resp = await ac.post(
            "/api/v1/products/MTBR4001050/translations/es/reject",
            json={"reason": "no"},
        )
    assert resp.status_code == 422


async def test_mark_stale_endpoint_returns_affected_only_non_en() -> None:
    rows = [
        _FakeTranslation("MTBR4001050", "es", status=STATE_APPROVED),
        _FakeTranslation("MTBR4001050", "ar", status=STATE_APPROVED),
        _FakeTranslation("MTBR4001050", "en", status=STATE_APPROVED),
    ]
    svc = _make_service(rows=rows)
    user = _FakeUser()
    app = _build_app(svc, user)
    async with await _client(app) as ac:
        resp = await ac.post(
            "/api/v1/products/MTBR4001050/translations/mark-stale",
            json={"reason": "master_en_changed"},
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["sku"] == "MTBR4001050"
    assert body["affected_count"] == 2
    langs = sorted(t["lang"] for t in body["affected"])
    assert langs == ["ar", "es"]
    assert all(t["status"] == STATE_STALE for t in body["affected"])


async def test_mark_stale_idempotent_returns_zero() -> None:
    rows = [
        _FakeTranslation("MTBR4001050", "es", status=STATE_DRAFT),
        _FakeTranslation("MTBR4001050", "ar", status=STATE_STALE),
    ]
    svc = _make_service(rows=rows)
    user = _FakeUser()
    app = _build_app(svc, user)
    async with await _client(app) as ac:
        resp = await ac.post("/api/v1/products/MTBR4001050/translations/mark-stale")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["affected_count"] == 0
    assert body["affected"] == []


async def test_mark_stale_unknown_sku_returns_404() -> None:
    svc = _make_service(products=[], rows=[])
    user = _FakeUser()
    app = _build_app(svc, user)
    async with await _client(app) as ac:
        resp = await ac.post("/api/v1/products/UNKNOWN/translations/mark-stale")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "product_not_found"

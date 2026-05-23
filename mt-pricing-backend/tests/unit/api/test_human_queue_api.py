"""Unit tests del router `app.api.routes.human_queue` (US-RND-01-10).

Estrategia:
- FastAPI ad-hoc montada con el router bajo `/api/v1` (sin tocar app/main.py).
- Override de `get_db_session`, `get_current_user`, `require_permissions`,
  `get_human_queue_service` para fakes in-memory.
- Sin DB real ni JWT real.

Cobertura:
1. ``GET /human-queue`` filtra correctamente por calibrated_confidence < 0.85
   y ordena ASC.
2. ``POST /human-queue/{id}/label`` persiste label=accept, reviewer_user_id
   y reviewed_at.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_user, get_db_session
from app.api.routes.human_queue import (
    get_human_queue_service,
)
from app.api.routes.human_queue import (
    router as human_queue_router,
)
from app.services.matching.human_queue_service import (
    HumanQueueNotFoundError,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------
class _FakeRole:
    def __init__(self, perms: list[str]) -> None:
        self.code = "tester"
        self.permissions_snapshot = perms


class _FakeUser:
    def __init__(self) -> None:
        self.id: UUID = uuid4()
        self.email = "tester@mt.ae"
        self.is_active = True
        self.role = _FakeRole(["matches:read", "matches:write"])


class _FakeMatchRow:
    """In-memory stand-in para MatchCandidate."""

    def __init__(self, **kw: Any) -> None:
        self.id: UUID = kw.get("id", uuid4())
        self.product_sku: str = kw.get("product_sku", "MTBR4001050")
        self.channel: str = kw.get("channel", "amazon_uae")
        self.external_id: str = kw.get("external_id", "B0001")
        self.brand: str | None = kw.get("brand")
        self.title: str = kw.get("title", "Test Product")
        self.price_aed: Decimal | None = kw.get("price_aed")
        self.delivery_text: str | None = None
        self.specs_jsonb: dict = kw.get("specs_jsonb", {})
        self.kind: str = kw.get("kind", "unknown")
        self.score: int = kw.get("score", 70)
        self.status: str = kw.get("status", "pending")
        self.calibrated_confidence: Decimal | None = kw.get("calibrated_confidence")
        self.label: str | None = kw.get("label")
        self.reviewer_user_id: UUID | None = kw.get("reviewer_user_id")
        self.reviewed_at: datetime | None = kw.get("reviewed_at")
        self.validated_by: UUID | None = None
        self.validated_at: datetime | None = None
        self.discarded_reason: str | None = None
        now = datetime.now(tz=UTC)
        self.created_at = now
        self.updated_at = now


class _FakeHumanQueueService:
    """Fake in-memory del HumanQueueService."""

    def __init__(self, rows: list[_FakeMatchRow]) -> None:
        self._rows = rows

    async def list_queue(
        self,
        limit: int = 50,
        offset: int = 0,
        confidence_threshold: float = 0.85,
    ) -> list[_FakeMatchRow]:
        filtered = [
            r
            for r in self._rows
            if r.calibrated_confidence is None
            or r.calibrated_confidence < Decimal(str(confidence_threshold))
        ]
        # Orden ASC nulls last
        filtered.sort(
            key=lambda r: (
                r.calibrated_confidence is None,
                r.calibrated_confidence if r.calibrated_confidence is not None else Decimal("999"),
            )
        )
        return filtered[offset : offset + limit]

    async def label_match(
        self,
        match_id: UUID,
        label: str,
        reviewer_user_id: UUID,
    ) -> _FakeMatchRow:
        for r in self._rows:
            if r.id == match_id:
                r.label = label
                r.reviewer_user_id = reviewer_user_id
                r.reviewed_at = datetime.now(tz=UTC)
                return r
        raise HumanQueueNotFoundError(match_id)


# ---------------------------------------------------------------------------
# App builder
# ---------------------------------------------------------------------------
def _build_app(service: _FakeHumanQueueService, user: _FakeUser) -> FastAPI:
    app = FastAPI()
    app.include_router(human_queue_router, prefix="/api/v1")

    async def _override_db():  # pragma: no cover
        yield None

    async def _override_user():
        return user

    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_current_user] = _override_user

    # Override require_permissions closures
    for route in human_queue_router.routes:
        dependant = getattr(route, "dependant", None)
        if dependant is None:
            continue
        for dep in dependant.dependencies:
            call = dep.call
            if call is not None and getattr(call, "__name__", "") == "_check":

                async def _allow(_call=call):
                    return user

                app.dependency_overrides[call] = _allow

    app.dependency_overrides[get_human_queue_service] = lambda: service
    return app


async def _client(app: FastAPI) -> AsyncClient:
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://testserver")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
async def test_get_human_queue_filters_by_confidence_and_orders_asc() -> None:
    """GET /human-queue devuelve sólo matches con calibrated_confidence < 0.85,
    ordenados ASC (menor confianza primero).
    """
    rows = [
        _FakeMatchRow(
            id=uuid4(),
            external_id="B0001",
            calibrated_confidence=Decimal("0.90"),  # debe excluirse
        ),
        _FakeMatchRow(
            id=uuid4(),
            external_id="B0002",
            calibrated_confidence=Decimal("0.60"),  # incluido
        ),
        _FakeMatchRow(
            id=uuid4(),
            external_id="B0003",
            calibrated_confidence=Decimal("0.30"),  # incluido — peor confianza
        ),
        _FakeMatchRow(
            id=uuid4(),
            external_id="B0004",
            calibrated_confidence=None,  # NULL — incluido al final
        ),
    ]
    user = _FakeUser()
    service = _FakeHumanQueueService(rows)
    app = _build_app(service, user)

    async with await _client(app) as ac:
        resp = await ac.get("/api/v1/human-queue")

    assert resp.status_code == 200, resp.text
    body = resp.json()

    # Sólo 3 items (excluye confidence=0.90)
    assert body["total"] == 3
    assert len(body["items"]) == 3

    # Primer item debe ser el de menor confianza (0.30)
    assert body["items"][0]["external_id"] == "B0003"
    # Segundo: 0.60
    assert body["items"][1]["external_id"] == "B0002"
    # Tercero: NULL (al final)
    assert body["items"][2]["external_id"] == "B0004"
    assert body["items"][2]["calibrated_confidence"] is None

    # Meta fields
    assert body["confidence_threshold"] == 0.85
    assert body["limit"] == 50
    assert body["offset"] == 0


async def test_post_label_persists_accept_and_reviewer() -> None:
    """POST /human-queue/{id}/label persiste label=accept, reviewer_user_id y
    reviewed_at.
    """
    row_id = uuid4()
    rows = [
        _FakeMatchRow(
            id=row_id,
            external_id="B0010",
            calibrated_confidence=Decimal("0.55"),
        ),
    ]
    user = _FakeUser()
    service = _FakeHumanQueueService(rows)
    app = _build_app(service, user)

    async with await _client(app) as ac:
        resp = await ac.post(
            f"/api/v1/human-queue/{row_id}/label",
            json={"label": "accept"},
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()

    # Label persistido
    assert body["label"] == "accept"
    # reviewer_user_id coincide con el usuario fake
    assert body["reviewer_user_id"] == str(user.id)
    # reviewed_at presente y no nulo
    assert body["reviewed_at"] is not None

    # Verificar que el objeto in-memory también mutó
    assert rows[0].label == "accept"
    assert rows[0].reviewer_user_id == user.id


async def test_post_label_unknown_id_returns_404() -> None:
    """POST /human-queue/{id}/label devuelve 404 para ID desconocido."""
    service = _FakeHumanQueueService([])
    user = _FakeUser()
    app = _build_app(service, user)

    async with await _client(app) as ac:
        resp = await ac.post(
            f"/api/v1/human-queue/{uuid4()}/label",
            json={"label": "reject"},
        )

    assert resp.status_code == 404
    body = resp.json()
    assert body["detail"]["code"] == "human_queue_not_found"

"""Tests de integración de los endpoints del agente.

Monta una mini-app con deps sobrescritas (mismo patrón que test_matches_api.py)
para ejercitar las rutas GET/PUT /matches/agent/config, GET /matches/agent/metrics
y POST /matches/{id}/revert sin necesitar red ni JWT real.

Marca: @pytest.mark.integration — requiere Postgres efímero (testcontainers) para
las fixtures que usan db_session. Los tests de HTTP usan async_client con mocks
en memoria.
"""

from __future__ import annotations

import decimal
import uuid
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.api.routes.matches import router as matches_router
from app.db.models.match_agent import MatchAgentConfig
from app.db.models.match_candidate import MatchCandidate

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_config_row(
    *,
    mode: str = "shadow",
    alpha: decimal.Decimal | None = None,
    min_labels_gate: int = 50,
) -> MatchAgentConfig:
    row = MatchAgentConfig.__new__(MatchAgentConfig)
    row.id = 1
    row.mode = mode
    row.alpha = alpha if alpha is not None else decimal.Decimal("0.10")
    row.min_labels_gate = min_labels_gate
    row.updated_at = datetime.now(tz=UTC)
    row.updated_by = None
    return row


# ---------------------------------------------------------------------------
# authed_client fixture (mini-app con deps mockeadas — sin JWT real)
# ---------------------------------------------------------------------------

_FAKE_USER_ID = uuid.uuid4()


class _FakeRole:
    code: str = "admin"


class _FakeUser:
    id: UUID = _FAKE_USER_ID
    email: str = "test@example.com"
    role: _FakeRole = _FakeRole()


def _fake_user() -> _FakeUser:
    return _FakeUser()


@pytest_asyncio.fixture
async def _mini_app(db_session: AsyncSession) -> FastAPI:
    """Mini FastAPI con el router de matches y deps sobrescritas."""
    mini = FastAPI()
    mini.include_router(matches_router, prefix="/api/v1/matches")

    # Inyectar db_session real (del testcontainer)
    async def _get_session():
        yield db_session

    mini.dependency_overrides[get_db_session] = _get_session

    # Bypass auth: override get_current_user con un admin fake (evita JWKS lookup
    # y la creación de funciones nuevas por require_permissions que rompería los
    # dependency_overrides al no coincidir por identidad de objeto).
    mini.dependency_overrides[get_current_user] = _fake_user

    return mini


@pytest_asyncio.fixture
async def authed_client(_mini_app: FastAPI) -> AsyncClient:
    """AsyncClient sobre la mini-app. Equivale al authed_client pedido."""
    transport = ASGITransport(app=_mini_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


# ---------------------------------------------------------------------------
# make_candidate fixture (compatible con test_match_agent_repo.py)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def make_candidate(db_session: AsyncSession):
    """Factory que inserta MatchCandidate sin FK real."""

    async def _factory(
        *,
        score: int = 80,
        status: str = "pending",
        specs_jsonb: dict[str, Any] | None = None,
    ) -> MatchCandidate:
        await db_session.execute(text("SET LOCAL session_replication_role = 'replica'"))
        cid = uuid.uuid4()
        candidate = MatchCandidate(
            id=cid,
            product_sku="TEST-SKU-AGENT-ROUTE",
            channel="amazon_uae",
            external_id=f"EXT-AGENT-{cid.hex[:8]}",
            title="Test product agent routes",
            brand=None,
            price_aed=decimal.Decimal("100.00"),
            delivery_text=None,
            specs_jsonb=specs_jsonb or {},
            kind="peer",
            score=score,
        )
        # Set status directly (bypass FSM)
        candidate.status = status
        db_session.add(candidate)
        await db_session.flush()
        return candidate

    return _factory


# ---------------------------------------------------------------------------
# Seed config fixture
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def seeded_config(db_session: AsyncSession) -> MatchAgentConfig:
    """Garantiza que la fila singleton id=1 existe."""
    row = await db_session.get(MatchAgentConfig, 1)
    if row is None:
        row = MatchAgentConfig(id=1, mode="shadow")
        db_session.add(row)
        await db_session.flush()
    return row


# ---------------------------------------------------------------------------
# Tests — GET /agent/config
# ---------------------------------------------------------------------------


async def test_get_agent_config(
    authed_client: AsyncClient, seeded_config: MatchAgentConfig
) -> None:
    resp = await authed_client.get("/api/v1/matches/agent/config")
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] in ("shadow", "active")
    assert "alpha" in body


# ---------------------------------------------------------------------------
# Tests — PUT /agent/config
# ---------------------------------------------------------------------------


async def test_put_agent_config_changes_alpha(
    authed_client: AsyncClient, seeded_config: MatchAgentConfig
) -> None:
    resp = await authed_client.put(
        "/api/v1/matches/agent/config", json={"alpha": 0.05}
    )
    assert resp.status_code == 200
    assert float(resp.json()["alpha"]) == pytest.approx(0.05)


async def test_put_agent_config_active_blocked_without_labels(
    authed_client: AsyncClient, seeded_config: MatchAgentConfig
) -> None:
    """No se puede pasar a active sin alcanzar el gate de labels."""
    resp = await authed_client.put(
        "/api/v1/matches/agent/config", json={"mode": "active"}
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "labels_gate_not_reached"


# ---------------------------------------------------------------------------
# Tests — GET /agent/metrics
# ---------------------------------------------------------------------------


async def test_get_agent_metrics(
    authed_client: AsyncClient, seeded_config: MatchAgentConfig
) -> None:
    resp = await authed_client.get("/api/v1/matches/agent/metrics")
    assert resp.status_code == 200
    body = resp.json()
    assert "golden_labels_total" in body
    assert "gate_reached" in body
    assert body["mode"] in ("shadow", "active")


# ---------------------------------------------------------------------------
# Tests — POST /{candidate_id}/revert
# ---------------------------------------------------------------------------


async def test_revert_agent_decision(
    authed_client: AsyncClient,
    db_session: AsyncSession,
    make_candidate,
    seeded_config: MatchAgentConfig,
) -> None:
    """Revertir devuelve a pending y limpia _agent."""
    cand = await make_candidate(
        score=85,
        status="validated",
        specs_jsonb={"_agent": {"verdict": "auto_validate", "applied": True}},
    )
    resp = await authed_client.post(f"/api/v1/matches/{cand.id}/revert")
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"


async def test_revert_rejects_human_validated(
    authed_client: AsyncClient,
    make_candidate,
    seeded_config: MatchAgentConfig,
) -> None:
    """No se puede revertir un candidato sin _agent.applied."""
    cand = await make_candidate(score=85, status="validated", specs_jsonb={})
    resp = await authed_client.post(f"/api/v1/matches/{cand.id}/revert")
    assert resp.status_code == 409

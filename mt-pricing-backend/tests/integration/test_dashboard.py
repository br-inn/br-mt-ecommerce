"""Integration tests para `/api/v1/dashboard/stats`.

Cobertura:
1. test_dashboard_unauthenticated_returns_401
2. test_dashboard_empty_db_returns_zeroed_kpis
3. test_dashboard_with_seeded_data_returns_correct_counts
4. test_dashboard_translations_coverage_pct
5. test_dashboard_recent_events_limit_10
"""

from __future__ import annotations

import os
import time
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession

# Force JWT secret BEFORE app config import.
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-jwt-secret-deterministic-32chars!")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "anon-test")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "service-test")

JWT_SECRET = "test-jwt-secret-deterministic-32chars!"
JWT_ALG = "HS256"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _emit_jwt(*, sub: str, email: str) -> str:
    now = int(time.time())
    payload = {
        "sub": sub,
        "aud": "authenticated",
        "email": email,
        "iat": now,
        "exp": now + 3600,
        "user_metadata": {"full_name": "Tester", "locale": "es"},
        "role": "authenticated",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


async def _seed_basic_user(session: AsyncSession, email: str) -> UUID:
    """Crea un User aplicativo sin rol — suficiente para autenticarse."""
    from app.db.models.user import User

    uid = uuid4()
    session.add(
        User(
            id=uid,
            email=email,
            full_name="Tester",
            locale="es",
            is_active=True,
        )
    )
    await session.flush()
    return uid


def _auth_headers(user_id: UUID, email: str) -> dict[str, str]:
    token = _emit_jwt(sub=str(user_id), email=email)
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def app_with_db(db_session: AsyncSession) -> AsyncIterator[Any]:
    from app.api.deps import get_db_session
    from app.main import app

    async def _override() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db_session] = _override
    try:
        yield app
    finally:
        app.dependency_overrides.pop(get_db_session, None)


@pytest_asyncio.fixture
async def client(app_with_db: Any) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app_with_db)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest_asyncio.fixture(autouse=True)
async def _cleanup_data(db_session: AsyncSession) -> AsyncIterator[None]:
    """Limpia productos + audit_events antes de cada test para evitar contaminación."""
    from sqlalchemy import text

    await db_session.execute(text("DELETE FROM product_translations;"))
    await db_session.execute(text("DELETE FROM product_assets;"))
    await db_session.execute(
        text("ALTER TABLE products DISABLE TRIGGER trg_products_no_hard_delete;")
    )
    await db_session.execute(text("DELETE FROM products;"))
    await db_session.execute(
        text("ALTER TABLE products ENABLE TRIGGER trg_products_no_hard_delete;")
    )
    await db_session.execute(text("DELETE FROM audit_events;"))
    await db_session.execute(text("DELETE FROM import_runs;"))
    await db_session.commit()
    yield


@pytest_asyncio.fixture
async def authed_user(db_session: AsyncSession) -> tuple[UUID, str]:
    email = f"dashboard-{uuid4().hex[:8]}@mt.ae"
    uid = await _seed_basic_user(db_session, email)
    return uid, email


# ===========================================================================
# Tests
# ===========================================================================
@pytest.mark.integration
@pytest.mark.asyncio
async def test_dashboard_unauthenticated_returns_401(client: AsyncClient) -> None:
    """Sin Bearer token → 401 (RBAC: panel requiere auth)."""
    res = await client.get("/api/v1/dashboard/stats")
    assert res.status_code == 401
    body = res.json()
    assert body["detail"]["title"] == "Missing bearer token"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_dashboard_empty_db_returns_zeroed_kpis(
    client: AsyncClient,
    authed_user: tuple[UUID, str],
) -> None:
    """DB vacía (salvo el user autenticado) → todos los counts = 0 o el mínimo."""
    uid, email = authed_user

    res = await client.get("/api/v1/dashboard/stats", headers=_auth_headers(uid, email))
    assert res.status_code == 200, res.text
    body = res.json()

    # Catálogo vacío.
    assert body["catalog"]["products_total"] == 0
    assert body["catalog"]["products_active"] == 0
    assert body["catalog"]["products_complete"] == 0
    assert body["catalog"]["products_partial"] == 0
    assert body["catalog"]["products_blocked"] == 0

    # Traducciones — sin productos, cobertura 0%.
    assert body["translations"]["es_approved"] == 0
    assert body["translations"]["ar_approved"] == 0
    assert body["translations"]["es_coverage_pct"] == 0.0
    assert body["translations"]["ar_coverage_pct"] == 0.0

    # Usuarios — al menos el autenticado existe.
    assert body["users"]["total"] >= 1
    assert body["users"]["with_role"] == 0  # Bootstrap no asigna rol.

    # Actividad / jobs vacíos.
    assert body["activity"]["audit_events_24h"] == 0
    assert body["activity"]["recent_events"] == []
    assert body["jobs"]["enabled"] == 0
    assert body["jobs"]["runs_24h"] == 0
    assert body["jobs"]["failures_24h"] == 0

    # `as_of` válido.
    assert "as_of" in body
    datetime.fromisoformat(body["as_of"])  # No lanza si está bien formado.


@pytest.mark.integration
@pytest.mark.asyncio
async def test_dashboard_with_seeded_data_returns_correct_counts(
    client: AsyncClient,
    db_session: AsyncSession,
    authed_user: tuple[UUID, str],
) -> None:
    """Seedea productos + un job + un audit event y verifica conteos."""
    from app.db.models.audit import AuditEvent
    from app.db.models.job import JobDefinition, JobRun
    from app.db.models.product import Product

    uid, email = authed_user

    # 3 productos: 2 active, 1 inactive; 1 complete, 1 partial, 1 blocked.
    db_session.add_all(
        [
            Product(
                sku="MT-V-001",
                family="valves_ball",
                lifecycle_status="active",
                data_quality="complete",
            ),
            Product(
                sku="MT-V-002",
                family="valves_ball",
                lifecycle_status="active",
                data_quality="partial",
            ),
            Product(
                sku="MT-V-003",
                family="valves_ball",
                lifecycle_status="deprecated",
                data_quality="blocked",
            ),
        ]
    )

    # 1 JobDefinition enabled + 1 JobRun success en 24h + 1 JobRun failed en 24h.
    job = JobDefinition(
        code="test_job",
        task_name="app.workers.tasks.dummy",
        schedule_type="interval",
        interval_seconds=60,
        enabled=True,
    )
    db_session.add(job)
    await db_session.flush()

    now = datetime.now(UTC)
    db_session.add_all(
        [
            JobRun(
                job_id=job.id,
                job_code="test_job",
                status="success",
                started_at=now - timedelta(hours=1),
            ),
            JobRun(
                job_id=job.id,
                job_code="test_job",
                status="failure",
                started_at=now - timedelta(hours=2),
            ),
            # Run viejo — fuera de la ventana 24h.
            JobRun(
                job_id=job.id,
                job_code="test_job",
                status="success",
                started_at=now - timedelta(hours=48),
            ),
        ]
    )

    # 1 audit event reciente.
    db_session.add(
        AuditEvent(
            actor_id=uid,
            actor_email=email,
            entity_type="product",
            entity_id="MT-V-001",
            action="product.created",
            event_at=now - timedelta(minutes=10),
        )
    )
    await db_session.flush()

    res = await client.get(
        "/api/v1/dashboard/stats", headers=_auth_headers(uid, email)
    )
    assert res.status_code == 200, res.text
    body = res.json()

    assert body["catalog"]["products_total"] == 3
    assert body["catalog"]["products_active"] == 2
    assert body["catalog"]["products_complete"] == 1
    assert body["catalog"]["products_partial"] == 1
    assert body["catalog"]["products_blocked"] == 1  # blocked = total - complete - partial.

    assert body["jobs"]["enabled"] == 1
    assert body["jobs"]["runs_24h"] == 2  # Excluye el run de -48h.
    assert body["jobs"]["failures_24h"] == 1

    assert body["activity"]["audit_events_24h"] == 1
    assert len(body["activity"]["recent_events"]) == 1
    evt = body["activity"]["recent_events"][0]
    assert evt["entity_type"] == "product"
    assert evt["action"] == "product.created"
    assert evt["actor_id"] == str(uid)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_dashboard_translations_coverage_pct(
    client: AsyncClient,
    db_session: AsyncSession,
    authed_user: tuple[UUID, str],
) -> None:
    """4 productos, 2 con ES approved → 50% cobertura ES."""
    from app.db.models.product import Product, ProductTranslation

    uid, email = authed_user

    skus = ["MT-A-1", "MT-A-2", "MT-A-3", "MT-A-4"]
    db_session.add_all(
        [
            Product(
                sku=sku,
                family="adapters",
                lifecycle_status="active",
                data_quality="partial",
            )
            for sku in skus
        ]
    )
    await db_session.flush()

    # 2 traducciones ES approved + 1 ES draft (no cuenta).
    db_session.add_all(
        [
            ProductTranslation(sku="MT-A-1", lang="es", status="approved"),
            ProductTranslation(sku="MT-A-2", lang="es", status="approved"),
            ProductTranslation(sku="MT-A-3", lang="es", status="draft"),
            ProductTranslation(sku="MT-A-1", lang="ar", status="approved"),
        ]
    )
    await db_session.flush()

    res = await client.get(
        "/api/v1/dashboard/stats", headers=_auth_headers(uid, email)
    )
    assert res.status_code == 200, res.text
    body = res.json()

    assert body["translations"]["es_approved"] == 2
    assert body["translations"]["ar_approved"] == 1
    assert body["translations"]["es_coverage_pct"] == 50.0
    assert body["translations"]["ar_coverage_pct"] == 25.0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_dashboard_recent_events_limit_10(
    client: AsyncClient,
    db_session: AsyncSession,
    authed_user: tuple[UUID, str],
) -> None:
    """Si hay >10 audit events, el tail recent_events trae sólo los 10 más recientes."""
    from app.db.models.audit import AuditEvent

    uid, email = authed_user
    now = datetime.now(UTC)
    # 15 events, ordered from oldest to newest.
    db_session.add_all(
        [
            AuditEvent(
                actor_id=uid,
                actor_email=email,
                entity_type="product",
                entity_id=f"MT-X-{i:03d}",
                action="product.updated",
                event_at=now - timedelta(minutes=15 - i),
            )
            for i in range(15)
        ]
    )
    await db_session.flush()

    res = await client.get(
        "/api/v1/dashboard/stats", headers=_auth_headers(uid, email)
    )
    assert res.status_code == 200, res.text
    body = res.json()

    assert body["activity"]["audit_events_24h"] == 15
    assert len(body["activity"]["recent_events"]) == 10
    # Ordenados desc: el primero debe ser el más reciente (event_at máximo).
    first_event_at = body["activity"]["recent_events"][0]["event_at"]
    last_event_at = body["activity"]["recent_events"][-1]["event_at"]
    assert first_event_at > last_event_at

"""Verifica que /billing/* requiere autenticación y rol gerente/admin.

Hallazgo: billing.py usa get_current_user (autenticación JWT únicamente).
Cualquier usuario autenticado — incluyendo comercial — puede listar y crear
facturas. Los tests fallan hasta que se añada require_role al router.
"""

from __future__ import annotations

import os
import time
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

os.environ.setdefault("SUPABASE_JWT_SECRET", "test-jwt-secret-deterministic-32chars!")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "anon-test")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "service-test")

JWT_SECRET = "test-jwt-secret-deterministic-32chars!"


def _emit_jwt(*, sub: str, email: str, role: str = "comercial") -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "sub": sub,
            "aud": "authenticated",
            "email": email,
            "iat": now,
            "exp": now + 3600,
            "app_metadata": {"role": role},
        },
        JWT_SECRET,
        algorithm="HS256",
    )


async def _seed_user(session: AsyncSession, role_code: str) -> tuple[UUID, str]:
    """Crea un usuario con el rol dado. Devuelve (uuid, email)."""
    from app.db.models.user import Role, User

    role = (await session.execute(select(Role).where(Role.code == role_code))).scalar_one_or_none()
    if role is None:
        role = Role(code=role_code, name=role_code, permissions_snapshot=[])
        session.add(role)
        await session.flush()

    uid = uuid4()
    email = f"{role_code}-{uid.hex[:6]}@mt.ae"
    user = User(
        id=uid,
        email=email,
        full_name="Test",
        locale="es",
        is_active=True,
        role_id=role.id,
    )
    session.add(user)
    await session.flush()
    return uid, email


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


@pytest.mark.integration
async def test_billing_list_without_auth_returns_401(client: AsyncClient) -> None:
    """GET /billing/invoices sin Bearer token → 401."""
    resp = await client.get("/api/v1/billing/invoices")
    assert resp.status_code == 401


@pytest.mark.integration
async def test_billing_list_comercial_returns_403(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """GET /billing/invoices con rol comercial → 403.

    Un usuario comercial no debe ver facturas de clientes.
    Este test FALLA hasta que Task 2 añada require_role al router.
    """
    uid, email = await _seed_user(db_session, "comercial")
    token = _emit_jwt(sub=str(uid), email=email, role="comercial")
    resp = await client.get(
        "/api/v1/billing/invoices",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403, f"Expected 403 but got {resp.status_code}: {resp.text}"


@pytest.mark.integration
async def test_billing_list_gerente_returns_200(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """GET /billing/invoices con rol gerente → 200."""
    uid, email = await _seed_user(db_session, "gerente")
    token = _emit_jwt(sub=str(uid), email=email, role="gerente")
    resp = await client.get(
        "/api/v1/billing/invoices",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200


@pytest.mark.integration
async def test_billing_post_invoice_comercial_returns_403(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """POST /billing/invoices con rol comercial → 403."""
    uid, email = await _seed_user(db_session, "comercial")
    token = _emit_jwt(sub=str(uid), email=email, role="comercial")
    resp = await client.post(
        "/api/v1/billing/invoices",
        headers={"Authorization": f"Bearer {token}"},
        json={"customer_id": "CUST-001"},
    )
    assert resp.status_code == 403

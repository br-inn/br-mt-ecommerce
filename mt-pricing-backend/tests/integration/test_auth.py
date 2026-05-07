"""Integration tests para auth (deps + AuthService + routes).

Estrategia:
- Usamos `db_session` fixture (testcontainer Postgres) y emitimos JWTs HS256
  contra `SUPABASE_JWT_SECRET` (override en setup) para simular Supabase Auth.
- Mockeamos `get_supabase_admin` para evitar llamadas reales a Supabase.
- Tests cubren:
    * Bootstrap on first login.
    * Endpoint /me returns profile + permissions.
    * require_permissions denies when user has no role.
    * Force-logout invokes admin.sign_out.
"""

from __future__ import annotations

import os
import time
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession

# Forzar secret antes de importar config singleton.
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-jwt-secret-deterministic-32chars!")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "anon-test")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "service-test")


JWT_SECRET = "test-jwt-secret-deterministic-32chars!"
JWT_ALG = "HS256"


def _emit_jwt(*, sub: str, email: str, full_name: str = "Test User") -> str:
    now = int(time.time())
    payload = {
        "sub": sub,
        "aud": "authenticated",
        "email": email,
        "iat": now,
        "exp": now + 3600,
        "user_metadata": {"full_name": full_name, "locale": "es"},
        "role": "authenticated",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


@pytest_asyncio.fixture
async def app_with_db(db_session: AsyncSession) -> AsyncIterator[Any]:
    """FastAPI app con override de `get_db_session` apuntando al session de test."""
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
@pytest.mark.asyncio
async def test_get_me_unauthenticated_returns_401(client: AsyncClient) -> None:
    response = await client.get("/api/v1/me")
    assert response.status_code == 401
    body = response.json()
    assert body["detail"]["title"] == "Missing bearer token"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_me_invalid_jwt_returns_401(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/me",
        headers={"Authorization": "Bearer not.a.valid.token"},
    )
    assert response.status_code == 401


@pytest.mark.integration
@pytest.mark.asyncio
async def test_first_login_bootstraps_user_row(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Primera vez que un Supabase user se autentica → row en `public.users`."""
    from app.db.models.user import User
    from sqlalchemy import select

    user_id = str(uuid4())
    token = _emit_jwt(sub=user_id, email="alice@mt.ae", full_name="Alice Test")

    response = await client.get(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["email"] == "alice@mt.ae"
    assert body["full_name"] == "Alice Test"
    assert body["role"] is None  # Sin rol asignado tras bootstrap.
    assert body["permissions"] == []

    # Verificar persistencia en DB.
    db_user = (
        await db_session.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    assert db_user is not None
    assert db_user.is_active is True


@pytest.mark.integration
@pytest.mark.asyncio
async def test_require_permissions_denies_without_role(
    client: AsyncClient,
) -> None:
    """Usuario sin rol no puede listar usuarios (necesita users:read)."""
    user_id = str(uuid4())
    token = _emit_jwt(sub=user_id, email="bob@mt.ae")

    response = await client.get(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    body = response.json()
    assert "missing_permissions" in body["detail"]
    assert "users:read" in body["detail"]["missing_permissions"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_logout_calls_supabase_admin_sign_out(
    client: AsyncClient,
) -> None:
    user_id = str(uuid4())
    token = _emit_jwt(sub=user_id, email="carol@mt.ae")

    fake_admin = MagicMock()
    fake_admin.auth.admin.sign_out = MagicMock(return_value=None)

    with patch(
        "app.api.routes.auth.get_supabase_admin",
        return_value=fake_admin,
    ):
        response = await client.post(
            "/api/v1/me/logout",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 204
    fake_admin.auth.admin.sign_out.assert_called_once_with(user_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_assign_role_then_get_me_returns_permissions(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Tras assign_role, /me devuelve permisos efectivos del rol."""
    from app.db.models.user import Permission, Role, RolePermission, User
    from sqlalchemy import select

    # Seed manual de un rol con un permiso (los seeds reales viven en migraciones).
    perm = Permission(code="products:read", description="Read products")
    db_session.add(perm)
    await db_session.flush()
    role = Role(
        code="comercial",
        name="Comercial",
        description="Sales role",
        permissions_snapshot=["products:read"],
    )
    db_session.add(role)
    await db_session.flush()
    db_session.add(RolePermission(role_id=role.id, permission_id=perm.id))
    await db_session.flush()

    # User con role asignado directamente.
    user_id = uuid4()
    user = User(
        id=user_id,
        email="dave@mt.ae",
        full_name="Dave",
        locale="es",
        is_active=True,
        role_id=role.id,
    )
    db_session.add(user)
    await db_session.flush()

    token = _emit_jwt(sub=str(user_id), email="dave@mt.ae")
    response = await client.get(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["role"]["code"] == "comercial"
    assert "products:read" in body["permissions"]

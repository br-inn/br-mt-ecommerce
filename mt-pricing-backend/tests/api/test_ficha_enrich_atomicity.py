"""Verifica que apply_ficha_series no hace session.commit() interno.

Hallazgo: ficha_enrich.py tenía await session.commit() explícito en el handler,
rompiendo la atomicidad de la transacción.
"""
from __future__ import annotations

import os
import time
from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

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


def _emit_jwt(*, sub: str, email: str) -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "sub": sub,
            "aud": "authenticated",
            "email": email,
            "iat": now,
            "exp": now + 3600,
            "app_metadata": {"role": "admin"},
        },
        JWT_SECRET,
        algorithm="HS256",
    )


async def _seed_admin(session: AsyncSession) -> tuple[str, str]:
    from app.db.models.user import Permission, Role, RolePermission, User

    perms_codes = ["products:read", "products:write"]
    perm_ids = []
    for code in perms_codes:
        existing = (
            await session.execute(
                select(Permission).where(Permission.code == code)
            )
        ).scalar_one_or_none()
        if existing is None:
            from app.db.models.user import Permission as P

            p = P(code=code, description=code)
            session.add(p)
            await session.flush()
            perm_ids.append(p.id)
        else:
            perm_ids.append(existing.id)

    role = (
        await session.execute(select(Role).where(Role.code == "admin"))
    ).scalar_one_or_none()
    if role is None:
        role = Role(code="admin", name="admin", permissions_snapshot=perms_codes)
        session.add(role)
        await session.flush()
        for pid in perm_ids:
            session.add(RolePermission(role_id=role.id, permission_id=pid))
        await session.flush()

    uid = uuid4()
    email = f"admin-{uid.hex[:6]}@mt.ae"
    user = User(
        id=uid,
        email=email,
        full_name="Admin",
        locale="es",
        is_active=True,
        role_id=role.id,
    )
    session.add(user)
    await session.flush()
    return str(uid), email


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
async def test_apply_ficha_series_no_internal_commit(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """apply_ficha_series no debe llamar session.commit() internamente.

    Cuenta las llamadas a commit durante un request. Con el bug, el handler
    hace 1 commit propio (antes de retornar). Con el fix, hace 0 commits
    propios — el ciclo de vida de la sesión gestiona el commit único al final.

    El request falla con 4xx (body inválido o serie inexistente) pero eso
    no importa — lo que verificamos es el conteo de commits ANTES de retornar.
    """
    uid, email = await _seed_admin(db_session)
    token = _emit_jwt(sub=uid, email=email)

    commit_count = 0
    original_commit = db_session.commit

    async def _counting_commit() -> None:
        nonlocal commit_count
        commit_count += 1
        await original_commit()

    db_session.commit = _counting_commit  # type: ignore[method-assign]

    resp = await client.post(
        "/api/v1/products/fichas/series/apply",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "series": "SERIE-INEXISTENTE-TEST",
            "apply_to_skus": [],
            "document_id": "doc-atomicity-test",
            "extracted_data": {},
        },
    )

    # El endpoint retorna 4xx (serie inexistente o body inválido).
    # Lo crítico: commit_count debe ser 0 (no hay commit propio del handler).
    assert commit_count == 0, (
        f"Handler llamó session.commit() {commit_count} vez/veces antes de retornar "
        f"(status={resp.status_code}). Debe ser 0 — el commit lo gestiona el "
        "ciclo de vida del request, no el handler."
    )

"""Integration tests para filtros avanzados (US-1A-02-09 backend).

- ``GET /products`` filtra por dn/pn/material.
- ``GET /products?include_total=true`` devuelve ``total`` además del cursor.
- ``GET /products?q=...`` ejecuta búsqueda full-text (`websearch_to_tsquery`)
  y rankea por peso (sku>name>family>brand).
- ``GET /products?created_after/created_before`` filtra por fecha.
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


def _emit_jwt(*, sub: str, email: str) -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "sub": sub,
            "aud": "authenticated",
            "email": email,
            "iat": now,
            "exp": now + 3600,
            "app_metadata": {"role": "comercial"},
        },
        JWT_SECRET,
        algorithm="HS256",
    )


async def _seed_admin(session: AsyncSession) -> tuple[UUID, str]:
    from app.db.models.user import Permission, Role, RolePermission, User

    perms_codes = ["products:read", "products:write"]
    perm_ids = []
    for code in perms_codes:
        existing = (
            await session.execute(select(Permission).where(Permission.code == code))
        ).scalar_one_or_none()
        if existing is None:
            p = Permission(code=code, description=code)
            session.add(p)
            await session.flush()
            perm_ids.append(p.id)
        else:
            perm_ids.append(existing.id)
    role = (
        await session.execute(select(Role).where(Role.code == "filt_admin"))
    ).scalar_one_or_none()
    if role is None:
        role = Role(code="filt_admin", name="filt_admin", permissions_snapshot=perms_codes)
        session.add(role)
        await session.flush()
        for pid in perm_ids:
            session.add(RolePermission(role_id=role.id, permission_id=pid))
        await session.flush()
    uid = uuid4()
    email = f"filt-{uid.hex[:6]}@mt.ae"
    user = User(id=uid, email=email, full_name="F", locale="es", is_active=True, role_id=role.id)
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


def _payload(sku: str, **kw: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "sku": sku,
        "family": "valves_ball",
        "material": "brass",
        "dn": "DN15",
        "pn": "PN16",
    }
    # name_en is no longer a product column (mig 065: moved to product_translations)
    kw.pop("name_en", None)
    base.update(kw)
    return base


@pytest.mark.integration
@pytest.mark.asyncio
async def test_filter_by_dn(client: AsyncClient, db_session: AsyncSession) -> None:
    uid, email = await _seed_admin(db_session)
    headers = {"Authorization": f"Bearer {_emit_jwt(sub=str(uid), email=email)}"}

    await client.post("/api/v1/products", json=_payload("MT-FLT-DN50", dn="DN50"), headers=headers)
    await client.post("/api/v1/products", json=_payload("MT-FLT-DN15", dn="DN15"), headers=headers)

    r = await client.get("/api/v1/products?dn=DN50", headers=headers)
    assert r.status_code == 200
    skus = {it["sku"] for it in r.json()["items"]}
    assert "MT-FLT-DN50" in skus
    assert "MT-FLT-DN15" not in skus


@pytest.mark.integration
@pytest.mark.asyncio
async def test_filter_by_material(client: AsyncClient, db_session: AsyncSession) -> None:
    uid, email = await _seed_admin(db_session)
    headers = {"Authorization": f"Bearer {_emit_jwt(sub=str(uid), email=email)}"}

    await client.post(
        "/api/v1/products", json=_payload("MT-MAT-BRASS", material="brass"), headers=headers
    )
    await client.post(
        "/api/v1/products", json=_payload("MT-MAT-SS", material="ss316"), headers=headers
    )

    r = await client.get("/api/v1/products?material=ss316", headers=headers)
    assert r.status_code == 200
    skus = {it["sku"] for it in r.json()["items"]}
    assert "MT-MAT-SS" in skus
    assert "MT-MAT-BRASS" not in skus


@pytest.mark.integration
@pytest.mark.asyncio
async def test_include_total_returns_total_count(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    uid, email = await _seed_admin(db_session)
    headers = {"Authorization": f"Bearer {_emit_jwt(sub=str(uid), email=email)}"}

    for i in range(3):
        await client.post("/api/v1/products", json=_payload(f"MT-TOT-{i:03d}"), headers=headers)

    r = await client.get(
        "/api/v1/products?material=brass&include_total=true&limit=2", headers=headers
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] is not None
    assert body["total"] >= 3
    # Sin include_total → total None.
    r2 = await client.get("/api/v1/products?material=brass&limit=2", headers=headers)
    assert r2.status_code == 200
    assert r2.json()["total"] is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_text_search_q_param(client: AsyncClient, db_session: AsyncSession) -> None:
    uid, email = await _seed_admin(db_session)
    headers = {"Authorization": f"Bearer {_emit_jwt(sub=str(uid), email=email)}"}

    await client.post(
        "/api/v1/products",
        json=_payload("MT-SEARCH-001", name_en="Brass DN50 ball valve"),
        headers=headers,
    )
    await client.post(
        "/api/v1/products",
        json=_payload("MT-OTHER-002", name_en="Stainless gate valve"),
        headers=headers,
    )

    r = await client.get("/api/v1/products?q=brass", headers=headers)
    assert r.status_code == 200
    skus = {it["sku"] for it in r.json()["items"]}
    assert "MT-SEARCH-001" in skus
    # gate valve no debería aparecer en búsqueda 'brass'.
    assert "MT-OTHER-002" not in skus


@pytest.mark.integration
@pytest.mark.asyncio
async def test_filter_created_after_invalid_iso_returns_422(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    uid, email = await _seed_admin(db_session)
    headers = {"Authorization": f"Bearer {_emit_jwt(sub=str(uid), email=email)}"}

    r = await client.get("/api/v1/products?created_after=not-a-date", headers=headers)
    assert r.status_code == 422
